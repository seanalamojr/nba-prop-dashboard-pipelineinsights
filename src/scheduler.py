"""
Background scheduler for PipelineInsights.

Runs ETL pipelines on a schedule without manual intervention.
The scheduler runs in a background thread, so it doesn't block the Dash app.

Schedule:
- Every 60 minutes: Odds refresh (live prop lines update frequently)
- Every 24 hours at 8:00 AM: Full pipeline refresh (players, games, stats)
- Every 60 minutes after odds refresh: Predictions update

Usage pattern (in app.py):
    from src.scheduler import start_scheduler
    start_scheduler()
"""

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

# Module-level scheduler instance (only one should ever run)
_scheduler = None


def refresh_odds_job():
    """Job function: refresh odds data."""
    try:
        from src.etl_odds import run_odds_etl
        logger.info("[Scheduler] Starting odds refresh...")
        run_odds_etl()
        logger.info("[Scheduler] Odds refresh complete.")
    except Exception as e:
        logger.error(f"[Scheduler] Odds refresh failed: {e}")


def refresh_predictions_job():
    """Job function: run predictions after odds are loaded."""
    try:
        from src.predictions import run_predictions_pipeline
        logger.info("[Scheduler] Starting predictions update...")
        run_predictions_pipeline()
        logger.info("[Scheduler] Predictions update complete.")
    except Exception as e:
        logger.error(f"[Scheduler] Predictions update failed: {e}")


def full_pipeline_job():
    """Job function: full data refresh (players, games, stats)."""
    try:
        from src.etl_players import run_players_etl
        from src.etl_games import run_games_etl
        from src.etl_player_stats import run_player_stats_etl
        
        logger.info("[Scheduler] Starting full pipeline refresh...")
        run_players_etl()
        run_games_etl(days_ahead=14)
        run_player_stats_etl(max_players=100)
        logger.info("[Scheduler] Full pipeline refresh complete.")
    except Exception as e:
        logger.error(f"[Scheduler] Full pipeline failed: {e}")


def start_scheduler():
    """
    Starts the background scheduler.
    
    Call this once from app.py before app.run().
    The scheduler runs in a daemon thread so it stops when the main app stops.
    """
    global _scheduler
    
    if _scheduler and _scheduler.running:
        logger.info("Scheduler already running.")
        return
    
    _scheduler = BackgroundScheduler(daemon=True)
    
    # Odds: every 60 minutes
    _scheduler.add_job(
        refresh_odds_job,
        trigger=IntervalTrigger(minutes=60),
        id="odds_refresh",
        name="Refresh Odds",
        replace_existing=True
    )
    
    # Predictions: every 60 minutes, offset by 5 minutes from odds
    _scheduler.add_job(
        refresh_predictions_job,
        trigger=IntervalTrigger(minutes=60, start_date="2000-01-01 00:05:00"),
        id="predictions_refresh",
        name="Refresh Predictions",
        replace_existing=True
    )
    
    # Full pipeline: daily at 8:00 AM
    _scheduler.add_job(
        full_pipeline_job,
        trigger=CronTrigger(hour=8, minute=0),
        id="full_pipeline",
        name="Daily Full Pipeline",
        replace_existing=True
    )
    
    _scheduler.start()
    logger.info("✅ Scheduler started. Jobs scheduled:")
    for job in _scheduler.get_jobs():
        logger.info(f"   - {job.name}: next run at {job.next_run_time}")


def stop_scheduler():
    """Stops the scheduler gracefully."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")