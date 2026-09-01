import copy
import logging
import os
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx
from dash import Dash, Input, Output, dcc, html, State

from biolink_manager import BiolinkManager, get_biolink_github_tags

# Import custom modules/classes
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from styles import Styles


class BiolinkDashApp:
    """
    A Dash application for visualizing and exploring Biolink Model category
    and predicate hierarchies.

    Allows users to view relationship graphs, filter by various criteria
    (mixins, domain/range, search), and view details about selected nodes.
    It can fetch data for different Biolink Model versions.
    """

    def __init__(self) -> None:
        """Initializes the BiolinkDashApp."""
        self.bm_cache : Dict[str, any] = dict()
        self.root_category = "NamedThing"
        self.root_predicate = "related_to"

        self.styles: Styles = Styles()

        self.app: Dash = Dash(__name__, title="Biolink Explorer", suppress_callback_exceptions=True)
        self.app.layout = self.get_layout()
        self.register_callbacks()

    # ------------------------- Data Loading and Update ------------------------- #

    def get_biolink_data_for_version(self, version: str) -> Dict[str, any]:
        """
        Fetches and processes Biolink data for the specified version using
        BiolinkManager. Updates a cache with data for different Biolink
        versions.
        """
        if version not in self.bm_cache:
            try:
                bm = BiolinkManager(biolink_version=version)
            except Exception as load_error:
                # Some versions may fail to load (e.g. an unparsable schema). Cache
                # the failure so we don't retry every callback, and degrade gracefully.
                logging.error(f"Failed to load Biolink version {version}: {load_error}")
                self.bm_cache[version] = None
                return None
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
            self.bm_cache[version] = {"bm": bm,
                                      "elements_predicates": elements_predicates,
                                      "elements_categories": elements_categories,
                                      "domains": domains,
                                      "ranges": ranges,
                                      "all_categories": all_categories,
                                      "all_predicates": all_predicates}
        return self.bm_cache[version]

    # -------------------------- Layout Generation Methods -------------------------- #

    def get_layout(self) -> html.Div:
        """Generates the main layout Div for the Dash application."""

        # Determine initial version and pre-load/cache its data
        all_version_tags = get_biolink_github_tags()
        initial_version_tag = all_version_tags[0]
        self.get_biolink_data_for_version(initial_version_tag)

        return html.Div([
            # Store for the user's selected version tag
            dcc.Store(id='session-biolink-version-store', data=initial_version_tag),  # Initialize with default
            dcc.Input(id='tab-switch-trigger', style={'display': 'none'}, value=0),

            # Header section with title and version selector
            html.Div([
                html.Div([
                    html.Span("Biolink Model Explorer", style={
                        "fontSize": "18px",
                        "fontWeight": 700,
                        "color": self.styles.text,
                        "letterSpacing": "-0.01em",
                    }),
                ]),
                html.Div([
                    html.Label([
                        "Showing ",
                        html.Div(id="biolink-version-link", style={"display": "inline-block"}),
                        " version:"
                    ], style={"marginRight": "8px", "color": self.styles.text_muted, "fontSize": "14px"}),
                    dcc.Dropdown(
                        id="biolink-version-input",
                        options=[{"label": tag, "value": tag} for tag in all_version_tags],
                        value=initial_version_tag,
                        clearable=False,
                        style={"width": "130px", "marginRight": "5px"}
                    ),
                ], style={
                    "display": "flex",
                    "alignItems": "center"
                })
            ], style={
                "display": "flex",
                "justifyContent": "space-between",
                "alignItems": "center",
                "padding": "12px 18px",
                "backgroundColor": self.styles.surface,
                "borderBottom": f"1px solid {self.styles.border_subtle}",
            }),
            # Main content area, updated by callback
            html.Div(id="main-content", children=self.get_main_content())
        ], style={
            "fontFamily": self.styles.font_family,
            "backgroundColor": self.styles.bg,
            "color": self.styles.text,
            "minHeight": "100vh",
        })

    def get_main_content(self) -> html.Div:
        """Generates the main content area including tabs and graphs."""
        # Each tab is a horizontal row: the graph column (filters + tree) on the left,
        # and the node-detail panel on the right.
        tab_row_style = {
            "display": "flex",
            "flexDirection": "row",
            "height": "calc(100vh - 110px)",
        }
        graph_col_style = {
            "display": "flex",
            "flexDirection": "column",
            "flex": "1 1 auto",
            "minWidth": "0",
            "height": "100%",
        }
        tree_style = {"width": "100%", "height": "100%", "flex": "1 1 auto",
                      "minHeight": "0", "backgroundColor": self.styles.bg, "overflow": "hidden"}

        def tab_body(filters_id, tree_id, info_id):
            return html.Div(
                style=tab_row_style,
                children=[
                    html.Div(
                        style=graph_col_style,
                        children=[
                            html.Div(id=filters_id),  # filters populated by callback
                            html.Div(id=tree_id, className="tree-container", style=tree_style),
                        ],
                    ),
                    html.Div(id=info_id, style=self.styles.detail_panel_style,
                             children=self.get_node_info(None)),
                ],
            )

        return html.Div(
            id="app-container",
            children=[
                # Stores holding the (filtered) graph elements and the selected node,
                # driving the D3 tree renderer (assets/tree.js) and the info panels.
                dcc.Store(id="elements-cats"),
                dcc.Store(id="elements-preds"),
                dcc.Store(id="selected-cats"),
                dcc.Store(id="selected-preds"),
                dcc.Store(id="render-signal"),  # clientside render callback target
                dcc.Tabs(
                    id="tabs",
                    value="tab-1",
                    children=[
                        dcc.Tab(label="Categories", value="tab-1",
                                children=[tab_body("category-filters-container", "tree-cats", "node-info-cats")]),
                        dcc.Tab(label="Predicates", value="tab-2",
                                children=[tab_body("predicate-filters-container", "tree-preds", "node-info-preds")]),
                        dcc.Tab(label="Info", value="tab-3", children=self.get_app_info())
                    ]),
        ])

    def get_filter_divs_preds(self, all_predicates: List[str], domains: List[str], ranges: List[str]) -> html.Div:
        """Generates the filter controls Div for the Predicates tab."""
        filter_div_style = {"width": "20%", "display": "inline-block", "padding": "0 1%"}
        return html.Div(
            [
                self.get_search_filter("node-search-preds", all_predicates or []),
                self.get_mixin_filter("include-mixins-preds", show_by_default=True),
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
            style=self.styles.filters_wrapper_style,
        )

    def get_filter_divs_cats(self, all_categories: List[str]) -> html.Div:
        """Generates the filter controls Div for the Categories tab."""
        return html.Div(
            [
                self.get_search_filter("node-search-cats", all_categories or []),
                self.get_mixin_filter("include-mixins-cats", show_by_default=False),
            ],
            style=self.styles.filters_wrapper_style,
        )

    def get_app_info(self) -> List[html.Div]:
        """Generates the content for the 'Info' tab."""
        chip_primary = self.get_chip_style(
            self.styles.accent_tint,
            border=f"2px solid {self.styles.accent}",
        )
        chip_noncanonical = self.get_chip_style(
            self.styles.surface,
            border=f"1.5px dashed {self.styles.noncanonical_border}",
            text_color=self.styles.noncanonical_text,
        )
        chip_grey = self.get_chip_style(
            self.styles.node_grey,
            border=f"1.5px solid {self.styles.node_border_grey}",
            text_color=self.styles.text_muted,
        )
        chip_mixin = self.get_chip_style(
            self.styles.accent_tint,
            opacity=self.styles.mixin_opacity,
            border=f"2px solid {self.styles.accent}",
        )

        info_content = [
            html.Div(
                style={
                    "padding": "30px",
                    "maxWidth": "800px",
                    "margin": "0 auto",
                    "marginBottom": "20px",
                    "overflowY": "auto",
                    "height": "calc(100vh - 150px)", # Adjust based on header/tabs
                },
                children=[
                    html.H3("About this app"),
                    html.P(
                        [
                            "This application is designed to visualize and explore the relationships between ",
                            "categories (i.e. node types) and predicates (i.e., edge types) within the ",
                            html.A(
                                "Biolink Model",
                                href="https://biolink.github.io/biolink-model",
                                target="_blank",
                                style=self.styles.hyperlink_style,
                            ),
                            ", an open-source schema for biomedical knowledge graphs developed by the ",
                            html.A(
                                "NCATS Biomedical Data Translator",
                                href="https://ncats.nih.gov/research/research-activities/translator",
                                target="_blank",
                                style=self.styles.hyperlink_style,
                            ),
                            " consortium.",
                        ]
                    ),
                    html.P(
                        [
                            "All Biolink logic is powered by the official ",
                            html.A(
                                "Biolink Model Toolkit (bmt)",
                                href="https://github.com/biolink/biolink-model-toolkit",
                                target="_blank",
                                style=self.styles.hyperlink_style,
                            ),
                            ", and any Biolink Model version can be loaded on the fly.",
                        ]
                    ),
                    html.H4("Using the tabs:"),
                    html.P(
                        """
                        The 'Categories' tab displays the hierarchy of concept categories in the Biolink Model.
                        You can use the filters at the top to focus on specific
                        categories or include/exclude mixin categories.
                        """
                    ),
                    html.P(
                        """
                        The 'Predicates' tab shows the hierarchy of relationship predicates in the Biolink Model.
                        All predicates are shown; canonical predicates (the Translator-preferred direction of a
                        relationship) are visually distinguished from non-canonical ones (see the legend below).
                        Use the filters at the top to focus on specific predicates, include/exclude mixin predicates,
                        and to filter predicates based on their domain and range.
                        """
                    ),
                    html.H4("Interacting with the graphs:"),
                    html.P(
                        [
                            "Clicking on a node in either graph will display details from the ",
                            html.A(
                                "Biolink Model YAML",
                                href=f"https://github.com/biolink/biolink-model/blob/master/biolink-model.yaml",
                                target="_blank",
                                style=self.styles.hyperlink_style,
                            ),
                            " about that item in the area below the graph. Scroll over the graph to zoom in or out.",
                        ]
                    ),
                    html.H5("Legend:"),
                    html.P(
                        [
                            html.Div("SomeCategory", style=chip_primary),
                            html.Div("canonical_predicate", style=chip_primary),
                            " Categories and canonical predicates are shown with a solid accent border.",
                        ]
                    ),
                    html.P(
                        [
                            html.Div("noncanonical_predicate", style=chip_noncanonical),
                            " Non-canonical predicates (e.g. the non-preferred direction of a "
                            "relationship) have a dashed, muted border.",
                        ]
                    ),
                    html.P(
                        [
                            html.Div("some_predicate", style=chip_grey),
                            " Predicates with a non-specific domain and range (either NamedThing or not provided) are grey.",
                        ]
                    ),
                    html.P(
                        [
                            html.Div("SomeMixin", style=chip_mixin),
                            " Mixins are faded.",
                        ]
                    ),
                    html.H4("Search functionality:"),
                    html.P(
                        """
                        You can use the search bar (top left) to find specific categories
                        or predicates. The graph will filter itself to show only the item(s) you selected and
                        their lineages (ancestors and descendants).
                        """
                    ),
                    html.H4("'Show mixins?' option:"),
                    html.P(
                        """
                        Mixin categories/predicates allow for multiple inheritance. Use the 'Show mixins?' checkbox to
                        include or exclude these items from the graph. When you opt to include mixins, the graph
                        will be a directed acyclic graph; when you exclude mixins, it will be a tree.
                        """
                    ),
                    html.P(
                        """
                        Note that if you search for an item that is a mixin but 'Show mixins?' is not selected, the app
                        will override 'Show mixins?' and set it to True.
                        """
                    ),
                    html.H4("Domain and Range Filters (Predicates Tab):"),
                    html.P(
                        """
                        On the 'Predicates' tab, you'll find dropdown menus labeled 'Filter by Domain' and 'Filter by Range'.
                        These filters allow you to narrow down the displayed predicates based on the types of categories
                        that are involved in the relationship.
                        """
                    ),
                    html.P(
                        """
                        You can use these filters independently or together to explore specific types of relationships
                        between different categories in the Biolink Model. For instance, you could filter for predicates
                        that have 'Disease' as a domain and 'Symptom' as a range to see predicates that can be used to
                        link diseases to their symptoms.
                        """
                    ),
                    html.H5("Domain Filter:"),
                    html.P(
                        [
                            "The 'Domain' of a predicate refers to the category of entity that is the ",
                            html.B("subject"),
                            " or source of the relationship. For example, for the predicate 'has_phenotype', the domain might be "
                            "'Disease' because a disease can have a phenotype. ",
                        ]
                    ),
                    html.P(
                        [
                            "When you select one or more categories in the ",
                            "'Filter by Domain' dropdown, the graph will only show predicates where the subject of the ",
                            "relationship belongs to one of the selected categories (or their ancestors ",
                            "in the category hierarchy). This makes this a convenient way of seeing all predicates that could ",
                            "describe an edge in a knowledge graph that connects a Disease to some other node, for instance.",
                        ]
                    ),
                    html.H5("Range Filter:"),
                    html.P(
                        [
                            "The 'Range' of a predicate refers to the category of entity that is the ",
                            html.B("object"),
                            " or target of the relationship. For example, for the predicate 'has_phenotype', the range might be ",
                            "'Phenotype' because a disease can have a phenotype. ",
                        ]
                    ),
                    html.P(
                        [
                            "When you select one or more categories in the ",
                            "'Filter by Range' dropdown, the graph will only show predicates where the object of the ",
                            "relationship belongs to one of the selected categories (or their ancestors ",
                            "in the category hierarchy). This makes this a convenient way of seeing all predicates that could ",
                            "describe an edge in a knowledge graph that connects some node to a Phenotype, for instance.",
                        ]
                    ),
                    html.H4("Creators"),
                    html.P(
                        [
                            "This application was developed by ",
                            html.A(
                                "Amy Glen",
                                href="https://github.com/amykglen",
                                target="_blank",
                                style=self.styles.hyperlink_style,
                            ),
                            " at ",
                            html.A(
                                "Phenome Health",
                                href="https://www.phenomehealth.org",
                                target="_blank",
                                style=self.styles.hyperlink_style,
                            ),
                            ". Its source code lives ",
                            html.A(
                                "here",
                                href="https://github.com/amykglen/biolink-explorer",
                                target="_blank",
                                style=self.styles.hyperlink_style,
                            ),
                            ".",
                        ]
                    ),
                ],
            )
        ]
        return info_content

    # ----------------------------- Helper Methods ------------------------------ #

    def get_node_info(self, selected_nodes: Optional[List[Dict[str, Any]]]) -> Any:
        """
        Generates the content of the right-hand detail panel for the selected node:
        a header (id, docs link, status badges), a domain -> range / inverse section
        for predicates, and description / notes / aliases sections.

        Args:
            selected_nodes: A list containing a single selected node's data dict
                            (``{"id": ..., "attributes": {...}}``), or falsy if none.
        """
        if not selected_nodes or not selected_nodes[0] or "id" not in selected_nodes[0]:
            return html.Div(
                "Click a node in the graph to see its details.",
                style={"color": self.styles.text_muted, "fontSize": "14px",
                       "lineHeight": "1.5", "marginTop": "4px"},
            )

        node_data = selected_nodes[0]
        node_id = node_data.get("id")
        attributes = node_data.get("attributes", {})
        is_predicate = "domain" in attributes
        url = f"https://biolink.github.io/biolink-model/{node_id}"

        def chip(text: str, color: str, text_color: Optional[str] = None,
                 chip_value: Any = "value_present") -> html.Div:
            return html.Div(text, style=self.get_chip_style(
                color, chip_value=chip_value, text_color=text_color, margin_left="0"))

        # --- Status badges ---
        badges = []
        if is_predicate:
            if attributes.get("is_canonical"):
                badges.append(chip("canonical", self.styles.chip_canonical, self.styles.chip_canonical_text))
            else:
                badges.append(chip("non-canonical", self.styles.chip_grey, self.styles.text_muted))
        if attributes.get("is_mixin"):
            badges.append(chip("mixin", self.styles.chip_peach, self.styles.chip_peach_text))
        if attributes.get("is_symmetric"):
            badges.append(chip("symmetric", self.styles.chip_purple, self.styles.chip_purple_text))

        header_children = [
            html.Div(node_id, style={"fontSize": "20px", "fontWeight": 700,
                                     "lineHeight": "1.25", "wordBreak": "break-word",
                                     "color": self.styles.text}),
            html.A("View in Biolink docs ↗", href=url, target="_blank",
                   style={**self.styles.hyperlink_style, "fontSize": "13px",
                          "display": "inline-block", "marginTop": "5px"}),
        ]
        if badges:
            header_children.append(
                html.Div(badges, style={"display": "flex", "flexWrap": "wrap",
                                        "gap": "6px", "marginTop": "13px"}))

        sections = [html.Div(header_children)]

        # --- Predicate relationship (domain -> range, inverse) ---
        if is_predicate:
            domain = attributes.get("domain")
            range_val = attributes.get("range")
            relationship = html.Div(
                [
                    chip(domain if domain else "—", self.styles.chip_domain, chip_value=domain),
                    html.Span("→", style={"margin": "0 9px", "color": self.styles.text_muted,
                                               "fontSize": "16px"}),
                    chip(range_val if range_val else "—", self.styles.chip_domain, chip_value=range_val),
                ],
                style={"display": "flex", "alignItems": "center", "flexWrap": "wrap", "gap": "4px"},
            )
            sections.append(self.get_detail_section("Domain → Range", relationship))
            inverse_val = attributes.get("inverse")
            if inverse_val:
                sections.append(self.get_detail_section(
                    "Inverse predicate", chip(inverse_val, self.styles.chip_grey, self.styles.text)))

        # --- Free-text metadata ---
        sections.append(self.get_detail_section("Description", self.format_detail_value(attributes.get("description"))))
        sections.append(self.get_detail_section("Notes", self.format_detail_value(attributes.get("notes"))))
        sections.append(self.get_detail_section("Aliases", self.format_detail_value(attributes.get("aliases"))))

        return sections

    def get_detail_section(self, label: str, value_component: Any) -> html.Div:
        """A labeled block in the detail panel (small uppercase label + value)."""
        return html.Div([
            html.Div(label, style=self.styles.detail_label_style),
            value_component,
        ])

    def format_detail_value(self, value: Any) -> Any:
        """Renders a metadata value (string, list, or missing) for the detail panel."""
        if value is None or value == "" or value == []:
            return html.Div("—", style={**self.styles.detail_value_style,
                                             "color": self.styles.text_muted})
        if isinstance(value, list):
            if len(value) == 1:
                return html.Div(str(value[0]), style=self.styles.detail_value_style)
            return html.Ul(
                [html.Li(str(item), style={"marginBottom": "4px"}) for item in value],
                style={**self.styles.detail_value_style, "paddingLeft": "18px", "margin": "0"},
            )
        return html.Div(str(value), style=self.styles.detail_value_style)

    @staticmethod
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

    def remove_mixins(self, element_set: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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
        filtered_elements = self.filter_graph_to_certain_nodes(non_mixin_node_ids, element_set)

        return filtered_elements

    def filter_graph(
        self,
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
            relevant_elements = self.remove_mixins(element_set)

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

            relevant_elements = self.filter_graph_to_certain_nodes(search_nodes_expanded, relevant_elements)

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
            relevant_elements = self.filter_graph_to_certain_nodes(filtered_node_ids, relevant_elements)

        # --- Final Mixin Filtering, to handle any ancestors/descendants added ---
        if not include_mixins:
            relevant_elements = self.remove_mixins(relevant_elements)

        return relevant_elements

    @staticmethod
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

    @staticmethod
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

    def get_chip_style(
        self,
        color: str,
        chip_value: Optional[Any] = "value_present", # Use a sentinel instead of None directly
        opacity: Optional[float] = None,
        border: Optional[str] = None,
        circular: bool = False,
        text_color: Optional[str] = None,
        margin_left: str = "8px",
    ) -> Dict[str, Any]:
        """
        Generates a style dictionary for visual 'chip' elements.
        Grey out chip if value is None or the root category.
        """
        final_color = color
        final_text_color = text_color or self.styles.text
        if chip_value is None or chip_value == self.root_category:
            final_color = self.styles.chip_grey
            final_text_color = self.styles.text_muted

        chip_style: Dict[str, Any] = {
            "padding": "3px 10px",
            "borderRadius": "999px" if circular else "6px",
            "backgroundColor": final_color,
            "marginLeft": margin_left,
            "fontSize": "13.5px",
            "fontWeight": 500,
            "display": "inline-block",
            "color": final_text_color,
        }
        if opacity is not None:
            chip_style["opacity"] = opacity
        if border:
            chip_style["border"] = border
        return chip_style

    # --------------------------- Callback Registration --------------------------- #

    def register_callbacks(self):

        # Clientside callback: (re)render each D3 tree whenever its elements change or
        # a tab switch (re)mounts its container. Rendering while a tab is hidden is
        # harmless — the SVG viewBox auto-fits once the container becomes visible.
        self.app.clientside_callback(
            """
            function(catElements, predElements, tabTrigger) {
                function draw(containerId, elements, selectedStoreId, graphType) {
                    function go() {
                        var el = document.getElementById(containerId);
                        if (el && window.BiolinkTree) {
                            window.BiolinkTree.render(containerId, elements || [],
                                { selectedStoreId: selectedStoreId, graphType: graphType });
                            return true;
                        }
                        return false;
                    }
                    if (!go()) { setTimeout(go, 60); setTimeout(go, 200); }
                }
                draw("tree-cats", catElements, "selected-cats", "cats");
                draw("tree-preds", predElements, "selected-preds", "preds");
                return window.dash_clientside.no_update;
            }
            """,
            Output("render-signal", "data"),
            Input("elements-cats", "data"),
            Input("elements-preds", "data"),
            Input("tab-switch-trigger", "value"),
        )

        # Callbacks to filter graph elements based on dropdown/other selections

        @self.app.callback(
            Output("elements-preds", "data", allow_duplicate=True),
            Output("include-mixins-preds", "value"),
            Input("domain-filter", "value"),
            Input("range-filter", "value"),
            Input("include-mixins-preds", "value"),
            Input("node-search-preds", "value"),
            Input('tab-switch-trigger', 'value'),  # Trigger on tab switch
            State('session-biolink-version-store', 'data'),  # READ version from store
            prevent_initial_call=True  # Prevent initial call for filtering
        )
        def filter_graph_predicates(
            selected_domains: Optional[List[str]],
            selected_ranges: Optional[List[str]],
            include_mixins: List[str],
            search_nodes: Optional[List[str]],
            tab_trigger: int,
            version_tag: str
        ) -> Tuple[List[Dict[str, Any]], List[str]]:
            """Filters predicate graph based on domain, range, mixins, and search."""

            # Get data from cache for the session's version
            version_data = self.get_biolink_data_for_version(version_tag)
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

            return (self.filter_graph(elements_predicates,
                                      selected_domains,
                                      selected_ranges,
                                      include_mixins_updated,
                                      search_nodes,
                                      bm.predicate_dag,
                                      bm),
                    include_mixins_updated)

        @self.app.callback(
            Output("elements-cats", "data", allow_duplicate=True),
            Output("include-mixins-cats", "value"),
            Input("include-mixins-cats", "value"),
            Input("node-search-cats", "value"),
            Input('tab-switch-trigger', 'value'),  # Trigger on tab switch
            State('session-biolink-version-store', 'data'),  # READ version from store
            prevent_initial_call=True  # Prevent initial call for filtering
        )
        def filter_graph_categories(
            include_mixins: List[str],
            search_nodes: Optional[List[str]],
            tab_trigger: int,
            version_tag: str
        ) -> Tuple[List[Dict[str, Any]], List[str]]:
            """Filters category graph based on mixins and search."""

            # Get data from cache for the session's version
            version_data = self.get_biolink_data_for_version(version_tag)
            if not version_data or not version_data.get('bm'): # Check if data/bm loaded
                 return [], include_mixins
            bm = version_data['bm'] # Use the BM instance for THIS version
            elements_categories = version_data['elements_categories'] # Use elements for THIS version

            include_mixins_updated = include_mixins # Start with user's selection
            if search_nodes:
                # If a mixin was searched, force 'include mixins' checkbox
                if any(bm.category_dag.nodes[node_id].get("is_mixin") for node_id in search_nodes):
                    include_mixins_updated = ["include"]

            return (self.filter_graph(elements_categories,
                                      [],
                                      [],
                                      include_mixins_updated,
                                      search_nodes,
                                      bm.category_dag,
                                      bm),
                    include_mixins_updated)

        # Callback to display node info (Categories Tab)
        @self.app.callback(
            Output("node-info-cats", "children"),
            Input("selected-cats", "data"),
        )
        def display_node_info_categories(selected_nodes: Optional[List[Dict[str, Any]]]) -> Any:
            """Displays information for the selected category node."""
            return self.get_node_info(selected_nodes)

        # Callback to display node info (Predicates Tab)
        @self.app.callback(
            Output("node-info-preds", "children"),
            Input("selected-preds", "data"),
        )
        def display_node_info_predicates(selected_nodes: Optional[List[Dict[str, Any]]]) -> Any:
            """Displays information for the selected predicate node."""
            return self.get_node_info(selected_nodes)

        # Update the session store when version dropdown changes
        @self.app.callback(
            Output('session-biolink-version-store', 'data'),
            Input('biolink-version-input', 'value')
            # Note: No prevent_initial_call=True, we want it to run on load
            # with the initial dropdown value
        )
        def update_session_version(version_tag):
            # if not version_tag:
            #     return dash.no_update # Should not happen with clearable=False
            # Ensure data is loaded into cache (won't reload if already present)
            self.get_biolink_data_for_version(version_tag)
            # Store the selected version tag in the user's session
            return version_tag

        # Update graphs, filter options, and links when session version changes
        @self.app.callback(
            Output('elements-cats', 'data'),
            Output('elements-preds', 'data'),
            Output('category-filters-container', 'children'),
            Output('predicate-filters-container', 'children'),
            Output('biolink-version-link', 'children'),
            Input('session-biolink-version-store', 'data') # Triggered by store change
        )
        def update_ui_for_version(version_tag):
            if not version_tag:
                return [], [], [], [], html.A() # Handle initial or error state

            # Get data from cache for the session's version
            version_data = self.get_biolink_data_for_version(version_tag)
            if not version_data: # Handle case where loading failed
                 return [], [], [], [], html.A("Error loading version", href="#")

            # Generate filter divs using data for this version
            cat_filters = self.get_filter_divs_cats(version_data['all_categories'])
            pred_filters = self.get_filter_divs_preds(version_data['all_predicates'],
                                                      version_data['domains'],
                                                      version_data['ranges'])

            # Generate version link
            # Use actual version from bm instance if possible, otherwise use tag
            actual_version = version_tag
            if version_data.get('bm'):
                actual_version = version_data['bm'].biolink_version

            version_link = html.A(
                    "Biolink Model",
                    # Use actual version for link text if different from tag?
                    href=f"https://github.com/biolink/biolink-model/blob/{version_tag}/biolink-model.yaml", # Link using tag
                    target="_blank",
                    style=self.styles.hyperlink_style
                )

            # Return updated elements and filter components
            return (version_data['elements_categories'],
                    version_data['elements_predicates'],
                    cat_filters,
                    pred_filters,
                    version_link)

        # Callback to update the hidden trigger on tab switch
        @self.app.callback(
            Output('tab-switch-trigger', 'value'),
            Input('tabs', 'value'),
            State('tab-switch-trigger', 'value'),
            prevent_initial_call=True
        )
        def on_tab_switch(active_tab, current_trigger_value):
            # Simply increment the hidden input's value to trigger other callbacks
            return current_trigger_value + 1

    # ------------------------------ App Runner ------------------------------- #

    def run(self, **kwargs: Any) -> None:
        """Starts the Dash development server."""
        self.app.run(**kwargs)


biolink_app = BiolinkDashApp()

# Heroku uses this
server_app = biolink_app.app.server

# Local run
if __name__ == "__main__":
    biolink_app.run(debug=True)
