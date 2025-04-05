import os
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

import dash_cytoscape as cyto
from dash import Dash, Input, Output, dcc, html, State

# Import custom modules/classes
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from biolink_downloader import BiolinkDownloader
from styles import Styles

# Load additional Cytoscape layouts (including Dagre)
cyto.load_extra_layouts()


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
        self.biolink_version: str = "master"  # Default version
        self.bd: Optional[BiolinkDownloader] = None
        self.elements_predicates: Optional[List[Dict[str, Any]]] = None
        self.elements_categories: Optional[List[Dict[str, Any]]] = None
        self.domains: Optional[List[str]] = None
        self.ranges: Optional[List[str]] = None
        self.all_categories: Optional[List[str]] = None
        self.all_predicates: Optional[List[str]] = None

        self.styles: Styles = Styles()
        # Fetch initial data based on the default version
        self.update_biolink_data(self.biolink_version)

        self.app: Dash = Dash(__name__, title="Biolink Explorer")
        self.app.layout = self.get_layout()
        self.register_callbacks()

    # ------------------------- Data Loading and Update ------------------------- #

    def update_biolink_data(self, version: str) -> None:
        """
        Fetches and processes Biolink data for the specified version using
        BiolinkDownloader. Updates instance variables holding graph elements
        and filter options.
        """
        self.bd = BiolinkDownloader(biolink_version=version)
        self.biolink_version = self.bd.biolink_version # Store the actual resolved version
        self.elements_predicates = self.bd.predicate_dag_dash
        self.elements_categories = self.bd.category_dag_dash

        # Extract unique domain, range, category, and predicate values for dropdowns
        if self.bd.category_dag:
            self.domains = sorted(list(set(self.bd.category_dag.nodes())))
            self.ranges = sorted(list(set(self.bd.category_dag.nodes())))
            self.all_categories = sorted(list(set(self.bd.category_dag.nodes())))
        else:
            self.domains = []
            self.ranges = []
            self.all_categories = []

        if self.bd.predicate_dag:
             self.all_predicates = sorted(list(self.bd.predicate_dag.nodes()))
        else:
             self.all_predicates = []

    # -------------------------- Layout Generation Methods -------------------------- #

    def get_layout(self) -> html.Div:
        """Generates the main layout Div for the Dash application."""
        return html.Div([
            # Header section with title and version selector
            html.Div([
                html.Div("Biolink Model Explorer", style={
                    "fontSize": "18px",
                    "fontWeight": "bold"
                }),
                html.Div([
                    html.Label([
                        "Showing ",
                        html.A("Biolink Model",
                               href=f"https://github.com/biolink/biolink-model/releases/tag/v{self.biolink_version}",
                               target="_blank", style=self.styles.hyperlink_style),
                        " version:"
                    ], style={"marginRight": "5px"}),
                    dcc.Input(
                        id="biolink-version-input",
                        type="text",
                        value=self.biolink_version,
                        debounce=False,
                        style={"width": "100px", "marginRight": "5px"}
                    ),
                    html.Button("Submit", id="submit-version", n_clicks=0)
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
            # Main content area, updated by callback
            html.Div(id="main-content", children=self.get_main_content())
        ])

    def get_main_content(self) -> html.Div:
        """Generates the main content area including tabs and graphs."""
        tab_content_style = {
            "display": "flex",
            "flexDirection": "column",
            # Adjust height based on header and tabs
            "height": "calc(100vh - 110px)",
        }
        cytoscape_style = {"width": "100%", "height": "100%"}

        return html.Div(
            id="app-container",
            children=[
                dcc.Tabs([
                    dcc.Tab(label="Categories", children=[
                        html.Div(
                            style=tab_content_style,
                            children=[
                                self.get_filter_divs_cats(),
                                cyto.Cytoscape(
                                    id="cytoscape-dag-cats",
                                    elements=self.elements_categories,
                                    layout=self.styles.layout_settings,
                                    style=cytoscape_style,
                                    stylesheet=self.styles.main_styling
                                ),
                                html.Div(id="node-info-cats", style=self.styles.node_info_div_style)
                            ])
                    ]),
                    dcc.Tab(label="Predicates", children=[
                        html.Div(
                            style=tab_content_style,
                            children=[
                                self.get_filter_divs_preds(),
                                cyto.Cytoscape(
                                    id="cytoscape-dag-preds",
                                    elements=self.elements_predicates,
                                    layout=self.styles.layout_settings,
                                    style=cytoscape_style,
                                    stylesheet=self.styles.main_styling
                                ),
                                html.Div(id="node-info-preds", style=self.styles.node_info_div_style)
                            ])
                    ]),
                    dcc.Tab(label="Info", children=self.get_app_info())
                ]),
        ])

    def get_filter_divs_preds(self) -> html.Div:
        """Generates the filter controls Div for the Predicates tab."""
        filter_div_style = {"width": "20%", "display": "inline-block", "padding": "0 1%"}
        return html.Div(
            [
                self.get_search_filter("node-search-preds", self.all_predicates or []),
                self.get_mixin_filter("include-mixins-preds", show_by_default=True),
                html.Div(
                    [
                        html.Label("Filter by Domain (hierarchical):"),
                        dcc.Dropdown(
                            id="domain-filter",
                            options=[{"label": d, "value": d} for d in self.domains or []],
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
                            options=[{"label": r, "value": r} for r in self.ranges or []],
                            multi=True,
                            placeholder="Select one or more ranges...",
                        ),
                    ],
                    style=filter_div_style,
                ),
            ],
            style=self.styles.filters_wrapper_style,
        )

    def get_filter_divs_cats(self) -> html.Div:
        """Generates the filter controls Div for the Categories tab."""
        return html.Div(
            [
                self.get_search_filter("node-search-cats", self.all_categories or []),
                self.get_mixin_filter("include-mixins-cats", show_by_default=False),
            ],
            style=self.styles.filters_wrapper_style,
        )

    def get_app_info(self) -> List[html.Div]:
        """Generates the content for the 'Info' tab."""
        chip_style_green = self.get_chip_style(
            self.styles.node_green,
            opacity=self.styles.regular_opacity,
            border=f"2px solid {self.styles.node_border_green}",
        )
        chip_style_grey = self.get_chip_style(
            self.styles.node_grey,
            opacity=self.styles.regular_opacity,
            border=f"2px solid {self.styles.node_border_grey}",
        )
        chip_style_green_transparent = self.get_chip_style(
            self.styles.node_green,
            opacity=self.styles.mixin_opacity,
            border="0px solid black",
        )
        chip_style_grey_transparent = self.get_chip_style(
            self.styles.node_grey,
            opacity=self.styles.mixin_opacity,
            border="0px solid black",
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
                                href="https://github.com/biolink/biolink-model",
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
                                href="https://github.com/biolink/biolink-model/blob/master/biolink-model.yaml",
                                target="_blank",
                                style=self.styles.hyperlink_style,
                            ),
                            " about that item in the area below the graph.",
                        ]
                    ),
                    html.H5("Legend:"),
                    html.P(
                        [
                            html.Div("SomeCategory", style=chip_style_green),
                            html.Div("some_predicate", style=chip_style_green),
                            " Default color for categories and predicates.",
                        ]
                    ),
                    html.P(
                        [
                            html.Div("some_predicate", style=chip_style_grey),
                            " Predicates with a non-specific domain and range (either NamedThing or not provided) are grey.",
                        ]
                    ),
                    html.P(
                        [
                            html.Div("SomeCategory", style=chip_style_green_transparent),
                            html.Div(
                                "some_predicate", style=chip_style_grey_transparent
                            ),
                            " Mixins have a faded color.",
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
        Generates the HTML content to display information about a selected node
        in a table format, including attributes and visual chips.

        Args:
            selected_nodes: Data provided by Cytoscape for the selected node(s).
                            Expected to be a list containing a single node's data dict.

        Returns:
            A list of Dash HTML components or a string message.
        """
        if not selected_nodes:
            return "Click on a node to see info"

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
                            html.Td(str(value), style={"width": "auto"}),
                        ]
                    )
                )

            # Build the title with ID, docs link, and chips
            url = f"https://biolink.github.io/biolink-model/{node_id}"
            title_content = [
                html.Span(f"{node_id} "),
                html.A(
                    "docs",
                    href=url,
                    target="_blank",
                    style={
                        "color": self.styles.link_blue,
                        "fontSize": "11px",
                        "marginLeft": "3px",
                    },
                ),
            ]
            if attributes.get("is_mixin"):
                title_content.append(
                    html.Div(
                        "mixin",
                        style=self.get_chip_style(self.styles.chip_peach, True),
                    )
                )
            if attributes.get("is_symmetric"):
                title_content.append(
                    html.Div(
                        "symmetric",
                        style=self.get_chip_style(self.styles.chip_purple, True),
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
                            "fontSize": "11px",
                            "color": "grey",
                        },
                    ),
                    html.Div(
                        domain if domain else "-",
                        style=self.get_chip_style(self.styles.chip_green, domain),
                    ),
                    html.Span(" → ", style={"margin": "0 5px"}),
                    html.Span(
                        "range: ",
                        style={
                            "marginLeft": "5px",
                            "marginRight": "1px",
                            "fontSize": "11px",
                            "color": "grey",
                        },
                    ),
                    html.Div(
                        range_val if range_val else "-",
                        style=self.get_chip_style(self.styles.chip_green, range_val),
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

    def filter_graph_to_certain_nodes(self, node_ids, relevant_elements) -> list:
        relevant_nodes = [element for element in relevant_elements if
                          "id" in element["data"] and element["data"]["id"] in node_ids]
        relevant_node_ids = [element["data"]["id"] for element in relevant_nodes]
        relevant_edges = [element for element in relevant_elements if "source" in element["data"] and
                          element["data"]["source"] in relevant_node_ids and
                          element["data"]["target"] in relevant_node_ids]
        relevant_elements = relevant_nodes + relevant_edges
        return relevant_elements

    def filter_graph(self, element_set, selected_domains, selected_ranges, include_mixins, search_nodes, search_nodes_expanded):
        """Filter edges based on filter selections."""
        if "include" in include_mixins:
            relevant_elements = element_set
        else:
            relevant_node_ids = [element["data"]["id"] for element in element_set
                                 if "id" in element["data"] and not element["data"].get("attributes", {})["is_mixin"]]
            relevant_elements = self.filter_graph_to_certain_nodes(relevant_node_ids, element_set)

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
            relevant_node_ids = [element["data"]["id"] for element in relevant_elements
                                 if "id" in element["data"] and element["data"]["id"] in search_nodes_expanded]
            relevant_elements = self.filter_graph_to_certain_nodes(relevant_node_ids, element_set)

        if not selected_domains and not selected_ranges:
            return relevant_elements  # Show all elements if no filters applied

        selected_domains_set = self.bd.get_ancestors_nx(self.bd.category_dag, selected_domains)
        selected_ranges_set = self.bd.get_ancestors_nx(self.bd.category_dag, selected_ranges)

        filtered_node_ids = [node["data"]["id"] for node in relevant_elements if "id" in node["data"] and
                             (not selected_domains or not node["data"]["attributes"].get("domain") or node["data"]["attributes"]["domain"] in selected_domains_set) and
                             (not selected_ranges or not node["data"]["attributes"].get("range") or node["data"]["attributes"]["range"] in selected_ranges_set)]
        filtered_elements = self.filter_graph_to_certain_nodes(filtered_node_ids, relevant_elements)

        return filtered_elements

    @staticmethod
    def get_mixin_filter(filter_id: str, show_by_default: Optional[bool] = False) -> any:
        return html.Div([
                html.Label("Show mixins?"),
                dcc.Checklist(
                    id=filter_id,
                    options=[{"label": "", "value": "include"}],  # Empty label to show just the checkbox
                    value=["include"] if show_by_default else [],
                )
            ], style={"width": "20%", "display": "inline-block", "padding": "0 1%"})

    @staticmethod
    def get_search_filter(filter_id: str, node_names: Set[str]) -> any:
        item_type = "predicate" if "pred" in filter_id else "category"
        return html.Div([
            html.Label(f"Search for {item_type}(s):"),
            dcc.Dropdown(
                id=filter_id,
                options=[{"label": node_name, "value": node_name} for node_name in node_names],
                multi=True,
                placeholder=f"Select items... (will filter to their lineages)"
            )
        ], style={"width": "30%", "display": "inline-block", "padding": "0 1%"})

    def get_chip_style(self, color: str, chip_value: Optional[any] = "something", opacity: Optional[float] = None, border: Optional[str] = None) -> dict:
        if chip_value is None or chip_value == self.bd.root_category:
            color = self.styles.chip_grey
        chip_style = {'padding': '2px 5px', 'border-radius': '3px', 'background-color': color,
                      'margin-left': '8px', 'fontSize': '12px', 'display': 'inline-block'}
        if opacity:
            chip_style["opacity"] = opacity
        if border:
            chip_style["border"] = border
        return chip_style

    # --------------------------- Callback Registration --------------------------- #

    def register_callbacks(self):
        # Callbacks to filter graph elements based on dropdown/other selections

        @self.app.callback(
            Output("cytoscape-dag-preds", "elements"),
            Output("include-mixins-preds", "value"),
            Input("domain-filter", "value"),
            Input("range-filter", "value"),
            Input("include-mixins-preds", "value"),
            Input("node-search-preds", "value")
        )
        def filter_graph_predicates(selected_domains, selected_ranges, include_mixins, search_nodes):
            if search_nodes:
                # Override the include mixins filter as necessary!
                if any(self.bd.predicate_dag.nodes[node_id].get("is_mixin") for node_id in search_nodes):
                    include_mixins = ["include"]
                ancestors = self.bd.get_ancestors_nx(self.bd.predicate_dag, search_nodes)
                descendants = self.bd.get_descendants_nx(self.bd.predicate_dag, search_nodes)
                search_nodes_expanded = set(search_nodes).union(ancestors, descendants)
            else:
                search_nodes_expanded = set()
            return self.filter_graph(self.elements_predicates, selected_domains, selected_ranges, include_mixins, search_nodes, search_nodes_expanded), include_mixins

        @self.app.callback(
            Output("cytoscape-dag-cats", "elements"),
            Output("include-mixins-cats", "value"),
            Input("include-mixins-cats", "value"),
            Input("node-search-cats", "value")
        )
        def filter_graph_categories(include_mixins, search_nodes):
            if search_nodes:
                # Override the include mixins filter as necessary!
                if any(self.bd.category_dag.nodes[node_id].get("is_mixin") for node_id in search_nodes):
                    include_mixins = ["include"]
                ancestors = self.bd.get_ancestors_nx(self.bd.category_dag, search_nodes)
                descendants = self.bd.get_descendants_nx(self.bd.category_dag, search_nodes)
                search_nodes_expanded = set(search_nodes).union(ancestors, descendants)
            else:
                search_nodes_expanded = set()
            return self.filter_graph(self.elements_categories, [], [], include_mixins, search_nodes, search_nodes_expanded), include_mixins

        # Callbacks to display node info in the bottom area when a node is clicked

        @self.app.callback(
            Output("node-info-cats", "children"),
            Input("cytoscape-dag-cats", "selectedNodeData"),
        )
        def display_node_info_categories(selected_nodes):
            return self.get_node_info(selected_nodes)

        @self.app.callback(
            Output("node-info-preds", "children"),
            Input("cytoscape-dag-preds", "selectedNodeData"),
        )
        def display_node_info_predicates(selected_nodes):
            return self.get_node_info(selected_nodes)

        @self.app.callback(
            Output("main-content", "children"),
            Input("biolink-version-input", "value"),
            prevent_initial_call=True
        )
        def update_content(version):
            self.update_biolink_data(version)
            return self.get_main_content()

    # ------------------------------ App Runner ------------------------------- #

    def run(self, **kwargs):
        self.app.run(**kwargs)


# Main execution block
if __name__ == "__main__":
    app = BiolinkDashApp()
    app.run(debug=True)
