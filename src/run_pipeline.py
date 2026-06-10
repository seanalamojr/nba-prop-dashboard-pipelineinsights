"""
Master pipeline runner for PipelineInsights.

Runs all ETL pipelines in the correct dependency order:
1. Teams (already done — no need to re-run unless adding expansions)
2. Players
3. Games (schedule)
4. Player stats (historical — slow, only run daily)
5. Odds (live — run every 30-60 minutes)

Usage:
    python src/run_pipeline.py              # Full refresh
    python src/run_pipeline.py --odds-only  # Just refresh odds
"""

import sys
import logging
from src.etl_pipeline import run_teams_etl
from src.etl_players import run_players_etl
from src.etl_games import run_games_etl
from src.etl_player_stats import run_player_stats_etl
from src.etl_odds import run_odds_etl

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run_full_pipeline():
    """Runs all pipelines in order."""
    logger.info("=" * 60)
    logger.info("🏀 PipelineInsights Full Refresh Starting")
    logger.info("=" * 60)
    
    logger.info("\n[1/5] Teams ETL...")
    run_teams_etl()
    
    logger.info("\n[2/5] Players ETL...")
    run_players_etl()
    
    logger.info("\n[3/5] Games ETL...")
    run_games_etl(days_ahead=14)
    
    logger.info("\n[4/5] Player Stats ETL (limited for speed)...")
    run_player_stats_etl(max_players=50)
    
    logger.info("\n[5/5] Odds ETL...")
    run_odds_etl(max_events=2)
    
    logger.info("\n" + "=" * 60)
    logger.info("✅ Full pipeline refresh complete!")
    logger.info("=" * 60)


def run_odds_refresh():
    """Runs only the odds pipeline (fast, meant for frequent scheduling)."""
    logger.info("🔄 Odds refresh starting...")
    run_odds_etl()
    logger.info("✅ Odds refresh complete.")


if __name__ == "__main__":
    if "--odds-only" in sys.argv:
        run_odds_refresh()
    else:
        run_full_pipeline()