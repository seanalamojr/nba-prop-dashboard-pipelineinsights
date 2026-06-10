"""
Predictions page — model projections vs. posted lines with edge indicators.
"""

import dash
from dash import html, dcc, callback, Input, Output
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
from sqlalchemy.orm import Session
from src.db.connection import get_engine
from src.db.models import (
    PlayerPropPrediction, Player, Game, PropType, Odd, Sportsbook, Team
)

dash.register_page(__name__, path="/predictions", name="Predictions")

engine = get_engine()

EDGE_THRESHOLD = 2.0  # Points difference to flag as a "value edge"


def get_predictions_with_odds():
    """
    Joins predictions with the best available odds line and computes edge.
    Returns a DataFrame with all the info needed for the display table.
    """
    with Session(engine) as session:
        preds = session.query(PlayerPropPrediction).all()
        
        if not preds:
            return pd.DataFrame()
        
        rows = []
        for pred in preds:
            player = session.query(Player).filter_by(player_id=pred.player_id).first()
            game = session.query(Game).filter_by(game_id=pred.game_id).first()
            prop_type = session.query(PropType).filter_by(prop_type_id=pred.prop_type_id).first()
            
            # Get the best (average) line from all sportsbooks for this player+game+prop
            best_line = session.query(Odd).filter_by(
                player_id=pred.player_id,
                game_id=pred.game_id,
                prop_type_id=pred.prop_type_id
            ).first()
            
            home_team = session.query(Team).filter_by(team_id=game.home_team_id).first() if game else None
            away_team = session.query(Team).filter_by(team_id=game.away_team_id).first() if game else None
            
            line = best_line.line_value if best_line else None
            edge = round(pred.projected_value - line, 1) if line else None
            
            rows.append({
                "Player": player.full_name if player else "Unknown",
                "Prop": prop_type.description if prop_type else "?",
                "Game": f"{away_team.team_abbreviation if away_team else '?'} @ {home_team.team_abbreviation if home_team else '?'}" if game else "?",
                "Date": str(game.game_date) if game else "?",
                "Projection": pred.projected_value,
                "Lower CI": pred.lower_ci,
                "Upper CI": pred.upper_ci,
                "Best Line": line,
                "Edge": edge,
                "Games Used": pred.input_window_games,
            })
        
        return pd.DataFrame(rows)


layout = html.Div([
    html.H2("Predictions", className="my-3"),
    html.P(
        "Model projections compared to posted sportsbook lines. "
        f"Edge = Projection minus Line. Values ≥ {EDGE_THRESHOLD} or ≤ -{EDGE_THRESHOLD} are highlighted.",
        className="text-muted"
    ),
    
    dbc.Row([
        dbc.Col([
            html.Label("Minimum Edge"),
            dcc.Slider(
                id="edge-threshold",
                min=0, max=5, step=0.5, value=0,
                marks={i: str(i) for i in range(6)}
            )
        ], md=6),
        dbc.Col([
            dbc.Button("🔄 Refresh", id="pred-refresh-btn", color="primary", className="mt-4")
        ], md=2),
    ], className="mb-3"),
    
    html.Div(id="predictions-table"),
    
    html.Hr(),
    html.H4("Projection vs. Line — Visual Comparison"),
    dcc.Graph(id="edge-chart")
])


@callback(
    Output("predictions-table", "children"),
    Output("edge-chart", "figure"),
    Input("edge-threshold", "value"),
    Input("pred-refresh-btn", "n_clicks"),
)
def update_predictions(min_edge, _):
    df = get_predictions_with_odds()
    
    if df.empty:
        msg = dbc.Alert(
            "No predictions found. Make sure the odds ETL and prediction pipeline have been run.",
            color="info"
        )
        empty_fig = go.Figure()
        empty_fig.update_layout(title="No prediction data", template="plotly_dark")
        return msg, empty_fig
    
    # Filter by minimum edge
    if min_edge and "Edge" in df.columns:
        df_filtered = df[df["Edge"].abs() >= min_edge]
    else:
        df_filtered = df
    
    # Build the table with color-coded edge cells
    table_rows = []
    for _, row in df_filtered.iterrows():
        edge = row.get("Edge")
        if edge is not None:
            if edge >= EDGE_THRESHOLD:
                edge_badge = dbc.Badge(f"+{edge}", color="success")
            elif edge <= -EDGE_THRESHOLD:
                edge_badge = dbc.Badge(str(edge), color="danger")
            else:
                edge_badge = dbc.Badge(str(edge), color="secondary")
        else:
            edge_badge = dbc.Badge("N/A", color="secondary")
        
        table_rows.append(html.Tr([
            html.Td(row["Player"]),
            html.Td(row["Prop"]),
            html.Td(row["Game"]),
            html.Td(f"{row['Projection']} [{row['Lower CI']}–{row['Upper CI']}]"),
            html.Td(str(row.get("Best Line", "—"))),
            html.Td(edge_badge),
        ]))
    
    table = dbc.Table([
        html.Thead(html.Tr([
            html.Th("Player"), html.Th("Prop"), html.Th("Game"),
            html.Th("Projection [CI]"), html.Th("Best Line"), html.Th("Edge")
        ])),
        html.Tbody(table_rows)
    ], bordered=True, hover=True, responsive=True, size="sm")
    
    # Edge waterfall / scatter chart
    df_chart = df_filtered.dropna(subset=["Edge"]).sort_values("Edge", ascending=False).head(20)
    
    fig = go.Figure(go.Bar(
        x=df_chart["Player"] + " — " + df_chart["Prop"],
        y=df_chart["Edge"],
        marker_color=[
            "#00bc8c" if e >= EDGE_THRESHOLD
            else "#e74c3c" if e <= -EDGE_THRESHOLD
            else "#6c757d"
            for e in df_chart["Edge"]
        ],
        text=df_chart["Edge"].apply(lambda x: f"+{x}" if x > 0 else str(x)),
        textposition="outside"
    ))
    
    fig.update_layout(
        title="Top Edges: Projection vs. Line",
        xaxis_title="Player — Prop",
        yaxis_title="Edge (Projection − Line)",
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(30,30,30,0.8)",
        xaxis_tickangle=-45,
        height=400
    )
    
    return table, fig