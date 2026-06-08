from sqlalchemy import create_engine, text

# SQLite database file in the SAME folder as this script
DATABASE_URL = "sqlite:///nba_props.db"

print("Using DATABASE_URL:", DATABASE_URL)

engine = create_engine(DATABASE_URL, echo=False, future=True)


def get_connection():
    return engine.connect()


def test_connection():
    with get_connection() as conn:
        result = conn.execute(text("SELECT 1"))
        for row in result:
            print("Test query result:", row[0])


if __name__ == "__main__":
    test_connection()