"""
Database connection utility for PipelineInsights.

This module creates a SQLAlchemy engine that connects to the SQLite database.
The engine is the single entry point for all database operations in the project.

SQLAlchemy uses a "connection string" (also called a URL) to know which database
to connect to. For SQLite, the format is:
    sqlite:///relative/path/to/file.db

The three slashes mean "relative path from where you run the script."
"""

import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# load_dotenv() reads your .env file and puts the values into environment variables
load_dotenv()


def get_engine():
    """
    Creates and returns a SQLAlchemy engine connected to the SQLite database.
    
    Returns:
        sqlalchemy.engine.Engine: The database engine object.
    """
    # Read the database URL from your .env file
    # Falls back to a default path if DATABASE_URL is not set
    database_url = os.getenv("DATABASE_URL", "sqlite:///data/pipelineinsights.db")
    
    # create_engine() sets up the connection but doesn't open it yet
    # connect_args={"check_same_thread": False} is required for SQLite when
    # the app might access the database from multiple threads (like Dash callbacks)
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},
        echo=False  # Set to True if you want to see every SQL query in your terminal
    )
    return engine


def test_connection():
    """
    Quick smoke test to verify the database connection is working.
    Prints a success message if everything is fine.
    """
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        print("✅ Database connection successful!")
        print(f"   Connected to: {engine.url}")


if __name__ == "__main__":
    test_connection()