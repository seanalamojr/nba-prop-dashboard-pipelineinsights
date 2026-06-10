"""
ETL pipeline for NBA Games (Schedule).

Pulls game schedule data from BallDontLie for a date window
and loads into the games table.
"""

import logging
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from src.db.connection import get_engine
from src.db.models import Game, Team, RefreshRun
from src.stats_api_client import get_games_for_date_range

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run_games_etl(days_ahead: int = 7):
    """
    ETL for games. Fetches from today through the next `days_ahead` days.
    
    Args:
        days_ahead: How many days forward to fetch games for. Default: 7.
    """
    engine = get_engine()
    status = "Success"
    records_loaded = 0
    error_message = None
    
    try:
        # Date range: today through X days ahead
        start = date.today().isoformat()
        end = (date.today() + timedelta(days=days_ahead)).isoformat()
        
        # ── EXTRACT ──────────────────────────────────
        raw_games = get_games_for_date_range(start, end)
        logger.info(f"Extracted {len(raw_games)} games ({start} to {end}).")
        
        # ── LOAD ─────────────────────────────────────
        with Session(engine) as session:
            # Build a lookup dict: abbreviation → team_id
            # This avoids querying the database once per game
            teams = session.query(Team).all()
            team_lookup = {t.team_name: t.team_id for t in teams}
            # Also add abbreviation-based lookup
            abbrev_lookup = {t.team_abbreviation: t.team_id for t in teams}
            
            for g in raw_games:
                external_ref = str(g["id"])
                
                existing = session.query(Game).filter_by(
                    external_ref=external_ref
                ).first()
                
                if existing:
                    # Update status (game may have moved from Scheduled to Final)
                    existing.status = g.get("status", "Scheduled")
                    continue
                
                # Map team names to team_ids
                home_abbrev = g.get("home_team", {}).get("abbreviation", "")
                away_abbrev = g.get("visitor_team", {}).get("abbreviation", "")
                home_team_id = abbrev_lookup.get(home_abbrev)
                away_team_id = abbrev_lookup.get(away_abbrev)
                
                if not home_team_id or not away_team_id:
                    logger.warning(f"Could not match teams for game {external_ref}: {away_abbrev} @ {home_abbrev}")
                    continue
                
                game_date_str = g.get("date", "")
                game_date = datetime.strptime(game_date_str[:10], "%Y-%m-%d").date() if game_date_str else None
                
                new_game = Game(
                    external_ref=external_ref,
                    season=g.get("season"),
                    game_date=game_date,
                    home_team_id=home_team_id,
                    away_team_id=away_team_id,
                    status=g.get("status", "Scheduled")
                )
                session.add(new_game)
                records_loaded += 1
            
            session.commit()
            
            session.add(RefreshRun(
                run_timestamp=datetime.utcnow(),
                source_system="BallDontLie_games",
                status=status,
                records_loaded=records_loaded
            ))
            session.commit()
        
        logger.info(f"✅ Games ETL complete. {records_loaded} new games added.")
    
    except Exception as e:
        status = "Failed"
        error_message = str(e)
        logger.error(f"❌ Games ETL failed: {error_message}")
        with Session(engine) as session:
            session.add(RefreshRun(
                run_timestamp=datetime.utcnow(),
                source_system="BallDontLie_games",
                status="Failed",
                records_loaded=0,
                error_message=error_message
            ))
            session.commit()
        raise


if __name__ == "__main__":
    run_games_etl()