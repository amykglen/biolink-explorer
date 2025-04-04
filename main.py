from typing import Set, Optional

from dash import Dash, dcc, html, Input, Output
import dash_cytoscape as cyto

from biolink_downloader import BiolinkDownloader
from styles import Styles

# Load additional layouts (including Dagre)
cyto.load_extra_layouts()

class BiolinkDashApp:
    def __init__(self):

        self.biolink_version = "master"
        self.bd = None
        self.elements_predicates = None
        self.elements_categories = None
        self.domains = None
        self.ranges = None
        self.all_categories = None
        self.all_predicates = None

        self.styles = Styles()
        self.update_biolink_data(self.biolink_version)
        self.app = Dash(__name__, title="Biolink Explorer")


        # Extract unique domain and range values for dropdowns


        self.app.layout = self.get_layout()
        self.register_callbacks()



    # ---------------------------------------------- Helper functions ------------------------------------------------- #

    def get_node_info(self, selected_nodes) -> any:
        """Update the info display area CONTENT based on node selection in a table format with mixin, symmetric, and domain/range chips (using divs)."""

        if selected_nodes:
            node_data = selected_nodes[0]

            if node_data and "id" in node_data:
                attributes = node_data.get("attributes", {})
                node_id = node_data.get('id')

                attributes_to_show = {"description": attributes.get("description", "-"),
                                      "notes": attributes.get("notes", "-"),
                                      "aliases": attributes.get("aliases", "-")}
                table_rows = []
                for key, value in attributes_to_show.items():
                    table_rows.append(html.Tr([
                        html.Td(key, style={'text-align': 'right', 'padding-right': '10px', 'vertical-align': 'top',
                                            'width': '150px', 'font-family': 'monospace'}),
                        html.Td(str(value), style={'width': 'auto'})
                    ]))

                # Craft the title
                url = f"https://biolink.github.io/biolink-model/{node_id}"
                title_content = [html.Span(f"{node_id} "),
                                 html.A("docs", href=url, target="_blank",
                                        style={"color": self.styles.link_blue, "font-size": "11px", "margin-left": "3px"})]
                if attributes.get("is_mixin"):
                    title_content.append(html.Div("mixin", style=self.get_chip_style(self.styles.chip_peach, True)))
                if attributes.get("is_symmetric"):
                    title_content.append(html.Div("symmetric", style=self.get_chip_style(self.styles.chip_purple, True)))

                # Indicate domain/range as applicable
                domain_range_info = []
                if "domain" in attributes:  # If domain is there, range will be there
                    domain_range_info.append(html.Span("domain: ", style={'marginRight': '1px', 'font-size': '11px', 'color': 'grey'}))
                    domain_range_info.append(html.Div(attributes["domain"] if attributes["domain"] else "-",
                                                      style=self.get_chip_style(self.styles.chip_green, attributes["domain"])))
                    domain_range_info.append(html.Span(" → ", style={'margin': '0 5px'}))
                    domain_range_info.append(html.Span("range: ", style={'marginLeft': '5px', 'marginRight': '1px', 'font-size': '11px', 'color': 'grey'}))
                    domain_range_info.append(html.Div(attributes["range"] if attributes["range"] else "-",
                                                      style=self.get_chip_style(self.styles.chip_green, attributes["range"])))

                content = [
                    html.H4(title_content, style={'margin': '0px 0px 9px 0px'}),
                    html.Div(domain_range_info,
                             style={'display': 'flex', 'justify-content': 'center', 'align-items': 'center',
                                    'margin-bottom': '5px', 'margin-top': '0px'}),
                    html.Table(table_rows, style={'width': '800px', 'margin': 'auto',
                                                  'text-align': 'left'})
                ]
                return content if domain_range_info else [content[0], content[-1]]
            else:
                return "Error: Selected node data is invalid."
        else:
            return "Click on a node to see info"

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

    def get_mixin_filter(self, filter_id: str, show_by_default: Optional[bool] = False) -> any:
        return html.Div([
                html.Label("Show mixins?"),
                dcc.Checklist(
                    id=filter_id,
                    options=[{"label": "", "value": "include"}],  # Empty label to show just the checkbox
                    value=["include"] if show_by_default else [],
                )
            ], style={"width": "20%", "display": "inline-block", "padding": "0 1%"})

    def get_search_filter(self, filter_id: str, node_names: Set[str]) -> any:
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

    def get_app_info(self) -> list:
        chip_style_green = self.get_chip_style(self.styles.node_green, opacity=self.styles.regular_opacity, border=f"2px solid {self.styles.node_border_green}")
        chip_style_grey = self.get_chip_style(self.styles.node_grey, opacity=self.styles.regular_opacity, border=f"2px solid {self.styles.node_border_grey}")
        chip_style_green_transparent = self.get_chip_style(self.styles.node_green, opacity=self.styles.mixin_opacity, border="0px solid black")
        chip_style_grey_transparent = self.get_chip_style(self.styles.node_grey, opacity=self.styles.mixin_opacity, border="0px solid black")

        info = [
        html.Div(
            style={"padding": "30px", "max-width": "800px", "margin": "0 auto", "margin-bottom": "20px", "overflowY": "auto", "height": "calc(100vh - 150px)"},
            children=[
                html.H3("About this app"),
                html.P([
                    "This application is designed to visualize and explore the relationships between "
                    "categories (i.e. node types) and predicates (i.e., edge types) within the ",
                    html.A("Biolink Model", href="https://github.com/biolink/biolink-model", target="_blank"),
                    ", a schema for biomedical knowledge graphs developed by the ",
                    html.A("NCATS Biomedical Data Translator", href="https://ncats.nih.gov/research/research-activities/translator", target="_blank"),
                    " consortium."
                ]),
                html.H4("Using the tabs:"),
                html.P("""
                    The 'Categories' tab displays the hierarchy of categories in the Biolink Model.
                    You can use the filters at the top to focus on specific
                    categories or include/exclude mixin categories.
                """),
                html.P("""
                    The 'Predicates' tab shows the hierarchy of predicates in the Biolink Model.
                    Use the filters at the top to focus on specific predicates, include/exclude mixin predicates, 
                    and to filter predicates based on their domain and range.
                """),
                html.H4("Interacting with the graphs:"),
                html.P([
                    "Clicking on a node in either graph will display details from the ",
                    html.A("Biolink Model YAML",
                           href="https://github.com/biolink/biolink-model/blob/master/biolink-model.yaml",
                           target="_blank"),
                    " about that item in the area below the graph."
                ]),
                html.H5("Legend:"),
                html.P([html.Div("SomeCategory", style=chip_style_green),
                        html.Div("some_predicate", style=chip_style_green),
                        " Default color for categories and predicates."]),
                html.P([html.Div("some_predicate", style=chip_style_grey),
                        " Predicates with a non-specific domain and range (either NamedThing or not provided) are grey."]),
                html.P([html.Div("SomeCategory", style=chip_style_green_transparent),
                        html.Div("some_predicate", style=chip_style_grey_transparent),
                        " Mixins have a faded color."]),
                html.H4("Search functionality:"),
                html.P("""
                    You can use the search bar (top left) to find specific categories
                    or predicates. The graph will filter itself to show only the item(s) you selected and 
                    their lineages (ancestors and descendants).
                """),
                html.H4("'Show mixins?' option:"),
                html.P("""
                    Mixin categories/predicates allow for multiple inheritance. Use the 'Show mixins?' checkbox to
                    include or exclude these items from the graph. When you opt to include mixins, the graph 
                    will be a directed acyclic graph; when you exclude mixins, it will be a tree.
                """),
                html.P("""
                    Note that if you search for an item that is a mixin but 'Show mixins?' is not selected, the app
                    will override 'Show mixins?' and set it to True.
                """),
                html.H4("Domain and Range Filters (Predicates Tab):"),
                html.P("""
                    On the 'Predicates' tab, you'll find dropdown menus labeled 'Filter by Domain' and 'Filter by Range'.
                    These filters allow you to narrow down the displayed predicates based on the types of categories
                    that are involved in the relationship.
                """),
                html.P("""
                    You can use these filters independently or together to explore specific types of relationships
                    between different categories in the Biolink Model. For instance, you could filter for predicates
                    that have 'Disease' as a domain and 'Symptom' as a range to see predicates that can be used to
                    link diseases to their symptoms.
                """),
                html.H5("Domain Filter:"),
                html.P([
                    "The 'Domain' of a predicate refers to the category of entity that is the ",
                    html.B("subject"),
                    " or source of the relationship. For example, for the predicate 'has_phenotype', the domain might be "
                    "'Disease' because a disease can have a phenotype. "
                ]),
                html.P(["When you select one or more categories in the ",
                    "'Filter by Domain' dropdown, the graph will only show predicates where the subject of the ",
                    "relationship belongs to one of the selected categories (or their ancestors ",
                    "in the category hierarchy). This makes this a convenient way of seeing all predicates that could ",
                    "describe an edge in a knowledge graph that connects a Disease to some other node, for instance."
                ]),
                html.H5("Range Filter:"),
                html.P([
                    "The 'Range' of a predicate refers to the category of entity that is the ",
                    html.B("object"),
                    " or target of the relationship. For example, for the predicate 'has_phenotype', the range might be ",
                    "'Phenotype' because a disease can have a phenotype. "
                ]),
                html.P(["When you select one or more categories in the ",
                        "'Filter by Range' dropdown, the graph will only show predicates where the object of the ",
                        "relationship belongs to one of the selected categories (or their ancestors ",
                        "in the category hierarchy). This makes this a convenient way of seeing all predicates that could ",
                        "describe an edge in a knowledge graph that connects some node to a Phenotype, for instance."
                        ]),
                html.H4("Creators"),
                html.P(["This application was developed by ",
                        html.A("Amy Glen", href="https://github.com/amykglen", target="_blank"),
                        " at ",
                        html.A("Phenome Health", href="https://www.phenomehealth.org", target="_blank"),
                        "."])
            ],
        )
    ]
        return info

    def get_filter_divs_preds(self):
        return html.Div([
            self.get_search_filter("node-search-preds", self.all_predicates),
            self.get_mixin_filter("include-mixins-preds", show_by_default=True),
            html.Div([
                html.Label("Filter by Domain (hierarchical):"),
                dcc.Dropdown(
                    id="domain-filter",
                    options=[{"label": d, "value": d} for d in self.domains],
                    multi=True,
                    placeholder="Select one or more domains..."
                )
            ], style={"width": "20%", "display": "inline-block", "padding": "0 1%"}),
            html.Div([
                html.Label("Filter by Range (hierarchical):"),
                dcc.Dropdown(
                    id="range-filter",
                    options=[{"label": r, "value": r} for r in self.ranges],
                    multi=True,
                    placeholder="Select one or more ranges..."
                )
            ], style={"width": "20%", "display": "inline-block", "padding": "0 1%"})
        ], style=self.styles.filters_wrapper_style)

    def get_filter_divs_cats(self):
        return html.Div([
            self.get_search_filter("node-search-cats", self.all_categories),
            self.get_mixin_filter("include-mixins-cats", show_by_default=False)
        ], style=self.styles.filters_wrapper_style)

    def get_layout(self):
        return html.Div([
            html.Div([
                html.Label("Showing Biolink Model version:", style={"margin-right": "5px"}),
                dcc.Input(id="biolink-version-input", type="text", value=self.biolink_version, debounce=True),
                html.Button("Submit", id="submit-version", n_clicks=0)
            ], style={
                "display": "flex",
                "justifyContent": "flex-end",
                "alignItems": "center",
                "padding": "10px"
            }),
            html.Div(id="main-content", children=self.get_main_content())
        ])

    def get_main_content(self):
        return html.Div(
            id="app-container",
            children=[
                dcc.Tabs([
                    dcc.Tab(label="Categories", children=[
                        html.Div(
                            style={"display": "flex", "flex-direction": "column", "height": "calc(100vh - 100px)"}, # Adjust 50px for tabs height
                            children=[
                                self.get_filter_divs_cats(),
                                cyto.Cytoscape(
                                    id="cytoscape-dag-cats",
                                    elements=self.elements_categories,
                                    layout=self.styles.layout_settings,
                                    style={"width": "100%", "height": "100%"}, # Set height to 100% of parent
                                    stylesheet=self.styles.main_styling
                                ),
                                html.Div(id="node-info-cats", style=self.styles.node_info_div_style)
                            ])
                    ]),
                    dcc.Tab(label="Predicates", children=[
                        html.Div(
                            style={"display": "flex", "flex-direction": "column", "height": "calc(100vh - 100px)"}, # Adjust 50px for tabs height
                            children=[
                                self.get_filter_divs_preds(),
                                cyto.Cytoscape(
                                    id="cytoscape-dag-preds",
                                    elements=self.elements_predicates,
                                    layout=self.styles.layout_settings,
                                    style={"width": "100%", "height": "100%"}, # Set height to 100% of parent
                                    stylesheet=self.styles.main_styling
                                ),
                                html.Div(id="node-info-preds", style=self.styles.node_info_div_style)
                            ])
                    ]),
                    dcc.Tab(label="Info", children=self.get_app_info())
                ]),
        ])

    def update_biolink_data(self, version):
        print(f"in update biolink date, version is {version}")
        self.bd = BiolinkDownloader(biolink_version=version)
        self.biolink_version = self.bd.biolink_version
        self.elements_predicates = self.bd.predicate_dag_dash
        self.elements_categories = self.bd.category_dag_dash

        # Extract unique domain and range values for dropdowns
        self.domains = sorted(set(self.bd.category_dag.nodes()))
        self.ranges = sorted(set(self.bd.category_dag.nodes()))
        self.all_categories = sorted(set(self.bd.category_dag.nodes()))
        self.all_predicates = sorted(set(self.bd.predicate_dag.nodes()))

# ----------------------------------------------- Style variables -------------------------------------------------- #

    # Callbacks to filter graph elements based on dropdown/other selections
    def register_callbacks(self):

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


    def run(self, **kwargs):
        self.app.run(**kwargs)





if __name__ == "__main__":
    app = BiolinkDashApp()
    app.run(debug=True)
