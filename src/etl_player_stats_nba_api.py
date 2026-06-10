import logging
from datetime import datetime

from sqlalchemy.orm import Session

from nba_api.stats.endpoints import playergamelog
from nba_api.stats.static import players as nba_players

from src.db.connection import get_engine
from src.db.models import Player, Game, PlayerGameStat, RefreshRun

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

SEASON = "2023-24"  # adjust season string as needed


def get_nba_player_id_map() -> dict:
    """
    Build a mapping full_name.lower() -> nba_api player ID.
    """
    all_players = nba_players.get_active_players()
    return {p["full_name"].lower(): p["id"] for p in all_players}


def load_player_stats_from_nba_api(max_players: int | None = 10) -> None:
    """
    Pull game logs for active players via nba_api and load into PlayerGameStat.

    max_players: limit number of players for testing.
    """
    engine = get_engine()
    nba_id_map = get_nba_player_id_map()
    records_loaded = 0

    with Session(engine) as session:
        # Map our Player rows to nba_api IDs by name
        db_players = session.query(Player).all()
        matched_players: list[tuple[Player, int]] = []
        for p in db_players:
            nba_id = nba_id_map.get(p.full_name.lower())
            if nba_id:
                matched_players.append((p, nba_id))
        logger.info("Matched %d players to nba_api IDs", len(matched_players))

        if max_players:
            matched_players = matched_players[:max_players]
            logger.info("Limiting to %d players for testing", len(matched_players))

        for db_player, nba_id in matched_players:
            logger.info(
                "Fetching game logs for %s (nba_id=%s)",
                db_player.full_name,
                nba_id,
            )

            # If player has no team_id yet, skip to avoid NOT NULL errors
            if db_player.team_id is None:
                logger.warning(
                    "Skipping %s because team_id is None in Player table",
                    db_player.full_name,
                )
                continue

            # Call nba_api for this player's game logs
            gl = playergamelog.PlayerGameLog(player_id=nba_id, season=SEASON)
            df = gl.get_data_frames()[0]
            logger.info("  Retrieved %d game logs", len(df))

            for _, row in df.iterrows():
                # Columns from PlayerGameLog per your screenshot:
                # 'Game_ID', 'GAME_DATE', 'MATCHUP', 'MIN', 'PTS', 'REB',
                # 'AST', 'STL', 'BLK', 'TOV', 'FGM', 'FGA', 'FG3M', 'FG3A',
                # 'FTM', 'FTA', etc.
                game_date_str = row["GAME_DATE"]  # e.g. "Apr 14, 2024"
                matchup = row["MATCHUP"]          # e.g. "NYK vs. CHI"

                # Basic box score stats
                points = int(row.get("PTS", 0) or 0)
                rebounds = int(row.get("REB", 0) or 0)
                assists = int(row.get("AST", 0) or 0)
                steals = int(row.get("STL", 0) or 0)
                blocks = int(row.get("BLK", 0) or 0)
                turnovers = int(row.get("TOV", 0) or 0)

                minutes = row.get("MIN", 0)
                # MIN sometimes comes as a string; coerce to float safely
                try:
                    minutes_played = float(minutes or 0)
                except (TypeError, ValueError):
                    minutes_played = 0.0

                fgm = int(row.get("FGM", 0) or 0)
                fga = int(row.get("FGA", 0) or 0)
                fg3m = int(row.get("FG3M", 0) or 0)
                fg3a = int(row.get("FG3A", 0) or 0)
                ftm = int(row.get("FTM", 0) or 0)
                fta = int(row.get("FTA", 0) or 0)

                # Parse game date
                game_date = datetime.strptime(game_date_str, "%b %d, %Y")

                # Simple game match: by date only (can be improved later)
                game = (
                    session.query(Game)
                    .filter(Game.game_date == game_date)
                    .first()
                )
                if not game:
                    # Create a minimal game row tied to the player's team
                    game = Game(
                        home_team_id=db_player.team_id,
                        away_team_id=db_player.team_id,
                        game_date=game_date,
                        status="Final",
                    )
                    session.add(game)
                    session.flush()

                # Skip if stats already exist for this (player, game)
                existing = session.query(PlayerGameStat).filter_by(
                    player_id=db_player.player_id,
                    game_id=game.game_id,
                ).first()
                if existing:
                    continue

                stat = PlayerGameStat(
                    player_id=db_player.player_id,
                    game_id=game.game_id,
                    team_id=db_player.team_id,
                    minutes_played=minutes_played,
                    points=points,
                    rebounds=rebounds,
                    assists=assists,
                    steals=steals,
                    blocks=blocks,
                    turnovers=turnovers,
                    field_goal_attempts=fga,
                    field_goals_made=fgm,
                    three_pt_attempts=fg3a,
                    three_pt_made=fg3m,
                    free_throw_attempts=fta,
                    free_throws_made=ftm,
                )
                session.add(stat)
                records_loaded += 1

        session.commit()

        session.add(
            RefreshRun(
                run_timestamp=datetime.utcnow(),
                source_system="nba_api",
                status="Success",
                records_loaded=records_loaded,
            )
        )
        session.commit()

    logger.info(
        "Loaded %d player game stat rows from nba_api.", records_loaded
    )


if __name__ == "__main__":
    load_player_stats_from_nba_api(max_players=10)