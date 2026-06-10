"""
Stats API client for PipelineInsights.

This module fetches:
1. NBA players list — using BallDontLie (free tier)
2. NBA game schedule — using BallDontLie (free tier)
3. Player game stats — using nba_api (completely free, pulls from NBA.com)

Why two different APIs?
- BallDontLie has a clean REST API and is good for players and schedules.
- nba_api is a Python package that wraps the official NBA stats website.
  It's 100% free and has the most complete historical game stats data.
  The trade-off: it can be slower and occasionally requires rate limiting.
"""

import os
import time
import requests
import logging
import pandas as pd
from datetime import datetime, date
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# BallDontLie client (players + schedule)
# ─────────────────────────────────────────────

BDL_BASE_URL = "https://api.balldontlie.io"


def get_bdl_headers() -> dict:
    """Returns the authentication headers for BallDontLie."""
    key = os.getenv("BALLDONTLIE_API_KEY")
    if not key:
        raise ValueError(
            "BALLDONTLIE_API_KEY not found. Make sure it's set in your .env file."
        )
    return {"Authorization": key}


def get_all_players(season: int = 2024) -> list[dict]:
    """
    Fetches all active NBA players from BallDontLie.
    
    BallDontLie uses pagination — results come in pages (default 25 per page).
    We loop through all pages until there are no more results.
    
    Args:
        season: NBA season year (2024 = 2024-25 season)
    
    Returns:
        List of player dicts.
    """
    logger.info("Fetching all NBA players from BallDontLie...")
    
    all_players = []
    page = 1
    per_page = 100  # Max allowed by BallDontLie
    
    while True:
        response = requests.get(
            f"{BDL_BASE_URL}/nba/v1/players",
            headers=get_bdl_headers(),
            params={
                "per_page": per_page,
                "page": page,
            },
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        
        players = data.get("data", [])
        if not players:
            break
        
        all_players.extend(players)
        logger.info(f"  Fetched page {page} — {len(players)} players (total: {len(all_players)})")
        
        # BallDontLie free tier: 5 requests/minute. Wait between pages.
        time.sleep(0.5)
        
        # Check if there are more pages
        meta = data.get("meta", {})
        if page >= meta.get("total_pages", 1):
            break
        page += 1
    
    logger.info(f"Total players fetched: {len(all_players)}")
    return all_players


def get_games_for_date_range(start_date: str, end_date: str) -> list[dict]:
    """
    Fetches NBA games within a date range from BallDontLie.
    
    Args:
        start_date: "YYYY-MM-DD" format
        end_date: "YYYY-MM-DD" format
    
    Returns:
        List of game dicts.
    """
    logger.info(f"Fetching games from {start_date} to {end_date}...")
    
    all_games = []
    page = 1
    
    while True:
        response = requests.get(
            f"{BDL_BASE_URL}/nba/v1/games",
            headers=get_bdl_headers(),
            params={
                "start_date": start_date,
                "end_date": end_date,
                "per_page": 100,
                "page": page,
            },
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        
        games = data.get("data", [])
        if not games:
            break
        
        all_games.extend(games)
        time.sleep(0.5)
        
        meta = data.get("meta", {})
        if page >= meta.get("total_pages", 1):
            break
        page += 1
    
    logger.info(f"Total games fetched: {len(all_games)}")
    return all_games


# ─────────────────────────────────────────────
# nba_api client (player game stats)
# ─────────────────────────────────────────────

def get_player_game_log(player_id: str, season: str = "2024-25") -> pd.DataFrame:
    """
    Fetches a player's game-by-game stats for the given season using nba_api.
    
    nba_api pulls from stats.nba.com — completely free, no API key required.
    The package maps the complex NBA.com API into easy Python function calls.
    
    Args:
        player_id: NBA player ID (different from BallDontLie ID — this is the 
                   official NBA ID, e.g. LeBron James = "2544")
        season: Season string, e.g. "2024-25"
    
    Returns:
        Pandas DataFrame with one row per game, columns including:
        GAME_ID, GAME_DATE, MATCHUP, WL, MIN, PTS, REB, AST, STL, BLK, TOV,
        FGA, FGM, FG3A, FG3M, FTA, FTM
    """
    from nba_api.stats.endpoints import playergamelog
    
    logger.info(f"Fetching game log for player {player_id} ({season})...")
    
    # Small delay to respect NBA.com rate limits
    time.sleep(0.6)
    
    game_log = playergamelog.PlayerGameLog(
        player_id=player_id,
        season=season,
        timeout=60
    )
    
    df = game_log.get_data_frames()[0]
    logger.info(f"  Got {len(df)} game log rows for player {player_id}")
    return df


def get_all_active_player_ids_from_nba_api() -> list[dict]:
    """
    Gets all active players and their NBA IDs using nba_api's static data.
    
    nba_api includes a static players list — this is much faster than
    making API calls because the data is bundled with the package.
    The static list includes: id, full_name, first_name, last_name, is_active
    
    Returns:
        List of dicts with 'id', 'full_name', 'first_name', 'last_name', 'is_active'
    """
    from nba_api.stats.static import players as nba_players
    
    all_players = nba_players.get_active_players()
    logger.info(f"Found {len(all_players)} active players from nba_api static data.")
    return all_players


def test_stats_api():
    """Quick test — fetches today's games and prints them."""
    today = date.today().isoformat()
    games = get_games_for_date_range(today, today)
    
    if games:
        print(f"\nGames for {today}:")
        for game in games:
            away = game["visitor_team"]["abbreviation"]
            home = game["home_team"]["abbreviation"]
            print(f"  {away} @ {home} — Status: {game['status']}")
    else:
        print(f"No games found for {today}.")
    
    # Test nba_api static data
    players = get_all_active_player_ids_from_nba_api()
    print(f"\nnba_api found {len(players)} active players.")
    print(f"Example: {players[0]}")


if __name__ == "__main__":
    test_stats_api()