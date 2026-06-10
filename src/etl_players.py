"""
ETL pipeline for NBA Players.

Extracts active player data from nba_api static data,
transforms it into clean records, and loads into the players table.

This pipeline uses the NBA official player IDs (from nba_api), not 
BallDontLie IDs. The external_ref column stores these NBA IDs so we
can look up stats later.
"""

import logging
from sqlalchemy.orm import Session
from src.db.connection import get_engine
from src.db.models import Player, Team, RefreshRun
from src.stats_api_client import get_all_active_player_ids_from_nba_api
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run_players_etl():
    """
    Full ETL for players.
    - Extracts: active player list from nba_api static data
    - Transforms: normalizes names and maps team abbreviation → team_id
    - Loads: upserts into players table
    """
    engine = get_engine()
    status = "Success"
    records_loaded = 0
    error_message = None
    
    try:
        # ── EXTRACT ──────────────────────────────────
        raw_players = get_all_active_player_ids_from_nba_api()
        logger.info(f"Extracted {len(raw_players)} active players.")
        
        # ── LOAD ─────────────────────────────────────
        with Session(engine) as session:
            for p in raw_players:
                player_id_str = str(p["id"])
                
                existing = session.query(Player).filter_by(
                    external_ref=player_id_str
                ).first()
                
                if existing:
                    existing.full_name = p.get("full_name", "")
                    existing.first_name = p.get("first_name", "")
                    existing.last_name = p.get("last_name", "")
                    existing.is_active = p.get("is_active", True)
                else:
                    new_player = Player(
                        external_ref=player_id_str,
                        full_name=p.get("full_name", ""),
                        first_name=p.get("first_name", ""),
                        last_name=p.get("last_name", ""),
                        is_active=p.get("is_active", True)
                    )
                    session.add(new_player)
                    records_loaded += 1
            
            session.commit()
            
            # Log run
            session.add(RefreshRun(
                run_timestamp=datetime.utcnow(),
                source_system="nba_api_players",
                status=status,
                records_loaded=records_loaded
            ))
            session.commit()
        
        logger.info(f"✅ Players ETL complete. {records_loaded} new players added.")
    
    except Exception as e:
        status = "Failed"
        error_message = str(e)
        logger.error(f"❌ Players ETL failed: {error_message}")
        with Session(engine) as session:
            session.add(RefreshRun(
                run_timestamp=datetime.utcnow(),
                source_system="nba_api_players",
                status=status,
                records_loaded=0,
                error_message=error_message
            ))
            session.commit()
        raise


if __name__ == "__main__":
    run_players_etl()