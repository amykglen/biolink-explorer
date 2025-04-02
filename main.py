from dash import Dash, dcc, html, Input, Output
import dash_cytoscape as cyto

from biolink_downloader import BiolinkDownloader

# Load additional layouts (including Dagre)
cyto.load_extra_layouts()

# Graph elements with domain and range properties
# elements = [
#     {"data": {"id": "Gene", "label": "Gene", "attributes": {"definition": "A gene is a unit of heredity.",
#                                                             "notes": "Essential for encoding proteins."}}},
#     {"data": {"id": "Disease", "label": "Disease",
#               "attributes": {"definition": "A disorder of structure or function in an organism."}}},
#     {"data": {"id": "Variant", "label": "Variant", "attributes": {"definition": "A variation in DNA sequence."}}},
#     {"data": {"source": "Gene", "target": "Disease", "domain": "Gene", "range": "Disease"}},
#     {"data": {"source": "Gene", "target": "Variant", "domain": "Gene", "range": "Variant"}},
#     {"data": {"source": "Variant", "target": "Disease", "domain": "Variant", "range": "Disease"}}
# ]

bd = BiolinkDownloader()
elements = bd.predicate_dag_dash

# Extract unique domain and range values for dropdowns
domains = sorted(set(bd.category_dag.nodes()))
ranges = sorted(set(bd.category_dag.nodes()))


# Initialize Dash app
app = Dash(__name__)

app.layout = html.Div([
    html.Div([
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
        ], style={"width": "20%", "display": "inline-block", "padding": "0 1%"}),
        html.Div([
            html.Label("Include Mixins?"),
            dcc.Checklist(
                id="include-mixins",
                options=[{"label": "", "value": "include"}],  # Empty label to show just the checkbox
                value=["include"],  # Default: Show all nodes/edges
            )
        ], style={"width": "20%", "display": "inline-block", "padding": "0 1%"})
    ], style={"margin-bottom": "20px", "display": "flex", "flex-direction": "row", "width": "100%"}),

    cyto.Cytoscape(
        id="cytoscape-dag",
        elements=elements,
        layout={"name": "dagre",
                "rankDir": "LR",  # Can be LR (left-to-right) or TB (top-to-bottom)
                "spacingFactor": 0.28,  # Adjust spacing between nodes
                "nodeDimensionsIncludeLabels": True,
                # "nodeSep": 50,  # Adjust horizontal spacing
                "rankSep": 700,  # Adjust vertical spacing (between ranks)
                },
        style={"width": "100%", "height": "800px"},
        stylesheet=[
            # Style for nodes: small black circles with labels to the right, with colored label backgrounds
            {"selector": "node", "style": {
                "background-color": "#e3eac8",
                "width": "label",
                "height": "label",
                "label": "data(label)",
                "color": "black",
                "shape": "round-rectangle",
                "text-valign": "center",
                "text-halign": "center",
                "font-size": "10px",
                "cursor": "pointer",
                "padding": "3px",
                "background-opacity": 0.7,
                "border-width": "1px",
                "border-color": "#c7d591",
                # "text-background-shape": "round-rectangle",
                # "text-background-color": "#eae0c8",  # Add a background color to the label
                # "text-background-opacity": 0.7,  # Adjust opacity as needed
                # "text-background-padding": "3px",  # Add padding around the label background
            }},
            # Special style for nodes with is_mixin = True
            {"selector": ".mixin",
             "style": {
                 "border-width": "0px",
                 "color": "grey",
                 "background-opacity": 0.4  # Increase opacity for mixin nodes
            }},
            {"selector": ".unspecific",
             "style": {
                 "background-color": "#dcdcdc",
                 "border-color": "#c2c2c2"
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
            }},
        ]
    ),

    # Info display area at the bottom
    html.Div(id="node-info", style={
        "position": "absolute",
        "bottom": "0",
        "width": "100%",
        "padding": "20px",
        "background-color": "#f9f9f9",
        "border-top": "1px solid #ddd",
        "text-align": "center",
        "font-size": "16px",
        "color": "black"
    })
])

# Callback to filter graph elements based on dropdown selections
@app.callback(
    Output("cytoscape-dag", "elements"),
    Input("domain-filter", "value"),
    Input("range-filter", "value"),
    Input("include-mixins", "value")
)
def filter_graph(selected_domains, selected_ranges, include_mixins):
    """Filter edges based on filter selections."""
    if "include" in include_mixins:
        relevant_elements = elements
    else:
        relevant_nodes = [element for element in elements if "id" in element["data"] and not element["data"].get("attributes", {})["is_mixin"]]
        relevant_node_ids = [element["data"]["id"] for element in relevant_nodes]
        relevant_edges = [element for element in elements if "source" in element["data"] and
                          element["data"]["source"] in relevant_node_ids and
                          element["data"]["target"] in relevant_node_ids]
        relevant_elements = relevant_nodes + relevant_edges

    if not selected_domains and not selected_ranges:
        return relevant_elements  # Show all elements if no filters applied

    selected_domains_set = bd.get_ancestors_nx(bd.category_dag, selected_domains)
    selected_ranges_set = bd.get_ancestors_nx(bd.category_dag, selected_ranges)

    filtered_nodes = [node for node in relevant_elements if "id" in node["data"] and
                      (not selected_domains or (node["data"]["attributes"].get("domain", "") in selected_domains_set)) and
                      (not selected_ranges or (node["data"]["attributes"].get("range", "") in selected_ranges_set))]
    filtered_node_ids = {node["data"]["id"] for node in filtered_nodes}

    filtered_edges = [edge for edge in relevant_elements if "source" in edge["data"] and
                      edge["data"]["source"] in filtered_node_ids and edge["data"]["target"] in filtered_node_ids]

    return filtered_nodes + filtered_edges


# Callback to display node info in the bottom area when a node is clicked
@app.callback(
    Output("node-info", "children"),
    Input("cytoscape-dag", "selectedNodeData")
)
def display_node_info(selected_nodes):
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


if __name__ == "__main__":
    app.run(debug=True)
