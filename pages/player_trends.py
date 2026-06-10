"""
Player Trends page — rolling average area chart + home/away splits.
"""

import dash
from dash import html, dcc, callback, Input, Output
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
from sqlalchemy.orm import Session
from src.db.connection import get_engine
from src.db.models import Player, PlayerGameStat, Game, PropType

dash.register_page(__name__, path="/player-trends", name="Player Trends")

engine = get_engine()


def get_active_players_with_stats():
    """Returns players who have at least some stats loaded."""
    with Session(engine) as session:
        players = (
            session.query(Player)
            .join(PlayerGameStat, Player.player_id == PlayerGameStat.player_id)
            .filter(Player.is_active == True)
            .distinct()
            .order_by(Player.last_name)
            .all()
        )
        return [{"label": p.full_name, "value": p.player_id} for p in players]


def get_player_stat_history(player_id: int, stat_col: str = "points", n_games: int = 20):
    """Returns a DataFrame of a player's recent game stats, sorted oldest to newest."""
    col_map = {
        "Points": "points",
        "Rebounds": "rebounds",
        "Assists": "assists",
        "Steals": "steals",
        "Blocks": "blocks",
        "Turnovers": "turnovers",
        "3PM": "three_pt_made",
    }
    db_col = col_map.get(stat_col, "points")
    
    with Session(engine) as session:
        results = (
            session.query(PlayerGameStat, Game.game_date, Game.home_team_id)
            .join(Game, PlayerGameStat.game_id == Game.game_id)
            .filter(PlayerGameStat.player_id == player_id)
            .order_by(Game.game_date.desc())
            .limit(n_games)
            .all()
        )
        
        if not results:
            return pd.DataFrame()
        
        rows = []
        for stat, game_date, home_team_id in results:
            rows.append({
                "game_date": game_date,
                "value": getattr(stat, db_col, 0) or 0,
                "is_home": stat.team_id == home_team_id,
                "minutes": stat.minutes_played or 0
            })
        
        df = pd.DataFrame(rows).sort_values("game_date")
        df["rolling_avg"] = df["value"].rolling(5, min_periods=1).mean().round(1)
        return df


player_opts = get_active_players_with_stats()
stat_opts = [
    {"label": "Points", "value": "Points"},
    {"label": "Rebounds", "value": "Rebounds"},
    {"label": "Assists", "value": "Assists"},
    {"label": "Steals", "value": "Steals"},
    {"label": "Blocks", "value": "Blocks"},
    {"label": "Turnovers", "value": "Turnovers"},
    {"label": "3PM", "value": "3PM"},
]

layout = html.Div([
    html.H2("Player Trends", className="my-3"),
    
    dbc.Row([
        dbc.Col([
            html.Label("Player"),
            dcc.Dropdown(
                id="pt-player",
                options=player_opts,
                placeholder="Select a player...",
                clearable=False
            )
        ], md=6),
        dbc.Col([
            html.Label("Stat"),
            dcc.Dropdown(
                id="pt-stat",
                options=stat_opts,
                value="Points",
                clearable=False
            )
        ], md=6),
    ], className="mb-3"),
    
    dcc.Graph(id="trend-chart"),
    
    dbc.Row([
        dbc.Col([
            html.H5("Home vs. Away Split"),
            html.Div(id="home-away-split")
        ], md=6),
        dbc.Col([
            html.H5("Last 10 Games"),
            html.Div(id="recent-games-table")
        ], md=6),
    ], className="mt-3")
])


@callback(
    Output("trend-chart", "figure"),
    Output("home-away-split", "children"),
    Output("recent-games-table", "children"),
    Input("pt-player", "value"),
    Input("pt-stat", "value"),
)
def update_trends(player_id, stat_col):
    if not player_id:
        empty_fig = go.Figure()
        empty_fig.update_layout(
            title="Select a player to view trends",
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)"
        )
        return empty_fig, html.P("Select a player."), html.P("Select a player.")
    
    df = get_player_stat_history(player_id, stat_col or "Points")
    
    if df.empty:
        empty_fig = go.Figure()
        empty_fig.update_layout(title="No data available for this player", template="plotly_dark")
        return empty_fig, html.P("No data."), html.P("No data.")
    
    # ── Rolling Average Area Chart ─────────────────────────────
    fig = go.Figure()
    
    # Shaded area under the rolling average line
    fig.add_trace(go.Scatter(
        x=df["game_date"],
        y=df["rolling_avg"],
        fill="tozeroy",
        name="5-Game Rolling Avg",
        line=dict(color="#00bc8c", width=2),
        fillcolor="rgba(0, 188, 140, 0.15)"
    ))
    
    # Individual game markers
    fig.add_trace(go.Scatter(
        x=df["game_date"],
        y=df["value"],
        mode="markers",
        name=f"Game {stat_col}",
        marker=dict(
            color=["#3498db" if h else "#e74c3c" for h in df["is_home"]],
            size=8
        )
    ))
    
    fig.update_layout(
        title=f"{stat_col} — Last {len(df)} Games",
        xaxis_title="Game Date",
        yaxis_title=stat_col,
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(30,30,30,0.8)",
        legend=dict(orientation="h", y=1.1),
        hovermode="x unified"
    )
    
    # ── Home/Away Split ────────────────────────────────────────
    home_df = df[df["is_home"] == True]
    away_df = df[df["is_home"] == False]
    
    split_content = dbc.Table([
        html.Thead(html.Tr([html.Th("Context"), html.Th("Games"), html.Th(f"Avg {stat_col}")])),
        html.Tbody([
            html.Tr([html.Td("Home"), html.Td(len(home_df)), html.Td(f"{home_df['value'].mean():.1f}" if len(home_df) > 0 else "—")]),
            html.Tr([html.Td("Away"), html.Td(len(away_df)), html.Td(f"{away_df['value'].mean():.1f}" if len(away_df) > 0 else "—")]),
            html.Tr([html.Td("Overall"), html.Td(len(df)), html.Td(f"{df['value'].mean():.1f}")]),
        ])
    ], bordered=True, size="sm")
    
    # ── Recent Games Table ─────────────────────────────────────
    recent = df.tail(10).sort_values("game_date", ascending=False)
    recent_rows = [
        html.Tr([
            html.Td(str(row["game_date"])),
            html.Td(row["value"]),
            html.Td(row["rolling_avg"]),
            html.Td("🏠" if row["is_home"] else "✈️"),
        ])
        for _, row in recent.iterrows()
    ]
    
    recent_table = dbc.Table([
        html.Thead(html.Tr([html.Th("Date"), html.Th(stat_col), html.Th("5G Avg"), html.Th("Loc")])),
        html.Tbody(recent_rows)
    ], bordered=True, hover=True, size="sm")
    
    return fig, split_content, recent_table