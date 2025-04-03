from typing import Set, Optional

from dash import Dash, dcc, html, Input, Output
import dash_cytoscape as cyto

from biolink_downloader import BiolinkDownloader

# Load additional layouts (including Dagre)
cyto.load_extra_layouts()


# ---------------------------------------------- Helper functions ------------------------------------------------- #

def get_node_info(selected_nodes) -> any:
    """Update the info display area CONTENT based on node selection."""

    if selected_nodes: # Check if the list is not empty
        # A node (or nodes) is selected, display info for the first one
        node_data = selected_nodes[0] # Get the data of the first selected node

        if node_data and "id" in node_data: # Extra check just in case
            attributes = node_data.get("attributes", {})
            attribute_text = "\n".join(f"{k}: {v}" for k, v in attributes.items()) or "No attributes defined."
            node_id = node_data.get('id')
            link = None
            if node_id:
                url = f"https://biolink.github.io/biolink-model/{node_id}"
                link = html.A(f"View {node_id} Documentation", href=url, target="_blank",
                            style={"color": "blue", "text-decoration": "underline", "display": "block", "margin-top": "10px"})

            content = [
                html.H4(f"Information for {node_data.get('label', 'N/A')} ({node_id})"), # Show ID in title
                html.Pre(attribute_text, style={"text-align": "left", "max-width": "800px", "margin": "auto", "white-space": "pre-wrap"})
            ]
            if link:
                content.append(link)
            return content
        else:
            # Should not happen if selected_nodes is not empty and contains valid node data
             return "Error: Selected node data is invalid."
    else:
        # No node selected (list is empty), display the default text
        return "Click on a node to see info"

def filter_graph(element_set, selected_domains, selected_ranges, include_mixins, search_nodes, search_nodes_expanded):
    """Filter edges based on filter selections."""
    if "include" in include_mixins:
        relevant_elements = element_set
    else:
        relevant_nodes = [element for element in element_set if "id" in element["data"] and not element["data"].get("attributes", {})["is_mixin"]]
        relevant_node_ids = [element["data"]["id"] for element in relevant_nodes]
        relevant_edges = [element for element in element_set if "source" in element["data"] and
                          element["data"]["source"] in relevant_node_ids and
                          element["data"]["target"] in relevant_node_ids]
        relevant_elements = relevant_nodes + relevant_edges

    # First clear all node highlights from previous searches
    for element in element_set:
        if "id" in element["data"]:
            element["classes"] = element["classes"].replace("searched", "").strip()
            if "searched" in element["classes"]:
                print(element["classes"])
    if search_nodes:
        # Ensure the nodes the user searched for are highlighted visually
        for element in element_set:
            if "id" in element["data"] and element["data"]["id"] in search_nodes:
                element["classes"] += " searched"
        # Then filter down so we only show those nodes and their lineages
        relevant_nodes = [element for element in relevant_elements if "id" in element["data"] and element["data"]["id"] in search_nodes_expanded]
        relevant_node_ids = [element["data"]["id"] for element in relevant_nodes]
        relevant_edges = [element for element in element_set if "source" in element["data"] and
                          element["data"]["source"] in relevant_node_ids and
                          element["data"]["target"] in relevant_node_ids]
        relevant_elements = relevant_nodes + relevant_edges

    if not selected_domains and not selected_ranges:
        return relevant_elements  # Show all elements if no filters applied

    selected_domains_set = bd.get_ancestors_nx(bd.category_dag, selected_domains)
    selected_ranges_set = bd.get_ancestors_nx(bd.category_dag, selected_ranges)

    filtered_nodes = [node for node in relevant_elements if "id" in node["data"] and
                      (not selected_domains or "domain" not in node["data"]["attributes"] or node["data"]["attributes"]["domain"] in selected_domains_set) and
                      (not selected_ranges or "range" not in node["data"]["attributes"] or node["data"]["attributes"]["range"] in selected_ranges_set)]
    filtered_node_ids = {node["data"]["id"] for node in filtered_nodes}

    filtered_edges = [edge for edge in relevant_elements if "source" in edge["data"] and
                      edge["data"]["source"] in filtered_node_ids and edge["data"]["target"] in filtered_node_ids]

    return filtered_nodes + filtered_edges

def get_mixin_filter(filter_id: str, show_by_default: Optional[bool] = False) -> any:
    return html.Div([
            html.Label("Show mixins?"),
            dcc.Checklist(
                id=filter_id,
                options=[{"label": "", "value": "include"}],  # Empty label to show just the checkbox
                value=["include"] if show_by_default else [],
            )
        ], style={"width": "20%", "display": "inline-block", "padding": "0 1%"})

def get_search_filter(filter_id: str, node_names: Set[str]) -> any:
    item_type = "predicate" if "pred" in filter_id else "category"
    return html.Div([
        html.Label(f"Filter by {item_type}(s):"),
        dcc.Dropdown(
            id=filter_id,
            options=[{"label": node_name, "value": node_name} for node_name in node_names],
            multi=True,
            placeholder=f"Select items... (will filter to their lineages)"
        )
    ], style={"width": "30%", "display": "inline-block", "padding": "0 1%"})


# ----------------------------------------------- Style variables -------------------------------------------------- #


node_info_div_style = {
    "position": "absolute",
    "bottom": "0",
    "width": "100%",
    "padding": "20px",
    "background-color": "#f9f9f9",
    "border-top": "1px solid #ddd",
    "text-align": "center",
    "font-size": "12px",
    "color": "black"
}

main_styling = [
    # Style for nodes: small black circles with labels to the right, with colored label backgrounds
    {"selector": "node", "style": {
        "background-color": "#dae3b6",
        "width": "label",
        "height": "label",
        "label": "data(label)",
        "color": "black",
        "shape": "round-rectangle",
        "text-valign": "center",
        "text-halign": "center",
        "font-size": "14px",
        "cursor": "pointer",
        "padding": "3px",
        "background-opacity": 0.7,
        "border-width": "2px",
        "border-color": "#bece7f",
        "border-opacity": 0.7
    }},
    # Special style for nodes with certain classes
    {"selector": ".mixin",
     "style": {
         "border-width": "0px",
         "color": "grey",
         "background-opacity": 0.4  # Increase opacity for mixin nodes
    }},
    {"selector": ".unspecific",
     "style": {
         "background-color": "#e9e9e9",
         "border-color": "#cfcfcf"
     }},
    {"selector": ".searched",
     "style": {
         "border-width": "3px",
         "border-color": "#ff5500"
     }},
    # Style for edges: curved edges
    {"selector": "edge", "style": {
        "width": 0.5,
        "line-color": "#b4b4b4",
        "target-arrow-shape": "triangle",
        "target-arrow-color": "#b4b4b4",
        "arrow-scale": 0.6,
        'curve-style': 'bezier',
        # 'control-point-distances': [20, 40],
        # 'control-point-weights': [0.25, 0.75]
    }},
    # Optional: Style for selected nodes/edges
    {"selector": ":selected", "style": {
        "background-color": "#ff5500",
        # "border-width": "3px",
        "border-color": "#e64c00",
        # "border-cap": "round"
    }}
]

filters_wrapper_style = {"margin": "10px", "display": "flex", "flex-direction": "row", "width": "100%"}

layout_settings = {"name": "dagre",
                   "rankDir": "LR",  # Can be LR (left-to-right) or TB (top-to-bottom)
                   "spacingFactor": 0.34,  # Adjust spacing between nodes
                   "nodeDimensionsIncludeLabels": True,
                   # "nodeSep": 50,  # Adjust horizontal spacing
                   "rankSep": 640}  # Adjust vertical spacing (between ranks)


# --------------------------------------------------- App ---------------------------------------------------------- #


bd = BiolinkDownloader()
elements_predicates = bd.predicate_dag_dash
elements_categories = bd.category_dag_dash

# Extract unique domain and range values for dropdowns
domains = sorted(set(bd.category_dag.nodes()))
ranges = sorted(set(bd.category_dag.nodes()))
all_categories = sorted(set(bd.category_dag.nodes()))
all_predicates = sorted(set(bd.predicate_dag.nodes()))


# Initialize Dash app
app = Dash(__name__)

filters_div_preds = html.Div([
    get_search_filter("node-search-preds", all_predicates),
    get_mixin_filter("include-mixins-preds", show_by_default=True),
    html.Div([
        html.Label("Filter by Domain:"),
        dcc.Dropdown(
            id="domain-filter",
            options=[{"label": d, "value": d} for d in domains],
            multi=True,
            placeholder="Select one or more domains..."
        )
    ], style={"width": "20%", "display": "inline-block", "padding": "0 1%"}),
    html.Div([
        html.Label("Filter by Range:"),
        dcc.Dropdown(
            id="range-filter",
            options=[{"label": r, "value": r} for r in ranges],
            multi=True,
            placeholder="Select one or more ranges..."
        )
    ], style={"width": "20%", "display": "inline-block", "padding": "0 1%"})
], style=filters_wrapper_style)

filters_div_cats = html.Div([
    get_search_filter("node-search-cats", all_categories),
    get_mixin_filter("include-mixins-cats", show_by_default=False)
], style=filters_wrapper_style)


# Define our tabs
app.layout = html.Div([
    dcc.Tabs([
        dcc.Tab(label="Categories", children=[
            filters_div_cats,
            cyto.Cytoscape(
                id="cytoscape-dag-cats",
                elements=elements_categories,
                layout=layout_settings,
                style={"width": "100%", "height": "800px"},
                stylesheet=main_styling
            ),
            html.Div(id="node-info-cats", style=node_info_div_style)
        ]),
        dcc.Tab(label="Predicates", children=[
            filters_div_preds,
            cyto.Cytoscape(
                id="cytoscape-dag-preds",
                elements=elements_predicates,
                layout=layout_settings,
                style={"width": "100%", "height": "800px"},
                stylesheet=main_styling
            ),
            html.Div(id="node-info-preds", style=node_info_div_style)
        ])
    ]),
])


# Callbacks to filter graph elements based on dropdown/other selections

@app.callback(
    Output("cytoscape-dag-preds", "elements"),
    Input("domain-filter", "value"),
    Input("range-filter", "value"),
    Input("include-mixins-preds", "value"),
    Input("node-search-preds", "value")
)
def filter_graph_predicates(selected_domains, selected_ranges, include_mixins, search_nodes):
    if search_nodes:
        ancestors = bd.get_ancestors_nx(bd.predicate_dag, search_nodes)
        descendants = bd.get_descendants_nx(bd.predicate_dag, search_nodes)
        search_nodes_expanded = set(search_nodes).union(ancestors, descendants)
    else:
        search_nodes_expanded = set()
    return filter_graph(elements_predicates, selected_domains, selected_ranges, include_mixins, search_nodes, search_nodes_expanded)

@app.callback(
    Output("cytoscape-dag-cats", "elements"),
    Input("include-mixins-cats", "value"),
    Input("node-search-cats", "value")
)
def filter_graph_categories(include_mixins, search_nodes):
    if search_nodes:
        ancestors = bd.get_ancestors_nx(bd.category_dag, search_nodes)
        descendants = bd.get_descendants_nx(bd.category_dag, search_nodes)
        search_nodes_expanded = set(search_nodes).union(ancestors, descendants)
    else:
        search_nodes_expanded = set()
    return filter_graph(elements_categories, [], [], include_mixins, search_nodes, search_nodes_expanded)


# Callbacks to display node info in the bottom area when a node is clicked

@app.callback(
    Output("node-info-cats", "children"),
    Input("cytoscape-dag-cats", "selectedNodeData"),
)
def display_node_info_categories(selected_nodes):
    return get_node_info(selected_nodes)

@app.callback(
    Output("node-info-preds", "children"),
    Input("cytoscape-dag-preds", "selectedNodeData"),
)
def display_node_info_predicates(selected_nodes):
    return get_node_info(selected_nodes)






if __name__ == "__main__":
    app.run(debug=True)
