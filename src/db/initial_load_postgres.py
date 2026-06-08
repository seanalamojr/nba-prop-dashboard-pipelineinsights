import psycopg2

# Connection settings for PostgreSQL
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "nba_props",
    "user": "postgres",
    "password": "password",  # TODO: replace with your real password
}


def get_connection():
    """
    Open a connection to the PostgreSQL database.
    """
    return psycopg2.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        dbname=DB_CONFIG["dbname"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
    )


def create_tables():
    """
    Create a few core tables that match the schema document.
    """
    create_teams = """
    CREATE TABLE IF NOT EXISTS teams (
        team_id           SERIAL PRIMARY KEY,
        team_abbreviation VARCHAR(10),
        team_name         VARCHAR(100),
        conference        VARCHAR(20),
        division          VARCHAR(50)
    );
    """

    create_sportsbooks = """
    CREATE TABLE IF NOT EXISTS sportsbooks (
        sportsbook_id SERIAL PRIMARY KEY,
        name          VARCHAR(100),
        code          VARCHAR(50),
        country       VARCHAR(50)
    );
    """

    create_prop_types = """
    CREATE TABLE IF NOT EXISTS prop_types (
        prop_type_id SERIAL PRIMARY KEY,
        code         VARCHAR(50),
        description  VARCHAR(255),
        unit         VARCHAR(50)
    );
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(create_teams)
            cur.execute(create_sportsbooks)
            cur.execute(create_prop_types)
        conn.commit()

    print("Core tables created (teams, sportsbooks, prop_types).")


def load_sample_data():
    """
    Insert sample rows to demonstrate the loading workflow.
    """
    teams_rows = [
        ("BOS", "Boston Celtics", "Eastern", "Atlantic"),
        ("LAL", "Los Angeles Lakers", "Western", "Pacific"),
    ]

    sportsbooks_rows = [
        ("DraftKings", "DK", "US"),
        ("FanDuel", "FD", "US"),
    ]

    prop_types_rows = [
        ("POINTS", "Total points scored", "points"),
        ("ASSISTS", "Total assists recorded", "assists"),
    ]

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO teams (team_abbreviation, team_name, conference, division)
                VALUES (%s, %s, %s, %s);
                """,
                teams_rows,
            )

            cur.executemany(
                """
                INSERT INTO sportsbooks (name, code, country)
                VALUES (%s, %s, %s);
                """,
                sportsbooks_rows,
            )

            cur.executemany(
                """
                INSERT INTO prop_types (code, description, unit)
                VALUES (%s, %s, %s);
                """,
                prop_types_rows,
            )

        conn.commit()

    print("Sample data loaded into teams, sportsbooks, prop_types.")


if __name__ == "__main__":
    create_tables()
    load_sample_data()