"""
Prop Lines page — sportsbook comparison table with filters.
"""

import dash
from dash import html, dcc, callback, Input, Output
import dash_bootstrap_components as dbc
import pandas as pd
from sqlalchemy.orm import Session
from src.db.connection import get_engine
from src.db.models import Odd, Player, Sportsbook, PropType, Game

dash.register_page(__name__, path="/prop-lines", name="Prop Lines")

engine = get_engine()


def get_filter_options():
    """Get dropdown options for player, prop type, and sportsbook filters."""
    with Session(engine) as session:
        players = session.query(Player).filter(
            Player.is_active == True
        ).order_by(Player.last_name).all()
        player_opts = [{"label": p.full_name, "value": p.player_id} for p in players]
        
        prop_types = session.query(PropType).all()
        prop_opts = [{"label": pt.description, "value": pt.prop_type_id} for pt in prop_types]
        
        sportsbooks = session.query(Sportsbook).all()
        sb_opts = [{"label": sb.name, "value": sb.sportsbook_id} for sb in sportsbooks]
        
        return player_opts, prop_opts, sb_opts


def get_odds_table(player_id=None, prop_type_id=None, sportsbook_ids=None):
    """
    Queries the odds table with optional filters and returns a wide-format
    comparison table: one row per player+prop, one column per sportsbook.
    """
    with Session(engine) as session:
        query = session.query(
            Odd, Player.full_name, Sportsbook.name, PropType.description
        ).join(Player, Odd.player_id == Player.player_id, isouter=True)\
         .join(Sportsbook, Odd.sportsbook_id == Sportsbook.sportsbook_id)\
         .join(PropType, Odd.prop_type_id == PropType.prop_type_id, isouter=True)
        
        if player_id:
            query = query.filter(Odd.player_id == player_id)
        if prop_type_id:
            query = query.filter(Odd.prop_type_id == prop_type_id)
        if sportsbook_ids:
            query = query.filter(Odd.sportsbook_id.in_(sportsbook_ids))
        
        results = query.limit(500).all()
        
        if not results:
            return pd.DataFrame()
        
        rows = []
        for odd, player_name, sb_name, prop_desc in results:
            rows.append({
                "Player": player_name or "Unknown",
                "Prop": prop_desc or odd.market_name,
                "Sportsbook": sb_name,
                "Line": odd.line_value,
                "Over": odd.over_price,
                "Under": odd.under_price,
                "Updated": str(odd.odds_timestamp)[:16] if odd.odds_timestamp else ""
            })
        
        return pd.DataFrame(rows)


player_opts, prop_opts, sb_opts = get_filter_options()

layout = html.Div([
    html.H2("Prop Lines", className="my-3"),
    html.P("Compare player prop lines across sportsbooks. Use the filters below to narrow results.", className="text-muted"),
    
    # Filters
    dbc.Row([
        dbc.Col([
            html.Label("Player"),
            dcc.Dropdown(
                id="pl-player-filter",
                options=player_opts,
                placeholder="All Players",
                clearable=True
            )
        ], md=4),
        dbc.Col([
            html.Label("Prop Type"),
            dcc.Dropdown(
                id="pl-prop-filter",
                options=prop_opts,
                placeholder="All Props",
                clearable=True
            )
        ], md=4),
        dbc.Col([
            html.Label("Sportsbooks"),
            dcc.Dropdown(
                id="pl-sb-filter",
                options=sb_opts,
                placeholder="All Sportsbooks",
                multi=True
            )
        ], md=4),
    ], className="mb-3"),
    
    html.Div(id="prop-lines-table")
])


@callback(
    Output("prop-lines-table", "children"),
    Input("pl-player-filter", "value"),
    Input("pl-prop-filter", "value"),
    Input("pl-sb-filter", "value"),
)
def update_prop_lines(player_id, prop_type_id, sportsbook_ids):
    df = get_odds_table(player_id, prop_type_id, sportsbook_ids)
    
    if df.empty:
        return dbc.Alert(
            "No prop lines found. Run the odds ETL pipeline to load data: python src/etl_odds.py",
            color="info"
        )
    
    return dbc.Table.from_dataframe(
        df, striped=True, bordered=True, hover=True, responsive=True, size="sm"
    )