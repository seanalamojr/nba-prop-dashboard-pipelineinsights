"""
Overview page — KPI cards, tonight's games, pipeline status.
"""

import dash
from dash import html, dcc, callback, Input, Output
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from datetime import date
from sqlalchemy.orm import Session
from src.db.connection import get_engine
from src.db.models import Odd, PlayerPropPrediction, Game, RefreshRun, Team

# Register this page with Dash's page routing system
dash.register_page(__name__, path="/", name="Overview")

engine = get_engine()


def get_kpi_data():
    """Fetch numbers for the 4 KPI cards."""
    with Session(engine) as session:
        # Active prop markets = total distinct odds records loaded today
        active_props = session.query(Odd).count()
        
        # Predictions generated
        predictions = session.query(PlayerPropPrediction).count()
        
        # Tonight's games
        tonight = session.query(Game).filter(
            Game.game_date == date.today(),
            Game.status.in_(["Scheduled", "Pre-Game"])
        ).count()
        
        # Value edges = predictions where |projection - line| > 2 (meaningful difference)
        # This is a simple definition — you can refine it
        all_preds = session.query(PlayerPropPrediction).all()
        edge_count = 0
        for pred in all_preds:
            # Find a matching odds record for the same player+game+prop
            matching_odds = session.query(Odd).filter_by(
                player_id=pred.player_id,
                game_id=pred.game_id,
                prop_type_id=pred.prop_type_id
            ).first()
            if matching_odds and matching_odds.line_value:
                edge = abs(pred.projected_value - matching_odds.line_value)
                if edge >= 2.0:
                    edge_count += 1
        
        return {
            "active_props": active_props,
            "predictions": predictions,
            "tonight": tonight,
            "edges": edge_count
        }


def get_tonight_games():
    """Get tonight's scheduled games."""
    with Session(engine) as session:
        games = (
            session.query(Game)
            .filter(
                Game.game_date == date.today(),
            )
            .all()
        )
        result = []
        for g in games:
            home = session.query(Team).filter_by(team_id=g.home_team_id).first()
            away = session.query(Team).filter_by(team_id=g.away_team_id).first()
            result.append({
                "matchup": f"{away.team_abbreviation if away else '?'} @ {home.team_abbreviation if home else '?'}",
                "time": str(g.start_time_utc)[:16] if g.start_time_utc else "TBD",
                "status": g.status or "Scheduled"
            })
        return result


def get_pipeline_status():
    """Get the last run status of each pipeline."""
    with Session(engine) as session:
        sources = ["TeamsCSV", "BallDontLie_games", "nba_api_stats", "TheOddsAPI", "Predictions"]
        status_rows = []
        for source in sources:
            run = (
                session.query(RefreshRun)
                .filter_by(source_system=source)
                .order_by(RefreshRun.run_timestamp.desc())
                .first()
            )
            if run:
                status_rows.append({
                    "source": source,
                    "status": run.status,
                    "last_run": str(run.run_timestamp)[:16],
                    "records": run.records_loaded
                })
        return status_rows


# ── Layout ────────────────────────────────────────────────────────────────────
layout = html.Div([
    dcc.Interval(id="overview-refresh", interval=300_000, n_intervals=0),  # Refresh every 5 min
    html.H2("Overview", className="my-3"),
    
    # KPI Cards row
    dbc.Row(id="kpi-cards", className="mb-4"),
    
    dbc.Row([
        # Tonight's games
        dbc.Col([
            html.H4("Tonight's Games"),
            html.Div(id="tonight-games-table")
        ], md=6),
        
        # Pipeline status
        dbc.Col([
            html.H4("Pipeline Status"),
            html.Div(id="pipeline-status-table")
        ], md=6),
    ])
])


# ── Callbacks ─────────────────────────────────────────────────────────────────
@callback(
    Output("kpi-cards", "children"),
    Input("overview-refresh", "n_intervals")
)
def update_kpi_cards(_):
    """A 'callback' in Dash is a function that updates a part of the page.
    The Input is what triggers the update; the Output is what changes."""
    kpi = get_kpi_data()
    
    def make_card(title, value, color):
        return dbc.Col(
            dbc.Card([
                dbc.CardBody([
                    html.H6(title, className="card-subtitle text-muted mb-1"),
                    html.H2(str(value), className=f"text-{color}")
                ])
            ], className="shadow-sm"),
            md=3
        )
    
    return [
        make_card("Active Prop Markets", kpi["active_props"], "info"),
        make_card("Predictions Generated", kpi["predictions"], "success"),
        make_card("Tonight's Games", kpi["tonight"], "warning"),
        make_card("Value Edges Found", kpi["edges"], "danger"),
    ]


@callback(
    Output("tonight-games-table", "children"),
    Input("overview-refresh", "n_intervals")
)
def update_tonight_games(_):
    games = get_tonight_games()
    if not games:
        return html.P("No games scheduled for today.", className="text-muted")
    
    rows = [
        html.Tr([
            html.Td(g["matchup"]),
            html.Td(g["time"]),
            html.Td(dbc.Badge(g["status"], color="success" if g["status"] == "Final" else "primary"))
        ])
        for g in games
    ]
    
    return dbc.Table([
        html.Thead(html.Tr([html.Th("Matchup"), html.Th("Time (UTC)"), html.Th("Status")])),
        html.Tbody(rows)
    ], bordered=True, hover=True, responsive=True, size="sm")


@callback(
    Output("pipeline-status-table", "children"),
    Input("overview-refresh", "n_intervals")
)
def update_pipeline_status(_):
    status_rows = get_pipeline_status()
    if not status_rows:
        return html.P("No pipeline runs recorded yet.", className="text-muted")
    
    rows = [
        html.Tr([
            html.Td(r["source"]),
            html.Td(dbc.Badge(r["status"], color="success" if r["status"] == "Success" else "danger")),
            html.Td(r["last_run"]),
            html.Td(r["records"]),
        ])
        for r in status_rows
    ]
    
    return dbc.Table([
        html.Thead(html.Tr([html.Th("Source"), html.Th("Status"), html.Th("Last Run"), html.Th("Records")])),
        html.Tbody(rows)
    ], bordered=True, hover=True, responsive=True, size="sm")