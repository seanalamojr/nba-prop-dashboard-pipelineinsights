import logging
from dash import Dash, html, dcc
import plotly.express as px
import pandas as pd
from sqlalchemy import create_engine

# Database config (same as in etl_pipeline.py)
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "nba_props",
    "user": "postgres",
    "password": "password",
}

engine = create_engine(
    f"postgresql+psycopg2://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
    f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}"
)

def load_teams_view() -> pd.DataFrame:
    logging.info("Loading data from vw_dim_teams...")
    query = "SELECT * FROM vw_dim_teams;"
    with engine.begin() as conn:
        df = pd.read_sql(query, conn)
    logging.info("Loaded %d rows from vw_dim_teams.", len(df))
    return df

app = Dash(__name__)

# Load data once at startup
teams_df = load_teams_view()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# Create the Dash app object at the top level
app = Dash(__name__)

# Build figures from the DataFrame

# Conference-level counts
conf_df = (
    teams_df.groupby("conference")["team_id"]
    .count()
    .reset_index(name="team_count")
)

fig_conf = px.bar(
    conf_df,
    x="conference",
    y="team_count",
    title="Number of Teams by Conference",
)

# Division-level counts
div_df = (
    teams_df.groupby("division")["team_id"]
    .count()
    .reset_index(name="team_count")
)

fig_div = px.bar(
    div_df,
    x="division",
    y="team_count",
    title="Number of Teams by Division",
)

total_teams = len(teams_df)

conference_options = [
    {"label": conf, "value": conf}
    for conf in sorted(teams_df["conference"].dropna().unique())
]

# Define the layout
from dash import Input, Output  # make sure this import is at the top

app.layout = html.Div(
    children=[
        html.H1("NBA Teams Dashboard - MVP"),

        # KPI card
        html.Div(
            children=[
                html.H3("Total Teams"),
                html.H2(id="kpi-total-teams"),
            ],
            style={
                "border": "1px solid #ccc",
                "padding": "10px",
                "display": "inline-block",
                "margin": "10px",
            },
        ),

        # Filter
        html.Div(
            children=[
                html.Label("Conference Filter"),
                dcc.Dropdown(
                    id="conference-filter",
                    options=conference_options,
                    value=None,
                    placeholder="Select a conference (optional)",
                    clearable=True,
                    style={"width": "300px"},
                ),
            ],
            style={"margin": "10px 0"},
        ),

        # Charts
        html.Div(
            children=[
                dcc.Graph(id="teams-by-conference"),
                dcc.Graph(id="teams-by-division"),
            ]
        ),
    ]
)



@app.callback(
    Output("kpi-total-teams", "children"),
    Output("teams-by-conference", "figure"),
    Output("teams-by-division", "figure"),
    Input("conference-filter", "value"),
)
def update_dashboard(selected_conference):
    if selected_conference:
        filtered = teams_df[teams_df["conference"] == selected_conference]
    else:
        filtered = teams_df

    # KPI
    kpi_value = len(filtered)

    # Rebuild figures from filtered data
    conf_df = (
        filtered.groupby("conference")["team_id"]
        .count()
        .reset_index(name="team_count")
    )
    fig_conf = px.bar(
        conf_df,
        x="conference",
        y="team_count",
        title="Number of Teams by Conference",
    )

    div_df = (
        filtered.groupby("division")["team_id"]
        .count()
        .reset_index(name="team_count")
    )
    fig_div = px.bar(
        div_df,
        x="division",
        y="team_count",
        title="Number of Teams by Division",
    )

    return kpi_value, fig_conf, fig_div

# Entry point
if __name__ == "__main__":
    logging.info("Starting Dash app...")
    app.run(debug=True)