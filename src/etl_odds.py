"""
ETL pipeline for Player Prop Odds.

Fetches current player prop lines from The Odds API for all
upcoming NBA games, then loads them into the odds table.

This pipeline should be run frequently (every 30-60 minutes)
to capture line movements. Watch your monthly API credit budget.
"""

import logging
from datetime import datetime
from sqlalchemy.orm import Session
from src.db.connection import get_engine
from src.db.models import Team, Odd, Game, Player, Sportsbook, PropType, RefreshRun
from src.odds_api_client import get_nba_events, get_event_prop_odds, parse_prop_odds

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Map The Odds API market keys to our prop_type codes
MARKET_TO_PROP_CODE = {
    "player_points": "POINTS",
    "player_rebounds": "REBOUNDS",
    "player_assists": "ASSISTS",
    "player_threes": "THREE_PT",
    "player_blocks": "BLOCKS",
    "player_steals": "STEALS",
}

from datetime import datetime

def find_or_create_game(session: Session, event_payload) -> Game:
    """
    Given a single event from The Odds API, find or create a matching Game row.
    Assumes event_payload has home_team, away_team, and commence_time fields.
    """
    home_team_name = event_payload["home_team"]
    away_team_name = event_payload["away_team"]
    start_time_str = event_payload["commence_time"]  # usually ISO string

    # Parse commence_time to datetime
    start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))

    # Look up home and away teams in the Team table
    home_team = (
        session.query(Team)
        .filter(Team.team_name == home_team_name)
        .first()
    )
    away_team = (
        session.query(Team)
        .filter(Team.team_name == away_team_name)
        .first()
    )

    if not home_team or not away_team:
        # If team lookup fails, you may want to log and skip this event
        raise ValueError(f"Could not find teams for event: {home_team_name} vs {away_team_name}")

    # Try to find an existing game with same teams and start_time
    game = (
        session.query(Game)
        .filter(
            Game.home_team_id == home_team.team_id,
            Game.away_team_id == away_team.team_id,
            Game.game_date == start_time,
        )
        .first()
    )

    if game:
        return game

    # Otherwise create a new game row
    game = Game(
        home_team_id=home_team.team_id,
        away_team_id=away_team.team_id,
        game_date=start_time,
        status="Scheduled",  # treat as upcoming
    )
    session.add(game)
    session.flush()  # assigns game.game_id without committing yet
    return game

def run_odds_etl(max_events: int = None):
    """
    ETL for player prop odds.
    
    Args:
        max_events: Limit number of events to fetch (for testing).
                    Set to 1 during development to save API credits.
    """
    engine = get_engine()
    status = "Success"
    records_loaded = 0
    error_message = None
    
    try:
        # ── EXTRACT ──────────────────────────────────
        events = get_nba_events()
        
        if not events:
            logger.info("No upcoming NBA events found. Odds ETL skipped.")
            return
        
        if max_events:
            events = events[:max_events]
            logger.info(f"Limited to {max_events} events for testing.")
        
        # ── LOAD ─────────────────────────────────────
        with Session(engine) as session:
            # Build lookup dicts to avoid repeated queries
            sportsbooks = session.query(Sportsbook).all()
            sb_lookup = {sb.code: sb.sportsbook_id for sb in sportsbooks}
            
            prop_types = session.query(PropType).all()
            pt_lookup = {pt.code: pt.prop_type_id for pt in prop_types}
            
            players = session.query(Player).all()
            # Build player lookup by full_name (lowercase for fuzzy matching)
            player_lookup = {p.full_name.lower(): p.player_id for p in players}
            
            
            for event in events:
                event_id = event.get("id")
                                # Find or create a Game row for this event
                try:
                    game = find_or_create_game(session, event)
                except Exception as e:
                    logger.warning(f"Could not find/create game for event {event_id}: {e}")
                    continue

                game_id = game.game_id
                
                # Fetch prop odds for this event
                try:
                    event_odds_data = get_event_prop_odds(event_id)
                except Exception as e:
                    logger.warning(f"Could not fetch odds for event {event_id}: {e}")
                    continue
                
                # Parse the raw API response into flat records
                prop_records = parse_prop_odds(event_odds_data)
                logger.info(f"  Event {event_id}: {len(prop_records)} prop lines found.")
                
                for record in prop_records:
                    # Map bookmaker key to sportsbook_id
                    sportsbook_id = sb_lookup.get(record["bookmaker_key"])
                    if not sportsbook_id:
                        logger.debug(f"  Unknown sportsbook: {record['bookmaker_key']}")
                        continue
                    
                    # Map market key to prop_type_id
                    prop_code = MARKET_TO_PROP_CODE.get(record["market_key"])
                    if not prop_code:
                        continue
                    prop_type_id = pt_lookup.get(prop_code)
                    
                    # Match player by name
                    player_name_lower = record["player_name"].lower()
                    player_id = player_lookup.get(player_name_lower)
                    
                    
                    # Store the odds record
                    new_odd = Odd(
                        sportsbook_id=sportsbook_id,
                        game_id=game_id,
                        player_id=player_id,
                        prop_type_id=prop_type_id,
                        market_name=record["market_key"],
                        line_value=record.get("line_value"),
                        over_price=record.get("over_price"),
                        under_price=record.get("under_price"),
                        odds_timestamp=datetime.utcnow(),
                        is_live=False,
                        data_source="TheOddsAPI"
                    )
                    session.add(new_odd)
                    records_loaded += 1
            
            session.commit()
            
            session.add(RefreshRun(
                run_timestamp=datetime.utcnow(),
                source_system="TheOddsAPI",
                status=status,
                records_loaded=records_loaded
            ))
            session.commit()
        
        logger.info(f"✅ Odds ETL complete. {records_loaded} prop lines loaded.")
    
    except Exception as e:
        status = "Failed"
        error_message = str(e)
        logger.error(f"❌ Odds ETL failed: {error_message}")
        with Session(engine) as session:
            session.add(RefreshRun(
                run_timestamp=datetime.utcnow(),
                source_system="TheOddsAPI",
                status="Failed",
                records_loaded=0,
                error_message=error_message
            ))
            session.commit()
        raise


if __name__ == "__main__":
    # IMPORTANT: During testing, always limit to 1 event to save API credits
    run_odds_etl(max_events=1)