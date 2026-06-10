"""
SQLAlchemy ORM models for PipelineInsights.

Each class below maps to one table in the database. SQLAlchemy reads these
class definitions and knows how to create the corresponding SQL tables, enforce
foreign key relationships, and let you insert/query data using Python objects.

Key concepts used here:
- Column: defines a column in the table
- Integer, String, Float, Boolean, DateTime, Date: column data types
- ForeignKey: links a column to the primary key of another table
- relationship(): lets you navigate related objects in Python (e.g., player.team)
- Index: speeds up queries that filter on a specific column
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Date,
    ForeignKey, Index, Text, create_engine
)
from sqlalchemy.orm import relationship, declarative_base

# Base is the parent class all your model classes will inherit from.
# SQLAlchemy uses it to track all your table definitions.
Base = declarative_base()


# ─────────────────────────────────────────────
# TABLE 1: teams
# Parent table. Every player, game, and odds row links back to a team.
# ─────────────────────────────────────────────
class Team(Base):
    __tablename__ = "teams"

    team_id = Column(Integer, primary_key=True, autoincrement=True)
    team_abbreviation = Column(String(10), unique=True, nullable=False)  # e.g. "BOS"
    team_name = Column(String(100), nullable=False)                      # e.g. "Boston Celtics"
    conference = Column(String(20))                                       # "Eastern" or "Western"
    division = Column(String(50))                                         # e.g. "Atlantic"

    # These relationship() calls let you write player.team and get the Team object.
    # They don't create database columns — they're Python-only navigation helpers.
    players = relationship("Player", back_populates="team", foreign_keys="Player.team_id")
    home_games = relationship("Game", back_populates="home_team", foreign_keys="Game.home_team_id")
    away_games = relationship("Game", back_populates="away_team", foreign_keys="Game.away_team_id")

    def __repr__(self):
        return f"<Team {self.team_abbreviation}>"


# ─────────────────────────────────────────────
# TABLE 2: players
# Stores one row per NBA player. Links to teams.
# ─────────────────────────────────────────────
class Player(Base):
    __tablename__ = "players"

    player_id = Column(Integer, primary_key=True, autoincrement=True)
    external_ref = Column(String(100), unique=True)  # The player's ID from BallDontLie
    full_name = Column(String(100), nullable=False)
    first_name = Column(String(50))
    last_name = Column(String(50))
    position = Column(String(10))                    # "G", "F", "C", "G-F", etc.
    team_id = Column(Integer, ForeignKey("teams.team_id"))
    is_active = Column(Boolean, default=True)

    # Relationships
    team = relationship("Team", back_populates="players", foreign_keys=[team_id])
    game_stats = relationship("PlayerGameStat", back_populates="player")
    injuries = relationship("PlayerInjury", back_populates="player")
    odds = relationship("Odd", back_populates="player")
    predictions = relationship("PlayerPropPrediction", back_populates="player")

    # Index on last_name speeds up name-based searches
    __table_args__ = (Index("ix_players_last_name", "last_name"),)

    def __repr__(self):
        return f"<Player {self.full_name}>"


# ─────────────────────────────────────────────
# TABLE 3: games
# One row per NBA game. Links to teams (home and away).
# ─────────────────────────────────────────────
class Game(Base):
    __tablename__ = "games"

    game_id = Column(Integer, primary_key=True, autoincrement=True)
    external_ref = Column(String(100), unique=True)  # The game's ID from BallDontLie
    season = Column(Integer)                         # e.g. 2024
    game_date = Column(Date)
    start_time_utc = Column(DateTime)
    home_team_id = Column(Integer, ForeignKey("teams.team_id"))
    away_team_id = Column(Integer, ForeignKey("teams.team_id"))
    venue = Column(String(100))
    status = Column(String(20))  # "Scheduled", "InProgress", "Final"

    # Relationships — note how we specify foreign_keys because there are TWO
    # foreign keys pointing to teams from this table
    home_team = relationship("Team", back_populates="home_games", foreign_keys=[home_team_id])
    away_team = relationship("Team", back_populates="away_games", foreign_keys=[away_team_id])
    player_stats = relationship("PlayerGameStat", back_populates="game")
    injuries = relationship("PlayerInjury", back_populates="game")
    odds = relationship("Odd", back_populates="game")
    predictions = relationship("PlayerPropPrediction", back_populates="game")

    # Index on game_date speeds up "tonight's games" dashboard queries
    __table_args__ = (Index("ix_games_game_date", "game_date"),)

    def __repr__(self):
        return f"<Game {self.game_date} {self.external_ref}>"


# ─────────────────────────────────────────────
# TABLE 4: sportsbooks
# Reference table — one row per sportsbook (DraftKings, FanDuel, etc.)
# ─────────────────────────────────────────────
class Sportsbook(Base):
    __tablename__ = "sportsbooks"

    sportsbook_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)   # "DraftKings"
    code = Column(String(50), unique=True)        # "draftkings" (from The Odds API)
    country = Column(String(50))                  # "US"

    odds = relationship("Odd", back_populates="sportsbook")

    def __repr__(self):
        return f"<Sportsbook {self.name}>"


# ─────────────────────────────────────────────
# TABLE 5: prop_types
# Reference table — one row per stat category we track (points, rebounds, etc.)
# ─────────────────────────────────────────────
class PropType(Base):
    __tablename__ = "prop_types"

    prop_type_id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), unique=True, nullable=False)  # "POINTS", "REBOUNDS"
    description = Column(String(255))                        # "Player Points"
    unit = Column(String(50))                                # "points", "rebounds"

    odds = relationship("Odd", back_populates="prop_type")
    predictions = relationship("PlayerPropPrediction", back_populates="prop_type")

    def __repr__(self):
        return f"<PropType {self.code}>"


# ─────────────────────────────────────────────
# TABLE 6: player_injuries
# Stores injury reports. Used to add context to predictions.
# ─────────────────────────────────────────────
class PlayerInjury(Base):
    __tablename__ = "player_injuries"

    injury_id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Integer, ForeignKey("players.player_id"), nullable=False)
    report_date = Column(Date, nullable=False)
    game_id = Column(Integer, ForeignKey("games.game_id"), nullable=True)  # nullable: injury may not be game-specific
    status = Column(String(50))       # "Out", "Questionable", "Probable", "Day-To-Day"
    description = Column(String(255)) # "Left knee soreness"
    source = Column(String(100))      # "BallDontLie"

    player = relationship("Player", back_populates="injuries")
    game = relationship("Game", back_populates="injuries")

    def __repr__(self):
        return f"<PlayerInjury {self.player_id} {self.status}>"


# ─────────────────────────────────────────────
# TABLE 7: player_game_stats
# One row per player per game — the historical stats used for predictions.
# ─────────────────────────────────────────────
class PlayerGameStat(Base):
    __tablename__ = "player_game_stats"

    player_game_id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Integer, ForeignKey("players.player_id"), nullable=False)
    game_id = Column(Integer, ForeignKey("games.game_id"), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.team_id"), nullable=False)
    minutes_played = Column(Float)
    points = Column(Integer)
    rebounds = Column(Integer)
    assists = Column(Integer)
    steals = Column(Integer)
    blocks = Column(Integer)
    turnovers = Column(Integer)
    field_goal_attempts = Column(Integer)
    field_goals_made = Column(Integer)
    three_pt_attempts = Column(Integer)
    three_pt_made = Column(Integer)
    free_throw_attempts = Column(Integer)
    free_throws_made = Column(Integer)

    player = relationship("Player", back_populates="game_stats")
    game = relationship("Game", back_populates="player_stats")

    # Unique constraint: a player can only have one stat row per game
    __table_args__ = (
        Index("ix_pgs_player_game", "player_id", "game_id", unique=True),
    )

    def __repr__(self):
        return f"<PlayerGameStat player={self.player_id} game={self.game_id}>"


# ─────────────────────────────────────────────
# TABLE 8: odds
# The central table — one row per sportsbook prop line.
# This is what you're comparing across sportsbooks.
# ─────────────────────────────────────────────
class Odd(Base):
    __tablename__ = "odds"

    odds_id = Column(Integer, primary_key=True, autoincrement=True)
    sportsbook_id = Column(Integer, ForeignKey("sportsbooks.sportsbook_id"), nullable=False)
    game_id = Column(Integer, ForeignKey("games.game_id"), nullable=True)   # nullable: game may not be in DB yet
    player_id = Column(Integer, ForeignKey("players.player_id"), nullable=True)
    prop_type_id = Column(Integer, ForeignKey("prop_types.prop_type_id"), nullable=True)
    market_name = Column(String(100))   # Raw name from API, e.g. "player_points"
    line_value = Column(Float)          # The prop line, e.g. 24.5
    over_price = Column(Float)          # American odds for the over, e.g. -110
    under_price = Column(Float)         # American odds for the under, e.g. -110
    odds_timestamp = Column(DateTime, default=datetime.utcnow)
    is_live = Column(Boolean, default=False)
    data_source = Column(String(50))    # "TheOddsAPI"

    sportsbook = relationship("Sportsbook", back_populates="odds")
    game = relationship("Game", back_populates="odds")
    player = relationship("Player", back_populates="odds")
    prop_type = relationship("PropType", back_populates="odds")

    __table_args__ = (
        Index("ix_odds_player_game", "player_id", "game_id", "prop_type_id"),
    )

    def __repr__(self):
        return f"<Odd player={self.player_id} line={self.line_value}>"


# ─────────────────────────────────────────────
# TABLE 9: player_prop_predictions
# Stores model output — one row per player/game/prop prediction.
# ─────────────────────────────────────────────
class PlayerPropPrediction(Base):
    __tablename__ = "player_prop_predictions"

    prediction_id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Integer, ForeignKey("players.player_id"), nullable=False)
    game_id = Column(Integer, ForeignKey("games.game_id"), nullable=False)
    prop_type_id = Column(Integer, ForeignKey("prop_types.prop_type_id"), nullable=False)
    model_version = Column(String(50))    # e.g. "rolling_avg_v1"
    prediction_timestamp = Column(DateTime, default=datetime.utcnow)
    projected_value = Column(Float)       # Model's predicted stat value
    lower_ci = Column(Float)              # Lower confidence interval bound
    upper_ci = Column(Float)              # Upper confidence interval bound
    input_window_games = Column(Integer)  # How many recent games were used
    notes = Column(Text)                  # Any context notes

    player = relationship("Player", back_populates="predictions")
    game = relationship("Game", back_populates="predictions")
    prop_type = relationship("PropType", back_populates="predictions")

    def __repr__(self):
        return f"<Prediction player={self.player_id} projected={self.projected_value}>"


# ─────────────────────────────────────────────
# TABLE 10: refresh_runs
# Pipeline audit log — records every time a data refresh runs.
# ─────────────────────────────────────────────
class RefreshRun(Base):
    __tablename__ = "refresh_runs"

    run_id = Column(Integer, primary_key=True, autoincrement=True)
    run_timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    source_system = Column(String(50))    # "TheOddsAPI", "BallDontLie", "Predictions"
    status = Column(String(20))           # "Success", "Failed", "Partial"
    records_loaded = Column(Integer, default=0)
    error_message = Column(Text)

    def __repr__(self):
        return f"<RefreshRun {self.source_system} {self.status}>"