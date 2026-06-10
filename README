# PipelineInsights — NBA Player Prop Comparison & Prediction Dashboard

**Developer:** Sean Alamo  
**Course:** Data Engineering  
**Stack:** Python · SQLite · Dash · Plotly · nba_api · The Odds API · APScheduler

---

## Overview

PipelineInsights is an end-to-end data engineering application that aggregates NBA player prop betting lines from multiple sportsbooks, stores them alongside historical player statistics, and generates transparent statistical projections — all presented in a live-updating interactive dashboard.

The core problem this solves: sportsbook prop lines are not standardized across platforms. A bettor checking DraftKings, FanDuel, and BetMGM for the same player market sees different numbers with no easy comparison or statistical reference point. PipelineInsights centralizes that data, adds a rolling-average projection model, and highlights where a posted line diverges from recent statistical expectations.

---

## Features

| Feature | Description |
|---|---|
| Live Odds Ingestion | Pulls player prop lines from The Odds API across DraftKings, FanDuel, BetMGM |
| Player Stats ETL | Fetches historical game logs via `nba_api` for all active NBA players |
| Prediction Engine | Rolling-average framework (last 10 games) with home/away split adjustments and confidence intervals |
| 4-Page Dash Dashboard | Overview · Prop Lines · Player Trends · Predictions |
| Automated Scheduler | APScheduler refreshes odds every 60 minutes, full pipeline daily at 8 AM |
| Audit Logging | Every pipeline run logged to `refresh_runs` table and `logs/pipelineinsights.log` |
| Data Validation | Null checks, duplicate checks, and domain validation on all ETL inputs |

---

## Project Structure

```
nba-prop-dashboard-pipelineinsights/
│
├── app.py                      # Dash application entry point — starts dashboard + scheduler
│
├── data/
│   ├── teams_all.csv           # All 30 NBA teams with conference and division
│   └── teams_sample.csv        # Original 2-row sample (BOS, LAL)
│
├── src/
│   ├── __init__.py
│   ├── etl_pipeline.py         # Teams ETL: extract → transform → validate → load
│   ├── etl_players.py          # Players ETL: pulls active roster from nba_api
│   ├── etl_games.py            # Games ETL: pulls schedule and game metadata
│   ├── etl_player_stats.py     # Player game stats ETL: historical box scores via nba_api
│   ├── etl_odds.py             # Odds ETL: live prop lines from The Odds API
│   ├── predictions.py          # Rolling-average prediction engine
│   ├── run_pipeline.py         # Master pipeline runner (runs all ETLs in sequence)
│   ├── scheduler.py            # APScheduler configuration for automated refresh
│   └── db/
│       ├── __init__.py
│       ├── connection.py       # SQLAlchemy engine and SessionLocal factory
│       ├── models.py           # ORM models for all 10 database tables
│       ├── init_db.py          # Creates all tables and seeds reference data
│       └── initial_load_postgres.py  # Original Postgres loader (legacy reference)
│
├── docs/
│   ├── Alamo_Project_Proposal_PipelineInsights.docx
│   └── alamo_database_schema_report.docx
│
├── logs/
│   └── pipelineinsights.log    # Runtime log file (auto-created on first run)
│
├── requirements.txt
├── .env.example                # Template for environment variables
├── .gitignore
└── README.md
```

---

## Database Schema

PipelineInsights uses a **normalized SQLite database** (`nba_props.db`) with 10 tables. The design separates reference entities from transactional data and uses foreign keys to enforce relationships.

### Tables

| Table | Purpose | Key Columns |
|---|---|---|
| `teams` | One row per NBA franchise | `team_id`, `team_abbreviation`, `team_name`, `conference`, `division` |
| `players` | Active player roster | `player_id`, `external_ref`, `full_name`, `position`, `team_id` |
| `games` | Game schedule and results | `game_id`, `external_ref`, `game_date`, `home_team_id`, `away_team_id`, `status` |
| `sportsbooks` | Sportsbook reference | `sportsbook_id`, `name`, `code` |
| `prop_types` | Prop category definitions | `prop_type_id`, `code` (POINTS, REBOUNDS, ASSISTS…), `unit` |
| `player_injuries` | Injury status reports | `injury_id`, `player_id`, `status`, `report_date` |
| `player_game_stats` | Historical box scores | `player_game_id`, `player_id`, `game_id`, `points`, `rebounds`, `assists`, … |
| `odds` | Live sportsbook prop lines | `odds_id`, `sportsbook_id`, `game_id`, `player_id`, `prop_type_id`, `line_value`, `over_price`, `under_price` |
| `player_prop_predictions` | Model projections | `prediction_id`, `player_id`, `game_id`, `prop_type_id`, `projected_value`, `lower_ci`, `upper_ci` |
| `refresh_runs` | Pipeline audit log | `run_id`, `run_timestamp`, `source_system`, `status`, `records_loaded` |

### Key Relationships

- `players.team_id` → `teams.team_id`
- `games.home_team_id` / `games.away_team_id` → `teams.team_id`
- `odds.sportsbook_id` → `sportsbooks.sportsbook_id`
- `odds.game_id` → `games.game_id`
- `odds.player_id` → `players.player_id`
- `odds.prop_type_id` → `prop_types.prop_type_id`
- `player_game_stats.player_id` / `game_id` / `team_id` → respective parent tables
- `player_prop_predictions.player_id` / `game_id` / `prop_type_id` → respective parent tables

The design uses **normalized core tables for data integrity** and is designed to support denormalized reporting views (e.g., `vw_fact_player_prop_odds`) for dashboard query performance.

---

## Pipeline Architecture

```
Data Sources
    │
    ├── The Odds API ──────────────────► etl_odds.py ──────► odds table
    │
    ├── nba_api (game logs) ───────────► etl_player_stats.py ► player_game_stats table
    │
    ├── nba_api (roster) ──────────────► etl_players.py ────► players table
    │
    ├── nba_api (schedule) ────────────► etl_games.py ──────► games table
    │
    └── data/teams_all.csv ────────────► etl_pipeline.py ──► teams table
                │
                ▼
        src/predictions.py
        (rolling avg · home/away splits · CI)
                │
                ▼
        player_prop_predictions table
                │
                ▼
        Dash Dashboard (app.py)
        ├── Overview Page
        ├── Prop Lines Page
        ├── Player Trends Page
        └── Predictions Page
                │
                ▼
        APScheduler (scheduler.py)
        ├── Odds refresh: every 60 min
        └── Full pipeline: daily 8 AM
```

---

## Setup Instructions

### Prerequisites
- Python 3.10 or higher
- A free API key from [The Odds API](https://the-odds-api.com) (500 requests/month free)
- Git

### Step 1 — Clone the repository

```bash
git clone https://github.com/seanalamojr/nba-prop-dashboard-pipelineinsights.git
cd nba-prop-dashboard-pipelineinsights
```

### Step 2 — Create and activate a virtual environment

**Windows (Command Prompt):**
```cmd
python -m venv venv
venv\Scripts\activate.bat
```

**Mac/Linux:**
```bash
python -m venv venv
source venv/bin/activate
```

### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

### Step 4 — Configure environment variables

Copy `.env.example` to `.env` and fill in your API key:

```bash
cp .env.example .env
```

Edit `.env`:
```
ODDS_API_KEY=your_key_here
```

> The `.env` file is listed in `.gitignore` and will never be committed to GitHub.

### Step 5 — Initialize the database

```bash
python -m src.db.init_db
```

This creates `nba_props.db` and seeds the `sportsbooks` and `prop_types` reference tables.

### Step 6 — Run the full pipeline

```bash
python -m src.run_pipeline
```

This runs all ETL scripts in order: teams → players → games → player stats → odds → predictions.

### Step 7 — Start the dashboard

```bash
python app.py
```

Open your browser and go to: **http://127.0.0.1:8050**

---

## Dashboard Pages

### Overview
- KPI cards: active prop markets, avg line spread, predictions generated, value edges found
- Top value edges table (projection vs line ≥ 1.5 pts)
- Tonight's games with prop market counts
- Pipeline status with last refresh timestamps

### Prop Lines
- Full sportsbook comparison table (DraftKings, FanDuel, BetMGM)
- Filter by player name, prop type, and sportsbook
- Line discrepancy highlighting when books disagree

### Player Trends
- Rolling 10-game area chart per player per prop type
- Posted sportsbook line and model projection as reference lines
- Home / Away / matchup context splits

### Predictions
- Bar chart: projected value vs posted line for all tonight's players
- Individual prediction cards with confidence interval, edge indicator, and matchup notes
- Over/Under direction based on model vs line comparison

---

## Prediction Model

The prediction engine (`src/predictions.py`) uses a transparent, interpretable framework:

1. **Rolling average** — computes the mean of a player's last 10 games for the requested stat column
2. **Home/away split** — applies a minor adjustment based on whether the upcoming game is home or away
3. **Confidence interval** — uses the standard deviation of the input window to compute upper and lower bounds
4. **Edge calculation** — compares `projected_value` to `line_value` from the odds table; differences ≥ 1.5 are flagged as value edges

**Model version:** `rolling_avg_v1`  
**Minimum games required:** 5  
**Prop types supported:** POINTS, REBOUNDS, ASSISTS, STEALS, BLOCKS, TURNOVERS, THREE_PT

This approach is intentionally simple and interpretable. Results are presented as decision-support information, not guaranteed outcomes.

---

## ETL & Validation

Every ETL module follows the same pattern:

| Stage | What happens |
|---|---|
| Extract | Pull from API or CSV |
| Transform | Rename columns, standardize formats, derive fields |
| Validate | Null checks, duplicate checks, domain validation |
| Load | Incremental insert (skip rows that already exist) |
| Audit | Write a `RefreshRun` record with status and record count |

Validation rules enforced:
- Required columns may not be null
- No duplicate primary key candidates (e.g., `team_abbreviation`, `external_ref`)
- Conference values must be `"Eastern"` or `"Western"`
- Team abbreviations must be 2–4 characters

---

## Logging

All pipeline activity is written to two destinations simultaneously:

- **Console** — visible when running scripts in the terminal
- **File** — `logs/pipelineinsights.log` (auto-created on first run)

Log format:
```
2026-06-09 20:00:01 [INFO] Starting ETL pipeline for teams...
2026-06-09 20:00:01 [INFO] Extracted 30 rows from teams CSV
2026-06-09 20:00:01 [INFO] ETL pipeline completed successfully.
```

---

## Scheduler

`src/scheduler.py` uses APScheduler to keep the dashboard current without manual intervention:

| Job | Frequency | Function |
|---|---|---|
| Odds refresh | Every 60 minutes | `run_odds_etl()` |
| Full pipeline | Daily at 8:00 AM | `run_full_pipeline()` |
| Predictions | Every 60 minutes | `run_predictions()` |

The scheduler starts automatically when `app.py` is launched.

---

## Dependencies

```
pandas
requests
sqlalchemy
psycopg2-binary
dash
dash-bootstrap-components
plotly
python-dotenv
nba_api
apscheduler
```

Full pinned versions in `requirements.txt`.

---

## Data Sources

| Source | What it provides | Cost |
|---|---|---|
| [The Odds API](https://the-odds-api.com) | Live NBA player prop lines across DraftKings, FanDuel, BetMGM | Free (500 req/month) |
| [nba_api](https://github.com/swar/nba_api) | Historical player game logs, rosters, schedules | Free (no key needed) |

---

## Known Limitations & Future Work

- **Game ID linkage:** The odds ETL currently stores `game_id = NULL` on some rows when The Odds API event ID cannot be matched to a game in the local database. A fix requires syncing `Game.external_ref` from the same API source as the odds events.
- **Prediction coverage:** Players with fewer than 5 historical game logs will not generate predictions until the stats ETL has loaded sufficient history.
- **Prop type mapping:** The `PROP_TO_STAT_COL` dictionary in `predictions.py` must match the exact codes stored in the `prop_types` table.
- **Future:** Add machine learning model (Gradient Boosted Trees) as a `model_version = gbm_v1` alongside the rolling average baseline for comparison.
- **Future:** Add live injury status integration to dynamically adjust confidence intervals.
- **Future:** Deploy to cloud (Railway, Render, or AWS) for persistent hosting.

---

## Project Deliverables

| Deliverable | Location |
|---|---|
| Project Proposal | `docs/Alamo_Project_Proposal_PipelineInsights.docx` |
| Database Schema Report | `docs/alamo_database_schema_report.docx` |
| Initial Load Scripts | `src/db/init_db.py`, `src/db/initial_load_postgres.py` |
| ETL Pipelines | `src/etl_pipeline.py`, `src/etl_players.py`, `src/etl_games.py`, `src/etl_player_stats.py`, `src/etl_odds.py` |
| Validation Framework | Built into every ETL module (null/duplicate/domain checks) |
| Logging | `logs/pipelineinsights.log` + `refresh_runs` table |
| Dash Dashboard | `app.py` + dashboard page modules |
| Prediction Module | `src/predictions.py` |
| Scheduler | `src/scheduler.py` |
| Requirements | `requirements.txt` |

---

## Notes on AI Assistance

Perplexity AI (Computer) was used throughout this project to assist with debugging, code generation, architecture planning, and documentation writing. All design decisions, data modeling choices, and implementation logic were reviewed and directed by Sean Alamo.

---

