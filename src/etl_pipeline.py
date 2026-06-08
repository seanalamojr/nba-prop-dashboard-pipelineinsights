import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
from sqlalchemy import create_engine, text
from datetime import datetime, UTC

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# Reuse same DB as initial_load_postgres
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "nba_props",
    "user": "postgres",
    "password": "password",
}

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
TEAMS_CSV_PATH = DATA_DIR / "teams_sample.csv"

# SQLAlchemy engine
engine = create_engine(
    f"postgresql+psycopg2://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
    f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}"
)

def extract_teams_from_csv() -> pd.DataFrame:
    """
    Extract teams from a local CSV file.
    """
    logging.info("Extracting teams from CSV: %s", TEAMS_CSV_PATH)

    df = pd.read_csv(TEAMS_CSV_PATH)
    logging.info("Extracted %d rows from teams CSV", len(df))
    return df

def transform_teams(raw_df: pd.DataFrame) -> pd.DataFrame:
    """
    Transform raw teams data into a cleaned format matching the teams table.
    """
    logging.info("Transforming teams data...")

    df = raw_df.copy()

    # Rename columns from raw CSV to match DB schema
    df = df.rename(
        columns={
            "abbr": "team_abbreviation",
            "name": "team_name",
            "conf": "conference",
            "div": "division",
        }
    )

    # Clean and standardize
    df["team_abbreviation"] = df["team_abbreviation"].str.strip().str.upper()
    df["team_name"] = df["team_name"].str.strip()
    df["conference"] = df["conference"].str.title()
    df["division"] = df["division"].str.title()

    # Derived field: region based on conference (example metric)
    df["region"] = df["conference"].map(
        {
            "Eastern": "East",
            "Western": "West",
        }
    )

    # Loaded-at timestamp
    df["loaded_at"] = datetime.utcnow()

    logging.info("Transformed teams DataFrame shape: %s", df.shape)
    return df

def check_nulls(df: pd.DataFrame, required_cols: list[str], name: str) -> None:
    for col in required_cols:
        n = df[col].isna().sum()
        if n > 0:
            msg = f"{name}: column {col} has {n} nulls"
            logging.error(msg)
            raise ValueError(msg)
    logging.info("%s: null checks passed.", name)

def check_duplicates(df: pd.DataFrame, key_cols: list[str], name: str) -> None:
    dupes = df.duplicated(subset=key_cols).sum()
    if dupes > 0:
        msg = f"{name}: {dupes} duplicate rows based on {key_cols}"
        logging.error(msg)
        raise ValueError(msg)
    logging.info("%s: no duplicate keys.", name)

def validate_domains(df: pd.DataFrame, name: str) -> None:
    """
    Validate allowed values and basic constraints for key columns.
    """
    logging.info("%s: running domain and constraint checks...", name)

    # Check conference values
    allowed_conferences = {"Eastern", "Western"}
    bad_conf = ~df["conference"].isin(allowed_conferences)
    if bad_conf.any():
        invalid_values = df.loc[bad_conf, "conference"].unique()
        msg = f"{name}: invalid conference values found: {list(invalid_values)}"
        logging.error(msg)
        raise ValueError(msg)

    # Check abbreviation length (2-4 characters)
    abbr_len = df["team_abbreviation"].str.len()
    bad_len = ~abbr_len.between(2, 4)
    if bad_len.any():
        bad_rows = df.loc[bad_len, "team_abbreviation"].tolist()
        msg = f"{name}: team_abbreviation length out of range for values: {bad_rows}"
        logging.error(msg)
        raise ValueError(msg)

    logging.info("%s: domain and constraint checks passed.", name)


def load_teams_incremental(df: pd.DataFrame) -> None:
    """
    Incremental load: insert only new teams based on team_abbreviation.
    """
    logging.info("Starting incremental load for teams...")

    with engine.begin() as conn:
        existing = pd.read_sql("SELECT team_abbreviation FROM teams", conn)
        existing_set = set(existing["team_abbreviation"])

        new_df = df[~df["team_abbreviation"].isin(existing_set)]

        if new_df.empty:
            logging.info("No new teams to insert (all %d rows already present).", 
len(df))
            return

        new_df[["team_abbreviation", "team_name", "conference", "division"]].to_sql(
            "teams", conn, if_exists="append", index=False
        )

    logging.info("Inserted %d new team rows.", len(new_df))

def build_analytics_view() -> None:
    """
    Create a simple analytics-ready view for teams.
    """
    logging.info("Creating analytics-ready view vw_dim_teams...")

    query = """
    CREATE OR REPLACE VIEW vw_dim_teams AS
    SELECT
        team_id,
        team_abbreviation,
        team_name,
        conference,
        division
    FROM teams;
    """

    with engine.begin() as conn:
        conn.execute(text(query))

    logging.info("Analytics view vw_dim_teams created.")

def main():
    """
    Orchestrate the full ETL pipeline for teams:
    1) Extract from CSV
    2) Transform and derive metrics
    3) Validate data quality
    4) Incrementally load into Postgres
    5) Build analytics-ready view
    """
    logging.info("Starting ETL pipeline for teams...")

    # 1) Extract
    raw_df = extract_teams_from_csv()

    # 2) Transform
    teams_df = transform_teams(raw_df)

    # 3) Validate
    check_nulls(teams_df, ["team_abbreviation", "team_name"], "teams")
    check_duplicates(teams_df, ["team_abbreviation"], "teams")
    validate_domains(teams_df, "teams")

    # 4) Load (incremental)
    load_teams_incremental(teams_df)

    # 5) Build analytics view
    build_analytics_view()

    logging.info("ETL pipeline completed successfully.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.exception("ETL pipeline failed: %s", e)
        raise