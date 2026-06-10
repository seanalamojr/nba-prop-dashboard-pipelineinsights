"""
ETL pipeline for Player Game Stats.

Pulls game-by-game stats for active players using nba_api.
This is the data the prediction model uses to calculate rolling averages.

Strategy:
- Get list of active players from the database
- For each player, fetch their game log for the current season
- Load new stat rows into player_game_stats (skip rows already loaded)

Performance note: nba_api requires a small sleep between calls to
avoid rate limiting from NBA.com. For 500 players, this pipeline
will take 5-10 minutes to run. That's why we run it on a schedule,
not on every dashboard visit.
"""

import time
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from src.db.connection import get_engine
from src.db.models import Player, Game, Team, PlayerGameStat, RefreshRun
from src.stats_api_client import get_player_game_log




logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

CURRENT_SEASON = "2024-25"

def demo():
    print("demo works")

def run_player_stats_etl(max_players: int = None):
    """
    ETL for player game stats.
    
    Args:
        max_players: Optionally limit how many players to process
                     (useful for testing — set to 10 to test quickly)
    """
    engine = get_engine()
    status = "Success"
    records_loaded = 0
    error_message = None
    
    try:
        with Session(engine) as session:
            # Get active players who have an external_ref (NBA ID)
            query = session.query(Player).filter(
                Player.is_active == True,
                Player.external_ref != None
            )
            if max_players:
                query = query.limit(max_players)
            players = query.all()
        
        logger.info(f"Processing stats for {len(players)} players...")
        
        with Session(engine) as session:
            # Build a lookup: game date → game objects
            # We'll use this to match nba_api game dates to our games table
            games = session.query(Game).filter(
                Game.season == 2024
            ).all()
            # Key: YYYYMMDD string (nba_api uses this format in GAME_ID)
            games_by_external_ref = {g.external_ref: g for g in games if g.external_ref}
            
            # Build team lookup
            teams = session.query(Team).all()
            team_abbrev_lookup = {t.team_abbreviation: t.team_id for t in teams}
            
            for idx, player in enumerate(players):
                try:
                    # Fetch the player's game log
                    df = get_player_game_log(player.external_ref, CURRENT_SEASON)
                    
                    for _, row in df.iterrows():
                        game_id_str = str(row.get("Game_ID", ""))
                        
                        # Find the matching game in our database
                        # nba_api GAME_ID format: "0022400123" — we match by external_ref
                        existing_game = games_by_external_ref.get(game_id_str)
                        
                        if not existing_game:
                            # Game not in our database yet — skip this stat row
                            continue
                        
                        # Check if we already have this stat row
                        existing_stat = session.query(PlayerGameStat).filter_by(
                            player_id=player.player_id,
                            game_id=existing_game.game_id
                        ).first()
                        
                        if existing_stat:
                            continue
                        
                        # Parse the MATCHUP to determine team (e.g. "BOS vs. LAL")
                        matchup = str(row.get("MATCHUP", ""))
                        team_abbrev = matchup.split(" ")[0] if matchup else ""
                        team_id = team_abbrev_lookup.get(team_abbrev)
                        
                        # Parse minutes (nba_api returns "32:45" format)
                        min_str = str(row.get("MIN", "0"))
                        try:
                            if ":" in min_str:
                                parts = min_str.split(":")
                                minutes_played = int(parts[0]) + int(parts[1]) / 60
                            else:
                                minutes_played = float(min_str) if min_str else 0
                        except (ValueError, IndexError):
                            minutes_played = 0
                        
                        new_stat = PlayerGameStat(
                            player_id=player.player_id,
                            game_id=existing_game.game_id,
                            team_id=team_id,
                            minutes_played=round(minutes_played, 2),
                            points=int(row.get("PTS", 0) or 0),
                            rebounds=int(row.get("REB", 0) or 0),
                            assists=int(row.get("AST", 0) or 0),
                            steals=int(row.get("STL", 0) or 0),
                            blocks=int(row.get("BLK", 0) or 0),
                            turnovers=int(row.get("TOV", 0) or 0),
                            field_goal_attempts=int(row.get("FGA", 0) or 0),
                            field_goals_made=int(row.get("FGM", 0) or 0),
                            three_pt_attempts=int(row.get("FG3A", 0) or 0),
                            three_pt_made=int(row.get("FG3M", 0) or 0),
                            free_throw_attempts=int(row.get("FTA", 0) or 0),
                            free_throws_made=int(row.get("FTM", 0) or 0),
                        )
                        session.add(new_stat)
                        records_loaded += 1
                    
                    # Commit every 10 players to avoid large transactions
                    if idx % 10 == 0:
                        session.commit()
                        logger.info(f"  Progress: {idx + 1}/{len(players)} players processed, {records_loaded} stats loaded")
                    
                except Exception as player_error:
                    logger.warning(f"  Skipping player {player.full_name}: {player_error}")
                    continue
            
            session.commit()
            
            session.add(RefreshRun(
                run_timestamp=datetime.utcnow(),
                source_system="nba_api_stats",
                status=status,
                records_loaded=records_loaded
            ))
            session.commit()
        
        logger.info(f"✅ Player stats ETL complete. {records_loaded} new stat rows loaded.")
    
    except Exception as e:
        status = "Failed"
        error_message = str(e)
        logger.error(f"❌ Player stats ETL failed: {error_message}")
        with Session(engine) as session:
            session.add(RefreshRun(
                run_timestamp=datetime.utcnow(),
                source_system="nba_api_stats",
                status="Failed",
                records_loaded=0,
                error_message=error_message
            ))
            session.commit()
        raise


if __name__ == "__main__":
    # During development, test with only 5 players to make it fast
    run_player_stats_etl(max_players=5)