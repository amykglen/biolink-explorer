import dash
from dash import html, callback, State  # Use 'callback' decorator directly
from dash import Input, Output  # Import necessary Dash components
import dash_cytoscape as cyto
from typing import List, Tuple, Dict, Optional, Any

from app import styles, get_biolink_data_for_version
from pages import utils

# --- Register Page ---
dash.register_page(
    __name__,
    path='/',  # Set as the default/home page route
    name='Categories', # Name for navigation links
    title='Categories' # Browser tab title
)


# --- Page Layout Definition ---
def layout() -> html.Div:
    return html.Div([
        html.Div(
            style=styles.tab_content_style,
            children=[
                # Filters will be populated by callback
                html.Div(id="category-filters-container"),
                cyto.Cytoscape(
                    id="cytoscape-dag-cats",
                    layout=styles.layout_settings,
                    style=styles.cytoscape_style,
                    stylesheet=styles.main_styling
                ),
                html.Div(id="node-info-cats", style=styles.node_info_div_style)
            ])
    ])


# --- Callbacks specific to this page ---




