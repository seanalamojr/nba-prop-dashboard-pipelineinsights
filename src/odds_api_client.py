"""
Client for The Odds API.

This module handles all HTTP requests to https://api.the-odds-api.com/v4/
It abstracts the HTTP calls so the ETL pipeline doesn't need to know
about URLs, headers, or request parameters — it just calls functions.

API documentation: https://the-odds-api.com/liveapi/guides/v4/

The two main things we fetch:
1. NBA events (upcoming games + their event IDs)
2. Player prop odds for each event
"""

import os
import requests
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Base URL for all API calls
BASE_URL = "https://api.the-odds-api.com/v4"

# The Odds API key for NBA
NBA_SPORT_KEY = "basketball_nba"

# The prop market keys we want — these must match exactly what The Odds API expects
PROP_MARKETS = [
    "player_points",
    "player_rebounds",
    "player_assists",
    "player_threes",
    "player_blocks",
    "player_steals",
]


def get_api_key() -> str:
    """Reads the API key from the environment. Raises an error if not set."""
    key = os.getenv("ODDS_API_KEY")
    if not key:
        raise ValueError(
            "ODDS_API_KEY not found. Make sure it's set in your .env file."
        )
    return key


def get_nba_events() -> list[dict]:
    """
    Fetches upcoming and in-progress NBA games from The Odds API.
    
    This endpoint does NOT count against your usage quota — it's free to call.
    We use it to get event IDs, which we then pass to the odds endpoint.
    
    Returns:
        List of event dicts, each containing:
        - id: the event's unique ID (used in odds calls)
        - sport_key: "basketball_nba"
        - commence_time: ISO timestamp of game start
        - home_team: home team name string
        - away_team: away team name string
    """
    url = f"{BASE_URL}/sports/{NBA_SPORT_KEY}/events"
    params = {
        "apiKey": get_api_key(),
        "dateFormat": "iso"
    }
    
    logger.info("Fetching NBA events from The Odds API...")
    response = requests.get(url, params=params, timeout=30)
    
    # raise_for_status() will throw an exception if the request failed (e.g. 401, 404)
    response.raise_for_status()
    
    # Log remaining quota so you know how many calls you have left
    remaining = response.headers.get("x-requests-remaining", "unknown")
    logger.info(f"Odds API requests remaining: {remaining}")
    
    events = response.json()
    logger.info(f"Found {len(events)} upcoming NBA events.")
    return events


def get_event_prop_odds(event_id: str, markets: list[str] = None) -> dict:
    """
    Fetches player prop odds for a single NBA game.
    
    This endpoint DOES cost usage credits: approximately 1 credit per market
    per region requested. Fetching all 6 markets = 6 credits per game.
    
    Args:
        event_id: The Odds API event ID (from get_nba_events())
        markets: List of market keys to fetch. Defaults to PROP_MARKETS.
    
    Returns:
        Dict containing event details and a list of bookmaker odds.
    """
    if markets is None:
        markets = PROP_MARKETS
    
    url = f"{BASE_URL}/sports/{NBA_SPORT_KEY}/events/{event_id}/odds"
    params = {
        "apiKey": get_api_key(),
        "regions": "us",                          # US sportsbooks only
        "markets": ",".join(markets),             # comma-separated market list
        "oddsFormat": "american",                 # -110, +100 format
        "dateFormat": "iso"
    }
    
    logger.info(f"Fetching prop odds for event {event_id}...")
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    
    remaining = response.headers.get("x-requests-remaining", "unknown")
    logger.info(f"Odds API requests remaining: {remaining}")
    
    return response.json()


def parse_prop_odds(event_data: dict) -> list[dict]:
    """
    Parses the raw API response into a flat list of prop line records.
    
    The Odds API returns a nested structure:
    event -> bookmakers[] -> markets[] -> outcomes[]
    
    This function flattens that into a list of dicts, where each dict
    is one sportsbook's line for one player on one prop market.
    
    Returns:
        List of dicts with keys:
        - event_id, home_team, away_team, commence_time
        - bookmaker_key, bookmaker_name
        - market_key (e.g. "player_points")
        - player_name (the player the prop is for)
        - line_value (e.g. 24.5)
        - over_price, under_price (American odds)
        - last_update (timestamp of this line)
    """
    records = []
    
    event_id = event_data.get("id")
    home_team = event_data.get("home_team")
    away_team = event_data.get("away_team")
    commence_time = event_data.get("commence_time")
    
    for bookmaker in event_data.get("bookmakers", []):
        bk_key = bookmaker.get("key")   # e.g. "draftkings"
        bk_name = bookmaker.get("title") # e.g. "DraftKings"
        last_update = bookmaker.get("last_update")
        
        for market in bookmaker.get("markets", []):
            market_key = market.get("key")  # e.g. "player_points"
            
            # The outcomes for prop markets come in pairs (Over/Under)
            # We need to match them by player name
            outcomes = market.get("outcomes", [])
            
            # Group outcomes by player name
            player_lines = {}
            for outcome in outcomes:
                player = outcome.get("description", "")  # player name is in "description"
                side = outcome.get("name", "")           # "Over" or "Under"
                price = outcome.get("price", 0)          # American odds number
                point = outcome.get("point", None)       # The line value (e.g. 24.5)
                
                if player not in player_lines:
                    player_lines[player] = {"over_price": None, "under_price": None, "line_value": point}
                
                if side == "Over":
                    player_lines[player]["over_price"] = price
                    player_lines[player]["line_value"] = point
                elif side == "Under":
                    player_lines[player]["under_price"] = price
            
            # Create one record per player
            for player_name, line_data in player_lines.items():
                if not player_name:
                    continue
                
                records.append({
                    "event_id": event_id,
                    "home_team": home_team,
                    "away_team": away_team,
                    "commence_time": commence_time,
                    "bookmaker_key": bk_key,
                    "bookmaker_name": bk_name,
                    "market_key": market_key,
                    "player_name": player_name,
                    "line_value": line_data.get("line_value"),
                    "over_price": line_data.get("over_price"),
                    "under_price": line_data.get("under_price"),
                    "last_update": last_update
                })
    
    return records


def test_odds_api():
    """
    Quick test — fetches NBA events and prints the first one.
    Does NOT fetch prop odds (saves your credits).
    """
    events = get_nba_events()
    if events:
        print(f"\nFound {len(events)} upcoming NBA games:")
        for event in events[:3]:
            print(f"  {event['away_team']} @ {event['home_team']}")
            print(f"  Start: {event['commence_time']}")
            print(f"  Event ID: {event['id']}\n")
    else:
        print("No upcoming NBA events found (check if it's off-season).")


if __name__ == "__main__":
    test_odds_api()