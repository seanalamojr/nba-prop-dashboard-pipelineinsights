"""
Prediction module for PipelineInsights.

Generates player prop projections using:
1. Rolling average (last N games) — the primary signal
2. Home/away split adjustment — scales the rolling average up or down
   based on whether the player historically performs better at home or away
3. Confidence interval — a simple range based on standard deviation

Statistical note: This is intentionally simple and transparent.
These are baselines, not guarantees. The model makes no claim of edge.

Usage:
    python src/predictions.py
"""

import logging
import math
from datetime import datetime
from typing import Optional
from unittest import result
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
import pandas as pd
from src.db.connection import get_engine
from src.db.models import (
    Player, Game, Team, PlayerGameStat, PropType,
    PlayerPropPrediction, RefreshRun, Odd
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# How many recent games to use for the rolling average
ROLLING_WINDOW = 10

# Minimum games required to make a prediction (if player has fewer, skip)
MIN_GAMES_REQUIRED = 1

# Model version string — increment this when you change the model
MODEL_VERSION = "rolling_avg_v1"

# Map prop type codes to the column name in player_game_stats
PROP_TO_STAT_COL = {
    "POINTS": "points",
    "REBOUNDS": "rebounds",
    "ASSISTS": "assists",
    "STEALS": "steals",
    "BLOCKS": "blocks",
    "TURNOVERS": "turnovers",
    "THREE_PT": "three_pt_made",
}


def get_player_recent_stats(
    session: Session,
    player_id: int,
    stat_col: str,
    n_games: int = ROLLING_WINDOW
) -> pd.DataFrame:
    """
    Fetches a player's most recent N game stats for a given stat column.
    
    Returns a DataFrame with columns: game_id, game_date, stat_value, is_home
    """
    results = (
        session.query(
            PlayerGameStat,
            Game.game_date,
            Game.home_team_id
        )
        .join(Game, PlayerGameStat.game_id == Game.game_id)
        .filter(PlayerGameStat.player_id == player_id)
        .order_by(Game.game_date.desc())
        .limit(n_games)
        .all()
    )
    
    if not results:
        return pd.DataFrame()
    
    rows = []
    for stat, game_date, home_team_id in results:
        stat_value = getattr(stat, stat_col, None)
        is_home = (stat.team_id == home_team_id)
        rows.append({
            "game_id": stat.game_id,
            "game_date": game_date,
            "stat_value": stat_value if stat_value is not None else 0,
            "is_home": is_home,
            "minutes": stat.minutes_played or 0
        })
    
    return pd.DataFrame(rows)


def calculate_home_away_adjustment(df: pd.DataFrame) -> float:
    """
    Calculates a home/away adjustment factor.
    
    If the player averages 25 points at home and 22 points away,
    and the upcoming game is at home, we want to nudge the projection
    slightly upward.
    
    Method:
    - Compute home average and away average from historical stats
    - Return the ratio: home_avg / overall_avg (if home) or away_avg / overall_avg (if away)
    - If there's not enough data for a split, return 1.0 (no adjustment)
    
    Args:
        df: DataFrame with 'stat_value' and 'is_home' columns
    
    Returns:
        Float adjustment factor (e.g. 1.05 = 5% boost, 0.95 = 5% reduction)
    """
    if len(df) < MIN_GAMES_REQUIRED:
        return 1.0
    
    overall_avg = df["stat_value"].mean()
    if overall_avg == 0:
        return 1.0
    
    home_games = df[df["is_home"] == True]
    away_games = df[df["is_home"] == False]
    
    if len(home_games) < 3 or len(away_games) < 3:
        # Not enough data for a meaningful split
        return 1.0
    
    home_avg = home_games["stat_value"].mean()
    away_avg = away_games["stat_value"].mean()
    
    # Return the ratio — this becomes the multiplier for home or away games
    home_factor = home_avg / overall_avg if overall_avg > 0 else 1.0
    away_factor = away_avg / overall_avg if overall_avg > 0 else 1.0
    
    return home_factor, away_factor


def project_player_prop(
    session: Session,
    player_id: int,
    game_id: int,
    prop_type_id: int,
    prop_code: str,
    is_home_game: bool
) -> Optional[dict]:
    """
    Generates a single player prop projection.
    
    Steps:
    1. Get the player's last ROLLING_WINDOW games for this stat
    2. Calculate rolling average
    3. Apply home/away adjustment
    4. Calculate confidence interval (mean ± 1.5 × std_dev)
    
    Returns:
        Dict with projected_value, lower_ci, upper_ci, input_window_games
        Or None if there's not enough data.
    """
    stat_col = PROP_TO_STAT_COL.get(prop_code)
    if not stat_col:
        return None
    
    df = get_player_recent_stats(session, player_id, stat_col, ROLLING_WINDOW)

    # If no history, try a fallback based on the line itself
    if len(df) < MIN_GAMES_REQUIRED:
        # Look up the line for this exact combo
        o = (
            session.query(Odd)
            .filter(
                Odd.game_id == game_id,
                Odd.player_id == player_id,
                Odd.prop_type_id == prop_type_id,
            )
            .first()
        )
        if not o or o.line_value is None:
            return None  # truly nothing to go on

        line_value = float(o.line_value)
        return {
            "projected_value": line_value,
            "lower_ci": line_value - 1.0,
            "upper_ci": line_value + 1.0,
            "input_window_games": 0,
            "notes": "Fallback: projection = line (no history)",
        }
    # ── Rolling Average ──────────────────────────
    rolling_avg = df["stat_value"].mean()
    std_dev = df["stat_value"].std()
    
    # ── Home/Away Adjustment ─────────────────────
    adjustment_result = calculate_home_away_adjustment(df)
    if isinstance(adjustment_result, tuple):
        home_factor, away_factor = adjustment_result
        adjustment = home_factor if is_home_game else away_factor
    else:
        adjustment = adjustment_result
    
    # Apply the adjustment (cap it so it doesn't go too extreme)
    adjustment = max(0.85, min(1.15, adjustment))  # Cap between -15% and +15%
    projected_value = round(rolling_avg * adjustment, 1)
    
    # ── Confidence Interval ──────────────────────
    # We use 1.5 standard deviations on either side
    # This isn't a formal statistical CI — it's a "likely range" indicator
    if std_dev and not math.isnan(std_dev):
        margin = round(1.5 * std_dev, 1)
    else:
        margin = round(projected_value * 0.2, 1)  # Default: ±20% if no std data
    
    lower_ci = round(max(0, projected_value - margin), 1)
    upper_ci = round(projected_value + margin, 1)
    
    return {
        "projected_value": projected_value,
        "lower_ci": lower_ci,
        "upper_ci": upper_ci,
        "input_window_games": len(df),
        "notes": f"Rolling avg: {rolling_avg:.1f}, Adjustment: {adjustment:.2f}x"
    }


def run_predictions_for_tonight(session: Session) -> int:
    """
    Generates predictions for all upcoming games and active player props.

    For each upcoming game:
      - For each player with odds loaded:
        - For each prop type in those odds:
          - Generate a projection
          - Save to player_prop_predictions

    Returns:
        Number of predictions generated.
    """
    logger.info("Generating predictions for upcoming games...")

    # Get upcoming games (games with status "Scheduled" or a future date)
    upcoming_games = session.query(Game).filter(
        Game.status.in_(["Scheduled", "Pre-Game"])
    ).all()

    if not upcoming_games:
        logger.info("No upcoming games found.")
        return 0

    logger.info(f"Found {len(upcoming_games)} upcoming games.")

    # Get prop types
    prop_types = session.query(PropType).all()
    pt_map = {pt.prop_type_id: pt.code for pt in prop_types}

    predictions_generated = 0

    for game in upcoming_games:
        logger.info(f"Processing game_id={game.game_id}, status={game.status}")

        # Determine which players have odds for this game
        odds_for_game = session.query(Odd).filter(
            Odd.game_id == game.game_id,
            Odd.player_id != None
        ).all()

        logger.info(
            f"  Found {len(odds_for_game)} odds rows with player_id for this game."
        )

        # Unique (player_id, prop_type_id) combos
        player_prop_combos = set(
            (o.player_id, o.prop_type_id)
            for o in odds_for_game
            if o.player_id and o.prop_type_id
        )

        logger.info(
            f"  Unique player/prop combos: {len(player_prop_combos)}"
        )

        for player_id, prop_type_id in player_prop_combos:
            prop_code = pt_map.get(prop_type_id)
            if not prop_code:
                logger.info(
                    f"    No prop_code for prop_type_id={prop_type_id}, skipping."
                )
                continue

            # Determine if this player is the home or away team
            player = session.query(Player).filter_by(player_id=player_id).first()
            is_home = (player and player.team_id == game.home_team_id)

            # Skip if prediction already exists for this combo and model
            existing = session.query(PlayerPropPrediction).filter_by(
                player_id=player_id,
                game_id=game.game_id,
                prop_type_id=prop_type_id,
                model_version=MODEL_VERSION,
            ).first()
            if existing:
                continue

            # Generate the projection
            result = project_player_prop(
                session=session,
                player_id=player_id,
                game_id=game.game_id,
                prop_type_id=prop_type_id,
                prop_code=prop_code,
                is_home_game=is_home,
            )

            if not result:
                logger.info(
                    f"    No projection for player_id={player_id}, prop_type_id={prop_type_id}"
                )
                continue

            prediction = PlayerPropPrediction(
                player_id=player_id,
                game_id=game.game_id,
                prop_type_id=prop_type_id,
                model_version=MODEL_VERSION,
                prediction_timestamp=datetime.utcnow(),
                projected_value=result["projected_value"],
                lower_ci=result["lower_ci"],
                upper_ci=result["upper_ci"],
                input_window_games=result["input_window_games"],
                notes=result["notes"],
            )
            session.add(prediction)
            predictions_generated += 1

    session.commit()
    return predictions_generated


def run_predictions_pipeline():
    """Main entdef run_prediry point for the predictions pipeline."""
    engine = get_engine()
    
    try:
        with Session(engine) as session:
            count = run_predictions_for_tonight(session)
        
        with Session(engine) as session:
            session.add(RefreshRun(
                run_timestamp=datetime.utcnow(),
                source_system="Predictions",
                status="Success",
                records_loaded=count
            ))
            session.commit()
        
        logger.info(f"✅ Predictions complete. {count} new predictions generated.")
    
    except Exception as e:
        logger.error(f"❌ Predictions failed: {e}")
        with Session(engine) as session:
            session.add(RefreshRun(
                run_timestamp=datetime.utcnow(),
                source_system="Predictions",
                status="Failed",
                records_loaded=0,
                error_message=str(e)
            ))
            session.commit()
        raise


if __name__ == "__main__":
    run_predictions_pipeline()