from dash import Dash, dcc, html, Input, Output
import dash_cytoscape as cyto

# Load additional layouts (including Dagre)
cyto.load_extra_layouts()

# Graph elements with domain and range properties
elements = [
    {"data": {"id": "Gene", "label": "Gene", "attributes": {"definition": "A gene is a unit of heredity.",
                                                            "notes": "Essential for encoding proteins."}}},
    {"data": {"id": "Disease", "label": "Disease",
              "attributes": {"definition": "A disorder of structure or function in an organism."}}},
    {"data": {"id": "Variant", "label": "Variant", "attributes": {"definition": "A variation in DNA sequence."}}},
    {"data": {"source": "Gene", "target": "Disease", "domain": "Gene", "range": "Disease"}},
    {"data": {"source": "Gene", "target": "Variant", "domain": "Gene", "range": "Variant"}},
    {"data": {"source": "Variant", "target": "Disease", "domain": "Variant", "range": "Disease"}}
]

# Extract unique domain and range values for dropdowns
domains = sorted(set(edge["data"]["domain"] for edge in elements if "source" in edge["data"]))
ranges = sorted(set(edge["data"]["range"] for edge in elements if "target" in edge["data"]))

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
        ], style={"width": "48%", "display": "inline-block", "padding": "0 1%"}),
        html.Div([
            html.Label("Filter by Range:"),
            dcc.Dropdown(
                id="range-filter",
                options=[{"label": r, "value": r} for r in ranges],
                multi=True,
                placeholder="Select one or more ranges..."
            )
        ], style={"width": "48%", "display": "inline-block", "padding": "0 1%"})
    ], style={"margin-bottom": "20px", "display": "flex", "flex-direction": "row", "width": "100%"}),

    cyto.Cytoscape(
        id="cytoscape-dag",
        elements=elements,
        layout={"name": "dagre",
                "rankDir": "LR",  # Can be LR (left-to-right) or TB (top-to-bottom)
                "spacingFactor": 0.5  # Adjust spacing between nodes
                },
        style={"width": "100%", "height": "800px"},
        stylesheet=[
            # Style for nodes: small black circles with labels to the right
            {"selector": "node", "style": {
                "background-color": "black",
                "width": "6px",
                "height": "6px",
                "label": "data(label)",
                "color": "black",
                "text-valign": "center",
                "text-halign": "left",
                "font-size": "8px",
                "text-margin-x": "-1px"
            }},
            # Style for edges: curved edges
            {"selector": "edge", "style": {
                "width": 0.5,
                "line-color": "black",
                "target-arrow-shape": "triangle",
                "target-arrow-color": "black",
                "arrow-scale": 0.3,
                "curve-style": "bezier",
                # "control-point-distances": "40px",
                # "control-point-weights": "0.5"
            }},
            # Optional: Style for selected nodes/edges
            {"selector": ":selected", "style": {
                "background-color": "#ff5500"
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
    Input("range-filter", "value")
)
def filter_edges(selected_domains, selected_ranges):
    """Filter edges based on domain and range selections."""
    if not selected_domains and not selected_ranges:
        return elements  # Show all elements if no filters applied

    filtered_edges = [
        edge for edge in elements if "source" in edge["data"] and (
                (not selected_domains or edge["data"]["domain"] in selected_domains) and
                (not selected_ranges or edge["data"]["range"] in selected_ranges)
        )
    ]

    # Get the unique node IDs from the filtered edges
    node_ids = {edge["data"]["source"] for edge in filtered_edges} | {edge["data"]["target"] for edge in filtered_edges}
    filtered_nodes = [node for node in elements if "id" in node["data"] and node["data"]["id"] in node_ids]

    return filtered_nodes + filtered_edges


# Callback to display node info in the bottom area when a node is clicked
@app.callback(
    Output("node-info", "children"),
    Input("cytoscape-dag", "selectedNodeData")
)
def display_node_info(selected_nodes):
    """Update the info display area CONTENT based on node selection."""
    # Add a print statement for debugging:
    print(f"selectedNodeData received: {selected_nodes}")

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
