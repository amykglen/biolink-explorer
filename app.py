import functools
import os
import sys
from typing import Dict, Tuple, List, Any, Optional

import dash_cytoscape as cyto
from dash import Dash, Input, Output, dcc, html, page_registry, page_container, no_update, State

from biolink_manager import BiolinkManager, get_biolink_github_tags

# Import custom modules/classes
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from styles import Styles
from pages import utils

# Load additional Cytoscape layouts (including Dagre)
cyto.load_extra_layouts()


bm_cache: Dict[str, any] = dict()

styles: Styles = Styles()


@functools.lru_cache(maxsize=8) # Example: Cache data for up to 8 Biolink versions
def get_biolink_data_for_version(version: str) -> Dict[str, any]:
    """
    Fetches and processes Biolink data for the specified version using
    BiolinkManager. Updates a cache with data for different Biolink
    versions.
    """
    if version not in bm_cache:
        bm = BiolinkManager(biolink_version=version)
        elements_predicates = bm.predicate_dag_dash
        elements_categories = bm.category_dag_dash

        # Extract unique domain, range, category, and predicate values for dropdowns
        if bm.category_dag:
            domains = sorted(list(set(bm.category_dag.nodes())))
            ranges = sorted(list(set(bm.category_dag.nodes())))
            all_categories = sorted(list(set(bm.category_dag.nodes())))
        else:
            domains = []
            ranges = []
            all_categories = []

        if bm.predicate_dag:
            all_predicates = sorted(list(bm.predicate_dag.nodes()))
        else:
            all_predicates = []
        bm_cache[version] = {"bm": bm,
                              "elements_predicates": elements_predicates,
                              "elements_categories": elements_categories,
                              "domains": domains,
                              "ranges": ranges,
                              "all_categories": all_categories,
                              "all_predicates": all_predicates}
    return bm_cache[version]


# Determine initial version and pre-load/cache its data
all_version_tags = get_biolink_github_tags()
initial_version_tag = all_version_tags[0]
get_biolink_data_for_version(initial_version_tag)

# Initiate the dash app and expose the server variable for Heroku deployment
app: Dash = Dash(__name__, title="Biolink Explorer", use_pages=True)
server_app = app.server

# Set the main app layout
app.layout = html.Div([
        # Store for the user's selected version tag
        dcc.Store(id='session-biolink-version-store', data=initial_version_tag),  # Initialize with default

        # Header section with title and version selector
        html.Div([
            html.Div("Biolink Model Explorer", style={
                "fontSize": "18px",
                "fontWeight": "bold"
            }),
            html.Div([
                html.Label([
                    "Showing ",
                    html.Div(id="biolink-version-link", style={"display": "inline-block"}),
                    " version:"
                ], style={"marginRight": "5px"}),
                dcc.Dropdown(
                    id="biolink-version-input",
                    options=[{"label": tag, "value": tag} for tag in all_version_tags],
                    value=initial_version_tag,
                    clearable=False,
                    style={"width": "120px", "marginRight": "5px"}
                ),
            ], style={
                "display": "flex",
                "alignItems": "center"
            })
        ], style={
            "display": "flex",
            "justifyContent": "space-between",
            "alignItems": "center",
            "padding": "10px 10px",
            "borderBottom": "1px solid #ddd"
        }),

        # -- Persistent Navigation Links --
        html.Div([
            # Use dash.page_registry to dynamically get paths for registered pages
            # This assumes you have pages/categories.py, pages/predicates.py, etc.
            # And they use dash.register_page(..., path='/categories'), etc.
            # The key in page_registry is module 'pages.pagename'
            dcc.Link("Categories", href=page_registry['pages.categories']['path'], style={'padding': '5px'}),
            dcc.Link("Predicates", href=page_registry['pages.predicates']['path'], style={'padding': '5px'}),
            dcc.Link("Info", href=page_registry['pages.info']['path'], style={'padding': '5px'})
            # Add default page link if desired:
            # dcc.Link("Home (Categories)", href=dash.page_registry['pages.categories']['path'])
        ], style={'padding': '10px', 'borderBottom': '1px solid #eee'}),

        # -- Page Content Container --
        # Content from the files in the 'pages' directory will be rendered here
        html.Div(style={'padding': '10px'}, children=[
            page_container
        ])
    ])


# --------------------------- Callback Registration (for this page-independent layout) --------------------------- #


# Update the session store when the version dropdown selection changes
@app.callback(
    Output('session-biolink-version-store', 'data'),
    Input('biolink-version-input', 'value')
    # This runs on initial load AND when the user changes the dropdown
)
def update_session_version(version_tag):
    if not version_tag:
        return no_update # Should only happen if clearable=True was added
    # We don't strictly NEED to preload cache here, the page load will trigger it.
    # But it could be done for perceived performance:
    # get_biolink_data_for_version(version_tag)
    print(f"SESSION STORE: Setting version to {version_tag}")
    return version_tag


# Update the dynamic Biolink version link in the header
@app.callback(
    Output("biolink-version-link", 'children'),
    Input('session-biolink-version-store', 'data')
    # This runs on initial load AND whenever the stored version changes
)
def update_biolink_anchor(version_tag):
    if version_tag:
        # Optional: could display the resolved version number if different from tag
        # version_data = get_biolink_data_for_version(version_tag)
        # display_tag = version_data['actual_version'] if version_data else version_tag
        print(f"HEADER LINK: Updating for version tag {version_tag}")
        return html.A(
            "Biolink Model",
            # Link using the selected tag (maps to GitHub branches/tags)
            href=f"https://github.com/biolink/biolink-model/blob/{version_tag}/biolink-model.yaml",
            target="_blank",
            style=styles.hyperlink_style # Assumes styles instance is accessible
        )
    print("HEADER LINK: No version tag found.")
    return "Biolink Model" # Default text



@app.callback(
    Output("node-info-cats", "children"),
    Input("cytoscape-dag-cats", "selectedNodeData"),
)
def display_node_info_categories(selected_nodes: Optional[List[Dict[str, Any]]]) -> Any:
    """Displays information for the selected category node."""
    return utils.get_node_info(selected_nodes)



# Callback to populate the page's dynamic components (filters, graph) based on the stored version
@app.callback(
    Output('category-filters-container', 'children'),
    Output('cytoscape-dag-cats', 'elements'),
    Input('session-biolink-version-store', 'data'), # Triggered by store change (inc. initial load)
    prevent_initial_call=False # Ensure this runs on load
)
def update_page_components(version_tag):
    """Populates filters and initial graph elements when version changes."""
    print(f"CATEGORIES PAGE: Loading UI for version tag '{version_tag}'")
    if not version_tag:
        return "No Biolink version selected.", []

    version_data = get_biolink_data_for_version(version_tag)
    if not version_data:
        print(f"CATEGORIES PAGE: Failed to load data for '{version_tag}'")
        return f"Error loading data for Biolink version '{version_tag}'.", []

    print(f"CATEGORIES PAGE: Data loaded for '{version_tag}'. Populating UI.")
    # Generate filter controls using data for this version
    filter_controls = utils.get_filter_divs_cats(version_data['all_categories'])

    # Return filter controls and the initial elements for the graph
    return filter_controls, version_data['elements_categories']



@app.callback(
    Output("cytoscape-dag-cats", "elements", allow_duplicate=True),
    Output("include-mixins-cats", "value"),
    Input("include-mixins-cats", "value"),
    Input("node-search-cats", "value"),
    State('session-biolink-version-store', 'data'),  # READ version from store
    prevent_initial_call=True
)
def filter_graph_categories(
    include_mixins: List[str],
    search_nodes: Optional[List[str]],
    version_tag: str
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Filters category graph based on mixins and search, and updates upon on Biolink version change."""

    # Get data from cache for the session's version
    version_data = get_biolink_data_for_version(version_tag)
    if not version_data or not version_data.get('bm'): # Check if data/bm loaded
         return [], include_mixins
    bm = version_data['bm'] # Use the BM instance for THIS version
    elements_categories = version_data['elements_categories'] # Use elements for THIS version

    include_mixins_updated = include_mixins # Start with user's selection
    if search_nodes:
        # If a mixin was searched, force 'include mixins' checkbox
        if any(bm.category_dag.nodes[node_id].get("is_mixin") for node_id in search_nodes):
            include_mixins_updated = ["include"]

    return utils.filter_graph(elements_categories,
                              [],
                              [],
                              include_mixins_updated,
                              search_nodes,
                              bm.category_dag,
                              bm), include_mixins_updated



@app.callback(
    Output("node-info-preds", "children"),
    Input("cytoscape-dag-preds", "selectedNodeData"),
)
def display_node_info_predicates(selected_nodes: Optional[List[Dict[str, Any]]]) -> Any:
    """Displays information for the selected predicate node."""
    return utils.get_node_info(selected_nodes)


# Callback to populate the page's dynamic components (filters, graph) based on the stored version
@app.callback(
    Output('predicate-filters-container', 'children'),
    Output('cytoscape-dag-preds', 'elements'),
    Input('session-biolink-version-store', 'data'), # Triggered by store change (inc. initial load)
    prevent_initial_call=False # Ensure this runs on load
)
def update_page_components(version_tag):
    """Populates filters and initial graph elements when version changes."""
    print(f"PREDICATES PAGE: Loading UI for version tag '{version_tag}'")
    if not version_tag:
        return "No Biolink version selected.", []

    version_data = get_biolink_data_for_version(version_tag)
    if not version_data:
        print(f"PREDICATES PAGE: Failed to load data for '{version_tag}'")
        return f"Error loading data for Biolink version '{version_tag}'.", []

    print(f"PREDICATES PAGE: Data loaded for '{version_tag}'. Populating UI.")
    # Generate filter controls using data for this version
    filter_controls = utils.get_filter_divs_preds(version_data['all_predicates'],
                                                  version_data['domains'],
                                                  version_data['ranges'])

    # Return filter controls and the initial elements for the graph
    return filter_controls, version_data['elements_predicates']




@app.callback(
    Output("cytoscape-dag-preds", "elements", allow_duplicate=True),
    Output("include-mixins-preds", "value"),
    Input("domain-filter", "value"),
    Input("range-filter", "value"),
    Input("include-mixins-preds", "value"),
    Input("node-search-preds", "value"),
    State('session-biolink-version-store', 'data'),  # READ version from store
    prevent_initial_call=True
)
def filter_graph_predicates(
    selected_domains: Optional[List[str]],
    selected_ranges: Optional[List[str]],
    include_mixins: List[str],
    search_nodes: Optional[List[str]],
    version_tag: str
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Filters predicate graph based on domain, range, mixins, and search."""

    # Get data from cache for the session's version
    version_data = get_biolink_data_for_version(version_tag)
    if not version_data or not version_data.get('bm'): # Check if data/bm loaded
         # Return empty elements and original mixin value if data is missing
         return [], include_mixins

    bm = version_data['bm'] # Use the BM instance for THIS version
    elements_predicates = version_data['elements_predicates'] # Use elements for THIS version

    include_mixins_updated = include_mixins # Start with user's selection
    if search_nodes:
        # If a mixin was searched, force 'include mixins' checkbox
        if any(bm.predicate_dag.nodes[node_id].get("is_mixin") for node_id in search_nodes):
            include_mixins_updated = ["include"]

    return utils.filter_graph(elements_predicates,
                              selected_domains,
                              selected_ranges,
                              include_mixins_updated,
                              search_nodes,
                              bm.predicate_dag,
                              bm), include_mixins_updated




# --- Run the App ---
if __name__ == '__main__':
    # Set debug=False for production deployments
    app.run(debug=True)