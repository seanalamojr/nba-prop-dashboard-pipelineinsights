"""
PipelineInsights — NBA Player Prop Comparison and Prediction Dashboard

Main Dash application entry point.

This file:
1. Creates the Dash app
2. Defines the overall layout (navigation + page container)
3. Registers the multi-page routing
4. Starts the development server

All page content lives in the pages/ folder (see below).
"""

import os
import dash
import dash_bootstrap_components as dbc
from dash import html, dcc
import logging

# Create the Dash app
# Use multi-page mode (pages/ folder) and Bootstrap CSS for styling
app = dash.Dash(
    __name__,
    use_pages=True,                          # Enable automatic page routing
    external_stylesheets=[dbc.themes.DARKLY], # Dark Bootstrap theme
    suppress_callback_exceptions=True         # Required for multi-page apps
)

# The overall layout is just a navbar + the page content area
# Each page in pages/ replaces dash.page_container when navigated to
app.layout = dbc.Container([
    # ── Navigation Bar ─────────────────────────────────────
    dbc.NavbarSimple(
        brand="🏀 PipelineInsights",
        brand_href="/",
        color="dark",
        dark=True,
        children=[
            dbc.NavItem(dbc.NavLink("Overview", href="/")),
            dbc.NavItem(dbc.NavLink("Prop Lines", href="/prop-lines")),
            dbc.NavItem(dbc.NavLink("Player Trends", href="/player-trends")),
            dbc.NavItem(dbc.NavLink("Predictions", href="/predictions")),
        ]
    ),
    
    # ── Page content — this changes with each nav click ────
    dash.page_container
    
], fluid=True, className="p-0")


if __name__ == "__main__":
    # Create logs directory if it doesn't exist (must be before FileHandler)
    os.makedirs("logs", exist_ok=True)

    # Set up project-wide logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        handlers=[
            logging.StreamHandler(),                      # Print to terminal
            logging.FileHandler("logs/pipelineinsights.log"),  # Save to file
        ],
    )

    # Start the background scheduler (for ETL refresh jobs)
    from src.scheduler import start_scheduler
    start_scheduler()

    # Start the Dash app (Dash 4 uses app.run)
    app.run(debug=True, port=8050)