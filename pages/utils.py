import copy
from typing import Optional, List, Dict, Any, Set

import networkx as nx
from dash import html, dcc

from biolink_manager import BiolinkManager
from app import styles


# ----------------------------- Helper Methods ------------------------------ #

def get_node_info(selected_nodes: Optional[List[Dict[str, Any]]]) -> Any:
    """
    Generates the HTML content to display information about a selected node
    in a table format, including attributes and visual chips.

    Args:
        selected_nodes: Data provided by Cytoscape for the selected node(s).
                        Expected to be a list containing a single node's data dict.

    Returns:
        A list of Dash HTML components or a string message.
    """
    if not selected_nodes:
        return "Scroll to zoom in or out. Click on a node to see details."

    node_data = selected_nodes[0]

    if node_data and "id" in node_data:
        node_id = node_data.get("id")
        attributes = node_data.get("attributes", {})

        # Attributes to display in the table
        attributes_to_show = {
            "description": attributes.get("description", "-"),
            "notes": attributes.get("notes", "-"),
            "aliases": attributes.get("aliases", "-"),
        }
        table_rows = []
        for key, value in attributes_to_show.items():
            table_rows.append(
                html.Tr(
                    [
                        html.Td(
                            key,
                            style={
                                "text-align": "right",
                                "padding-right": "10px",
                                "vertical-align": "top",
                                "width": "150px",
                                "font-family": "monospace",
                            },
                        ),
                        # Ensure value is string for display
                        html.Td(str(value), style={"width": "auto", "fontSize": "16px"}),
                    ]
                )
            )

        # Build the title with ID, docs link, and chips
        url = f"https://biolink.github.io/biolink-model/{node_id}"
        title_content = [
            html.Span(f"{node_id} ",
                      style={"fontSize": "19px"}),
            html.A(
                "docs",
                href=url,
                target="_blank",
                style={
                    "color": styles.link_blue,
                    "fontSize": "14px",
                    "marginLeft": "3px",
                },
            ),
        ]
        if attributes.get("is_mixin"):
            title_content.append(
                html.Div(
                    "mixin",
                    style=styles.get_chip_style(styles.chip_peach, circular=True),
                )
            )
        if attributes.get("is_symmetric"):
            title_content.append(
                html.Div(
                    "symmetric",
                    style=styles.get_chip_style(styles.chip_purple, circular=True),
                )
            )

        # Build domain/range info if applicable (only for predicates)
        domain_range_info = []
        if "domain" in attributes: # If domain key exists, range key must exist
            domain = attributes.get("domain")
            range_val = attributes.get("range") # 'range' is a keyword, use different var name
            domain_range_info.extend([
                html.Span(
                    "domain: ",
                    style={
                        "marginRight": "1px",
                        "fontSize": "15px",
                        "color": "grey",
                    },
                ),
                html.Div(
                    domain if domain else "-",
                    style=styles.get_chip_style(styles.chip_green, domain),
                ),
                html.Span(" → ", style={"margin": "0 5px"}),
                html.Span(
                    "range: ",
                    style={
                        "marginLeft": "5px",
                        "marginRight": "1px",
                        "fontSize": "15px",
                        "color": "grey",
                    },
                ),
                html.Div(
                    range_val if range_val else "-",
                    style=styles.get_chip_style(styles.chip_green, range_val),
                ),
            ])

        # Assemble the final content list
        content = [
            html.H4(title_content, style={"margin": "0px 0px 9px 0px"}),
            html.Div(
                domain_range_info,
                style={
                    "display": "flex",
                    "justifyContent": "center",
                    "alignItems": "center",
                    "marginBottom": "5px",
                    "marginTop": "0px",
                },
            ),
            html.Table(
                table_rows,
                style={
                    "width": "800px",
                    "margin": "auto",
                    "textAlign": "left",
                },
            ),
        ]
        # Conditionally return content based on whether domain/range info was added
        return content if domain_range_info else [content[0], content[-1]]
    else:
        # Handle cases where selected node data might be invalid
        return "Error: Selected node data is invalid."


def filter_graph_to_certain_nodes(node_ids: Set[str], relevant_elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filters a list of Cytoscape elements to include only nodes from a
    given set of IDs and the edges connecting them.

    Args:
        node_ids: A set of node IDs to keep.
        relevant_elements: The full list of Cytoscape elements (nodes and edges).

    Returns:
        A filtered list of Cytoscape elements.
    """
    # Filter nodes based on the provided node_ids set
    relevant_nodes = [element for element in relevant_elements if
                      "id" in element["data"] and element["data"]["id"] in node_ids]
    relevant_node_ids = [element["data"]["id"] for element in relevant_nodes]
    # Filter edges: keep only those where both source and target are in relevant_node_ids
    relevant_edges = [element for element in relevant_elements if "source" in element["data"] and
                      element["data"]["source"] in relevant_node_ids and
                      element["data"]["target"] in relevant_node_ids]
    relevant_elements = relevant_nodes + relevant_edges
    return relevant_elements


def remove_mixins(element_set: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filters a list of Cytoscape elements to remove all mixin nodes
    and any edges connected only to mixins or between a mixin and non-mixin.

    Args:
        element_set: The list of Cytoscape elements (nodes and edges).

    Returns:
        A new list of Cytoscape elements containing only non-mixin nodes
        and the edges strictly connecting *between* those non-mixin nodes.
    """
    # Identify the IDs of all nodes that are *not* mixins.
    non_mixin_node_ids: Set[str] = {
        element["data"]["id"]
        for element in element_set
        # Check it's a node ('id' key exists in data dict)
        if "id" in element.get("data", {})
           and not element["data"].get("attributes", {}).get("is_mixin", False)
    }
    filtered_elements = filter_graph_to_certain_nodes(non_mixin_node_ids, element_set)

    return filtered_elements


def filter_graph(
    element_set: List[Dict[str, Any]],
    selected_domains: Optional[List[str]],
    selected_ranges: Optional[List[str]],
    include_mixins: List[str],
    search_nodes: Optional[List[str]],
    nx_dag: nx.DiGraph,
    bm: BiolinkManager
) -> List[Dict[str, Any]]:
    """
    Filters a set of Cytoscape graph elements based on various criteria:
    mixins, domain/range selections, and search terms.

    Args:
        element_set: The initial list of Cytoscape elements to filter.
        selected_domains: List of domain categories selected for filtering (predicates only).
        selected_ranges: List of range categories selected for filtering (predicates only).
        include_mixins: List indicating if mixins should be included (e.g., ['include']).
        search_nodes: List of node IDs directly selected in the search dropdown.
        nx_dag: The relevant NetworkX directed graph (either for categories or predicates).
        bm: The BiolinkManager instance to use (for the proper version).

    Returns:
        The filtered list of Cytoscape elements.
    """
    # --- Mixin Filtering ---
    if "include" in include_mixins:
        relevant_elements = element_set
    else:
        relevant_elements = remove_mixins(element_set)

    # --- Search Filtering ---
    # First, clear previous search highlights and apply new ones
    relevant_elements = copy.deepcopy(relevant_elements)
    for element in relevant_elements:
        if "id" in element.get("data", {}):
            # Remove 'searched' class safely
            current_classes = element.get("classes", "").split()
            filtered_classes = [c for c in current_classes if c != "searched"]
            element["classes"] = " ".join(filtered_classes)

            # Add 'searched' class if this node was directly searched
            if search_nodes and element["data"]["id"] in search_nodes:
                element["classes"] = (element["classes"] + " searched").lstrip()

    # If search terms are active, filter down to the expanded lineage
    if search_nodes:
        # Calculate the full lineage (ancestors + descendants) for search terms
        ancestors = bm.get_ancestors(nx_dag, search_nodes)
        descendants = bm.get_descendants(nx_dag, search_nodes)
        search_nodes_expanded = set(search_nodes).union(ancestors, descendants)

        relevant_elements = filter_graph_to_certain_nodes(search_nodes_expanded, relevant_elements)

    # --- Domain/Range Filtering (for Predicates) ---
    if selected_domains or selected_ranges:
        # Get ancestors for selected domains/ranges for hierarchical filtering
        selected_domains_set = bm.get_ancestors(bm.category_dag, selected_domains)
        selected_ranges_set = bm.get_ancestors(bm.category_dag, selected_ranges)

        # Filter nodes (predicates) based on domain/range matching
        filtered_node_ids = {node["data"]["id"] for node in relevant_elements if "id" in node["data"] and
                             (not selected_domains or not node["data"]["attributes"].get("domain") or
                              node["data"]["attributes"]["domain"] in selected_domains_set) and
                             (not selected_ranges or not node["data"]["attributes"].get("range") or
                              node["data"]["attributes"]["range"] in selected_ranges_set)}
        relevant_elements = filter_graph_to_certain_nodes(filtered_node_ids, relevant_elements)

    # --- Final Mixin Filtering, to handle any ancestors/descendants added ---
    if not include_mixins:
        relevant_elements = remove_mixins(relevant_elements)

    return relevant_elements


def get_mixin_filter(filter_id: str, show_by_default: bool = False) -> html.Div:
    """Creates a 'Show mixins?' checklist component."""
    return html.Div(
        [
            html.Label("Show mixins?"),
            dcc.Checklist(
                id=filter_id,
                options=[{"label": "", "value": "include"}], # Label-less checkbox
                value=["include"] if show_by_default else [],
            ),
        ],
        style={"width": "20%", "display": "inline-block", "padding": "0 1%"},
    )


def get_search_filter(filter_id: str, node_names: List[str]) -> html.Div:
    """Creates a search dropdown component."""
    item_type = "predicate" if "pred" in filter_id else "category"
    return html.Div(
        [
            html.Label(f"Search for {item_type}(s):"),
            dcc.Dropdown(
                id=filter_id,
                options=[{"label": name, "value": name} for name in sorted(node_names)],
                multi=True,
                placeholder=f"Select items... (filters to lineages)",
            ),
        ],
        style={"width": "30%", "display": "inline-block", "padding": "0 1%"},
    )

def get_filter_divs_preds(all_predicates: List[str], domains: List[str], ranges: List[str]) -> html.Div:
    """Generates the filter controls Div for the Predicates tab."""
    filter_div_style = {"width": "20%", "display": "inline-block", "padding": "0 1%"}
    return html.Div(
        [
            get_search_filter("node-search-preds", all_predicates or []),
            get_mixin_filter("include-mixins-preds", show_by_default=True),
            html.Div(
                [
                    html.Label("Filter by Domain (hierarchical):"),
                    dcc.Dropdown(
                        id="domain-filter",
                        options=[{"label": d, "value": d} for d in domains or []],
                        multi=True,
                        placeholder="Select one or more domains...",
                    ),
                ],
                style=filter_div_style,
            ),
            html.Div(
                [
                    html.Label("Filter by Range (hierarchical):"),
                    dcc.Dropdown(
                        id="range-filter",
                        options=[{"label": r, "value": r} for r in ranges or []],
                        multi=True,
                        placeholder="Select one or more ranges...",
                    ),
                ],
                style=filter_div_style,
            ),
        ],
        style=styles.filters_wrapper_style,
    )

def get_filter_divs_cats(all_categories: List[str]) -> html.Div:
    """Generates the filter controls Div for the Categories tab."""
    return html.Div(
        [
            get_search_filter("node-search-cats", all_categories or []),
            get_mixin_filter("include-mixins-cats", show_by_default=False),
        ],
        style=styles.filters_wrapper_style,
    )


