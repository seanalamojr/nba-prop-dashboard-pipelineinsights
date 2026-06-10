"""
ETL pipeline for NBA Teams data.

ETL stands for Extract, Transform, Load — a standard pattern for data pipelines:
  - Extract: read raw data from a source (here: a CSV file)
  - Transform: clean, validate, and reshape the data
  - Load: write the cleaned data into the database

This pipeline:
1. Reads teams_all.csv
2. Validates required columns exist
3. Cleans and normalizes the data
4. Loads into the teams table (incrementally — won't duplicate rows)

Usage:
    python src/etl_pipeline.py
"""

import pandas as pd
import logging
from sqlalchemy.orm import Session
from src.db.connection import get_engine
from src.db.models import Team, RefreshRun
from datetime import datetime

# Set up basic logging so you can see what the pipeline is doing
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# Path to the teams data file
TEAMS_CSV_PATH = "data/teams_all.csv"


# ─────────────────────────────────────────────
# STEP 1: EXTRACT
# ─────────────────────────────────────────────
def extract_teams(csv_path: str) -> pd.DataFrame:
    """
    Reads the teams CSV file into a pandas DataFrame.
    
    A DataFrame is like a spreadsheet in Python — rows and columns
    that you can filter, clean, and transform with simple method calls.
    """
    logger.info(f"Extracting teams data from: {csv_path}")
    df = pd.read_csv(csv_path)
    logger.info(f"Extracted {len(df)} rows from CSV.")
    return df


# ─────────────────────────────────────────────
# STEP 2: TRANSFORM
# ─────────────────────────────────────────────
def transform_teams(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans and validates the raw CSV data.
    
    Transformations applied:
    - Strip whitespace from string columns
    - Standardize abbreviations to uppercase
    - Drop rows with missing required fields
    - Ensure column names match what the database expects
    """
    logger.info("Transforming teams data...")
    
    # Check required columns exist
    required_cols = ["team_abbreviation", "team_name", "conference", "division"]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")
    
    # Strip whitespace from all string columns
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].str.strip()
    
    # Ensure abbreviations are uppercase (BOS, not bos)
    df["team_abbreviation"] = df["team_abbreviation"].str.upper()
    
    # Drop any rows where team_abbreviation or team_name is missing
    before = len(df)
    df = df.dropna(subset=["team_abbreviation", "team_name"])
    after = len(df)
    if before != after:
        logger.warning(f"Dropped {before - after} rows with missing required fields.")
    
    logger.info(f"Transform complete. {len(df)} clean rows ready.")
    return df


# ─────────────────────────────────────────────
# STEP 3: LOAD
# ─────────────────────────────────────────────
def load_teams(df: pd.DataFrame, session: Session) -> int:
    """
    Loads transformed team data into the database.
    
    This is an INCREMENTAL load — it checks if each team already exists
    (by team_abbreviation) before inserting. If the team exists, it updates
    the record. If not, it inserts a new row. This pattern is called
    "upsert" (update + insert).
    
    Returns the number of records loaded.
    """
    logger.info("Loading teams into database...")
    records_loaded = 0
    
    for _, row in df.iterrows():
        # Check if team already exists
        existing = session.query(Team).filter_by(
            team_abbreviation=row["team_abbreviation"]
        ).first()
        
        if existing:
            # Update the existing record
            existing.team_name = row["team_name"]
            existing.conference = row["conference"]
            existing.division = row["division"]
        else:
            # Insert a new record
            new_team = Team(
                team_abbreviation=row["team_abbreviation"],
                team_name=row["team_name"],
                conference=row["conference"],
                division=row["division"]
            )
            session.add(new_team)
            records_loaded += 1
    
    session.commit()
    logger.info(f"Load complete. {records_loaded} new teams inserted.")
    return records_loaded


def run_teams_etl():
    """
    Runs the full teams ETL pipeline and records the result in refresh_runs.
    """
    engine = get_engine()
    status = "Success"
    records_loaded = 0
    error_message = None
    
    try:
        # Run the three ETL steps
        df_raw = extract_teams(TEAMS_CSV_PATH)
        df_clean = transform_teams(df_raw)
        
        with Session(engine) as session:
            records_loaded = load_teams(df_clean, session)
            
            # Log this run to refresh_runs
            run_log = RefreshRun(
                run_timestamp=datetime.utcnow(),
                source_system="TeamsCSV",
                status=status,
                records_loaded=records_loaded
            )
            session.add(run_log)
            session.commit()
        
        logger.info(f"✅ Teams ETL complete. {records_loaded} new records loaded.")
    
    except Exception as e:
        status = "Failed"
        error_message = str(e)
        logger.error(f"❌ Teams ETL failed: {error_message}")
        
        # Still log the failed run
        with Session(engine) as session:
            run_log = RefreshRun(
                run_timestamp=datetime.utcnow(),
                source_system="TeamsCSV",
                status=status,
                records_loaded=0,
                error_message=error_message
            )
            session.add(run_log)
            session.commit()
        
        raise


if __name__ == "__main__":
    run_teams_etl()