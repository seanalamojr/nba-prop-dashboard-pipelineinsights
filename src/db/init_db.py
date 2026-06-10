"""
Database initialization script for PipelineInsights.

Run this script once to create all tables and seed reference data.
It is safe to run multiple times — it will NOT drop existing tables.

Usage:
    python src/db/init_db.py
"""

from src.db.connection import get_engine
from src.db.models import Base, Sportsbook, PropType
from sqlalchemy.orm import Session


def create_all_tables(engine):
    """
    Creates all tables defined in models.py if they don't already exist.
    checkfirst=True means: skip if the table already exists.
    """
    Base.metadata.create_all(engine, checkfirst=True)
    print("✅ All 10 tables created (or already existed).")


def seed_sportsbooks(session):
    """
    Seeds the sportsbooks table with the major US sportsbooks
    that The Odds API returns data for.
    
    The 'code' field must match exactly what The Odds API uses
    as its bookmaker key — this is how we'll link API responses
    to sportsbook rows.
    """
    sportsbooks = [
        {"name": "DraftKings", "code": "draftkings", "country": "US"},
        {"name": "FanDuel", "code": "fanduel", "country": "US"},
        {"name": "BetMGM", "code": "betmgm", "country": "US"},
        {"name": "Caesars", "code": "williamhill_us", "country": "US"},
        {"name": "PointsBet", "code": "pointsbetus", "country": "US"},
        {"name": "BetRivers", "code": "betrivers", "country": "US"},
    ]
    
    added = 0
    for sb_data in sportsbooks:
        # Check if this sportsbook already exists (avoid duplicates)
        existing = session.query(Sportsbook).filter_by(code=sb_data["code"]).first()
        if not existing:
            session.add(Sportsbook(**sb_data))
            added += 1
    
    session.commit()
    print(f"✅ Sportsbooks seeded: {added} new rows added.")


def seed_prop_types(session):
    """
    Seeds the prop_types table with the NBA prop categories we track.
    The 'code' must match what we use in our prediction model — it's our
    internal identifier for each prop category.
    """
    prop_types = [
        {"code": "POINTS", "description": "Player Points", "unit": "points"},
        {"code": "REBOUNDS", "description": "Player Rebounds", "unit": "rebounds"},
        {"code": "ASSISTS", "description": "Player Assists", "unit": "assists"},
        {"code": "STEALS", "description": "Player Steals", "unit": "steals"},
        {"code": "BLOCKS", "description": "Player Blocks", "unit": "blocks"},
        {"code": "TURNOVERS", "description": "Player Turnovers", "unit": "turnovers"},
        {"code": "THREE_PT", "description": "Three Pointers Made", "unit": "threes"},
        {"code": "PRA", "description": "Points + Rebounds + Assists", "unit": "combined"},
    ]
    
    added = 0
    for pt_data in prop_types:
        existing = session.query(PropType).filter_by(code=pt_data["code"]).first()
        if not existing:
            session.add(PropType(**pt_data))
            added += 1
    
    session.commit()
    print(f"✅ Prop types seeded: {added} new rows added.")


def main():
    print("🏀 Initializing PipelineInsights database...\n")
    
    engine = get_engine()
    create_all_tables(engine)
    
    with Session(engine) as session:
        seed_sportsbooks(session)
        seed_prop_types(session)
    
    print("\n🎉 Database initialization complete!")
    print("   Database file: data/pipelineinsights.db")


if __name__ == "__main__":
    main()