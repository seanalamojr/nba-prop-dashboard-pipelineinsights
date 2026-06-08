import sqlite3
from pathlib import Path

# Use a DB file in the SAME folder as this script
db_path = Path(__file__).parent / "nba_props.db"
print("Using db_path:", db_path)

# Try to connect and create a tiny table
conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.execute("CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY, name TEXT);")
cur.execute("INSERT INTO test_table (name) VALUES (?);", ("hello",))
conn.commit()

cur.execute("SELECT id, name FROM test_table;")
rows = cur.fetchall()
print("Rows in test_table:", rows)

conn.close()
print("SQLite built-in test completed successfully.")