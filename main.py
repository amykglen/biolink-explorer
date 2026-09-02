import copy
import logging
import os
import sys
import urllib.parse
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx
from dash import Dash, Input, Output, dcc, html, State, no_update

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

        self.app: Dash = Dash(
            __name__,
            title="Biolink Explorer",
            suppress_callback_exceptions=True,
            external_stylesheets=[
                "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
            ],
        )
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
            all_associations = sorted(list(bm.association_dag.nodes())) if bm.association_dag else []
            self.bm_cache[version] = {"bm": bm,
                                      "elements_predicates": elements_predicates,
                                      "elements_categories": elements_categories,
                                      "elements_associations": bm.association_dag_dash,
                                      "domains": domains,
                                      "ranges": ranges,
                                      "all_categories": all_categories,
                                      "all_predicates": all_predicates,
                                      "all_associations": all_associations}
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
                html.Span("Biolink Model Explorer", style=self.styles.header_title_style),
                html.Div([
                    html.Label([
                        "Showing ",
                        html.Div(id="biolink-version-link", style={"display": "inline-block"}),
                        " version:"
                    ], style={**self.styles.header_text_style, "marginRight": "8px"}),
                    dcc.Dropdown(
                        id="biolink-version-input",
                        options=[{"label": tag, "value": tag} for tag in all_version_tags],
                        value=initial_version_tag,
                        clearable=False,
                        maxHeight=420,
                        style={"width": "112px", "fontSize": "13px"}
                    ),
                    html.Button(
                        self.get_info_icon("#e9f4f2"),
                        id="info-btn", title="About this app",
                        className="header-icon-btn", style=self.styles.header_icon_button_style,
                    ),
                ], style={
                    "display": "flex",
                    "alignItems": "center",
                    "gap": "10px",
                })
            ], style=self.styles.header_style),
            # Main content area, updated by callback
            html.Div(id="main-content", children=self.get_main_content()),
            # About / info modal (shown/hidden by assets/modal.js)
            self.get_info_modal(),
        ], style={
            "fontFamily": self.styles.font_family,
            "backgroundColor": self.styles.bg,
            "color": self.styles.text,
            "minHeight": "100vh",
        })

    def get_info_modal(self) -> html.Div:
        """The 'About' modal overlay (hidden by default; toggled by assets/modal.js)."""
        return html.Div(
            id="info-modal",
            style=self.styles.modal_backdrop_style,
            children=html.Div(
                id="info-modal-card",
                style=self.styles.modal_card_style,
                children=[
                    html.Button("✕", id="info-close", title="Close",
                                className="modal-close-btn", style=self.styles.modal_close_style),
                    *self.get_info_content(),
                ],
            ),
        )

    def get_main_content(self) -> html.Div:
        """Generates the main content area including tabs and graphs."""
        # Each tab is a horizontal row: the graph column (filters + tree) on the left,
        # and the node-detail panel on the right.
        # Fills the viewport below the header (~46px) and the tab bar (~42px).
        tab_row_style = {
            "display": "flex",
            "flexDirection": "row",
            "height": "calc(100vh - 88px)",
        }
        graph_col_style = {
            "display": "flex",
            "flexDirection": "column",
            "flex": "1 1 auto",
            "minWidth": "0",
            "height": "100%",
        }
        tree_style = {"width": "100%", "height": "100%", "flex": "1 1 auto",
                      "minHeight": "0", "backgroundColor": self.styles.bg, "overflow": "hidden",
                      "position": "relative"}  # anchors the overlaid zoom controls

        def tab_body(filters_id, tree_id, info_id):
            # Which filter Stores this tab's "Filtered view" banner watches / can clear.
            if "cats" in tree_id:
                clear_stores = ["node-search-cats"]
            elif "assoc" in tree_id:
                clear_stores = ["node-search-assoc"]
            else:
                clear_stores = ["node-search-preds", "domain-filter", "range-filter"]
            filter_banner = html.Div(
                [
                    html.Span("Filtered view", className="bl-filter-banner-text"),
                    html.Button("Clear filters", className="bl-filter-clear",
                                **{"data-clear": ",".join(clear_stores)}),
                ],
                id=f"{tree_id}--filterbanner", className="bl-filter-banner",
            )
            # "Hidden content" pills (one per hideable type), stacked bottom-left. Each has its
            # own Show button that flips just its checkbox.
            mixin_cb = ("include-mixins-cats" if "cats" in tree_id
                        else "include-mixins-assoc" if "assoc" in tree_id
                        else "include-mixins-preds")

            def hidden_pill_div(kind, reveal_cb):
                return html.Div(
                    [
                        html.Span("", id=f"{tree_id}--hiddencount-{kind}", className="bl-hidden-badge-text"),
                        html.Button("Show", className="bl-hidden-badge-show"),
                    ],
                    id=f"{tree_id}--hiddenbadge-{kind}", className="bl-hidden-badge",
                    **{"data-reveal": reveal_cb},
                )

            pills = [hidden_pill_div("mixins", mixin_cb)]
            if "preds" in tree_id:
                pills.append(hidden_pill_div("noncanon", "include-noncanonical-preds"))
            hidden_badge = html.Div(pills, className="bl-hidden-badges")
            return html.Div(
                style=tab_row_style,
                children=[
                    html.Div(
                        style=graph_col_style,
                        children=[
                            html.Div(id=filters_id),  # filters populated by callback
                            # Graph area (relative) so the overlays (banners/badges) can sit on it.
                            html.Div(
                                style={"position": "relative", "flex": "1 1 auto", "minHeight": "0",
                                       "display": "flex"},
                                children=[
                                    html.Div(id=tree_id, className="tree-container", style=tree_style),
                                    filter_banner,
                                    hidden_badge,
                                ],
                            ),
                        ],
                    ),
                    # Detail panel: a resize handle + the (callback-updated) content
                    html.Div(
                        style=self.styles.detail_panel_style,
                        children=[
                            html.Div(className="panel-resize-handle",
                                     style=self.styles.panel_resize_handle_style),
                            html.Div(id=info_id, style=self.styles.detail_content_style,
                                     children=self.get_node_info(None)),
                        ],
                    ),
                ],
            )

        return html.Div(
            id="app-container",
            children=[
                # Stores holding the (filtered) graph elements and the selected node,
                # driving the D3 tree renderer (assets/tree.js) and the info panels.
                # Wrapped in dcc.Loading so a slow (e.g. cold Heroku dyno) update shows a
                # spinner; delay_show avoids flashing it on fast, warm interactions.
                dcc.Loading(
                    id="app-loading",
                    type="circle",
                    color=self.styles.accent,
                    delay_show=350,
                    overlay_style={"visibility": "visible", "opacity": 0.55,
                                   "backgroundColor": self.styles.bg},
                    children=[
                        dcc.Store(id="elements-cats"),
                        dcc.Store(id="elements-preds"),
                        dcc.Store(id="elements-assoc"),
                        dcc.Store(id="selected-cats"),
                        dcc.Store(id="selected-preds"),
                        dcc.Store(id="selected-assoc"),
                        dcc.Store(id="render-signal"),  # clientside render callback target
                        dcc.Tabs(
                            id="tabs",
                            value="tab-1",
                            style=self.styles.tabs_container_style,
                            children=[
                                dcc.Tab(label="Categories", value="tab-1",
                                        style=self.styles.tab_style, selected_style=self.styles.tab_selected_style,
                                        children=[tab_body("category-filters-container", "tree-cats", "node-info-cats")]),
                                dcc.Tab(label="Predicates", value="tab-2",
                                        style=self.styles.tab_style, selected_style=self.styles.tab_selected_style,
                                        children=[tab_body("predicate-filters-container", "tree-preds", "node-info-preds")]),
                                dcc.Tab(label="Associations", value="tab-3",
                                        style=self.styles.tab_style, selected_style=self.styles.tab_selected_style,
                                        children=[tab_body("association-filters-container", "tree-assoc", "node-info-assoc")])
                            ]),
                    ],
                ),
        ])

    def get_filter_divs_preds(self, all_predicates: List[str], domains: List[str], ranges: List[str]) -> html.Div:
        """Generates the filter controls Div for the Predicates tab."""
        filter_div_style = {"width": "220px"}
        hierarchical_tip = ("Hierarchical: also matches predicates whose declared "
                            "domain/range is an ancestor of the selected category.")
        return html.Div(
            [
                self.get_search_filter("node-search-preds", all_predicates or []),
                self.get_checkbox_filter("include-mixins-preds", "Show mixins?", show_by_default=True),
                self.get_checkbox_filter("include-noncanonical-preds", "Show non-canonical?", show_by_default=False),
                # Domain + range dropdowns, grouped so they float right together
                html.Div(
                    [
                        html.Div(
                            [
                                html.Label("Filter by domain", title=hierarchical_tip,
                                           style={**self.styles.filter_label_style, "cursor": "help"}),
                                self.get_multiselect("domain-filter", domains or [], "Select domains…",
                                                     right_align=True),
                            ],
                            style=filter_div_style,
                        ),
                        html.Div(
                            [
                                html.Label("Filter by range", title=hierarchical_tip,
                                           style={**self.styles.filter_label_style, "cursor": "help"}),
                                self.get_multiselect("range-filter", ranges or [], "Select ranges…",
                                                     right_align=True),
                            ],
                            style=filter_div_style,
                        ),
                    ],
                    style={"display": "flex", "gap": "20px", "marginLeft": "auto"},
                ),
            ],
            style=self.styles.filters_wrapper_style,
        )

    def get_filter_divs_cats(self, all_categories: List[str]) -> html.Div:
        """Generates the filter controls Div for the Categories tab."""
        return html.Div(
            [
                self.get_search_filter("node-search-cats", all_categories or []),
                self.get_checkbox_filter("include-mixins-cats", "Show mixins?", show_by_default=False),
            ],
            style=self.styles.filters_wrapper_style,
        )

    def get_filter_divs_assoc(self, all_associations: List[str]) -> html.Div:
        """Generates the filter controls Div for the Associations tab (same shape as categories)."""
        return html.Div(
            [
                self.get_search_filter("node-search-assoc", all_associations or []),
                self.get_checkbox_filter("include-mixins-assoc", "Show mixins?", show_by_default=False),
            ],
            style=self.styles.filters_wrapper_style,
        )

    def get_info_content(self) -> List[Any]:
        """Generates the 'About' content shown in the info modal."""
        def glyph(symbol: str, color: str) -> html.Span:
            """A colored node-glyph for the legend (● hollow ○)."""
            return html.Span(symbol, style={
                "color": color,
                "fontSize": "17px",
                "marginRight": "8px",
                "verticalAlign": "middle",
            })

        info_content = [
            html.Div(
                style={
                    "fontSize": "13.5px",
                    "lineHeight": "1.6",
                },
                children=[
                    html.H3("About this app", style={"marginTop": "0"}),
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
                        By default only canonical predicates (the Translator-preferred direction of a relationship)
                        are shown; check 'Show non-canonical?' to also include the non-preferred directions, which
                        are visually distinguished (see the legend below). Use the filters at the top to focus on
                        specific predicates, include/exclude mixin predicates, and to filter by domain and range.
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
                            " about that item in the panel on the right. Hover a node to highlight it, and scroll over the graph to zoom in or out.",
                        ]
                    ),
                    html.H5("Legend:"),
                    html.P(
                        [
                            "Each node is a small circle, whose ", html.B("color"),
                            " shows whether it is a mixin and whose ", html.B("fill"),
                            " shows whether it is canonical:",
                        ]
                    ),
                    html.P(
                        [
                            glyph("●", self.styles.node_regular),
                            "Green is a regular category, or a canonical predicate "
                            "(the Translator-preferred direction of a relationship).",
                        ]
                    ),
                    html.P(
                        [
                            glyph("○", self.styles.node_regular),
                            "A hollow circle is a non-canonical predicate (the non-preferred "
                            "direction of a relationship).",
                        ]
                    ),
                    html.P(
                        [
                            glyph("●", self.styles.node_mixin), glyph("○", self.styles.node_mixin),
                            "Gold marks a mixin — a category or predicate that enables multiple "
                            "inheritance — solid or hollow following the same canonical rule.",
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

    def get_node_info(self, selected_nodes: Optional[List[Dict[str, Any]]],
                      graph_type: str = "cats") -> Any:
        """
        Generates the content of the right-hand detail panel for the selected node:
        a header (id, docs link, status badges), a domain -> range / inverse section
        for predicates, and description / notes / aliases sections.

        Args:
            selected_nodes: A list containing a single selected node's data dict
                            (``{"id": ..., "attributes": {...}}``), or falsy if none.
            graph_type: which tab the node belongs to ("cats", "preds", or "assoc") —
                        controls the "focus" button's target search box and wording.
        """
        if not selected_nodes or not selected_nodes[0] or "id" not in selected_nodes[0]:
            return html.Div(
                "Click an item in the graph to see its details.",
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

        title_block = html.Div(
            [
                html.Div(node_id, style={"fontSize": "17px", "fontWeight": 700,
                                         "lineHeight": "1.25", "wordBreak": "break-word",
                                         "color": self.styles.text}),
                html.A("View in Biolink docs ↗", href=url, target="_blank",
                       style={**self.styles.hyperlink_style, "fontSize": "13px",
                              "display": "inline-block", "marginTop": "5px"}),
            ],
            style={"minWidth": "0"},
        )

        # "Focus graph on this node" icon button (adds it to the search dropdown on this tab)
        button_id = f"filter-to-node-{graph_type}"
        item_word = {"cats": "category", "preds": "predicate", "assoc": "association"}.get(graph_type, "item")
        filter_button = html.Button(
            self.get_target_icon(self.styles.accent_dark),
            id=button_id, n_clicks=0, title=f"Focus the graph on this {item_word}",
            className="filter-icon-btn", style=self.styles.filter_icon_button_style,
        )

        header_row = html.Div(
            [title_block, filter_button],
            style={"display": "flex", "justifyContent": "space-between",
                   "alignItems": "flex-start", "gap": "12px"},
        )

        sections = [header_row]

        # --- Properties (fixed rows, so they stay put as you flip between nodes) ---
        flags = [("Mixin", bool(attributes.get("is_mixin")),
                  self.styles.chip_peach, self.styles.chip_peach_text)]
        if is_predicate:
            flags = [
                ("Canonical", bool(attributes.get("is_canonical")),
                 self.styles.chip_canonical, self.styles.chip_canonical_text),
                ("Mixin", bool(attributes.get("is_mixin")),
                 self.styles.chip_peach, self.styles.chip_peach_text),
                ("Symmetric", bool(attributes.get("is_symmetric")),
                 self.styles.chip_purple, self.styles.chip_purple_text),
            ]
        sections.append(self.get_detail_section(
            "Properties",
            html.Div([self.get_property_row(label, is_true, tint, tint_text)
                      for (label, is_true, tint, tint_text) in flags]),
        ))

        # --- Predicate relationship (domain -> range, inverse) ---
        if is_predicate:
            domain = attributes.get("domain")
            range_val = attributes.get("range")
            relationship = html.Div(
                [
                    chip(domain if domain else "—", self.styles.chip_domain, chip_value=domain),
                    html.Span("→", style={"margin": "0 8px", "color": self.styles.text_muted,
                                               "fontSize": "14px"}),
                    chip(range_val if range_val else "—", self.styles.chip_domain, chip_value=range_val),
                ],
                style={"display": "flex", "alignItems": "center", "flexWrap": "wrap", "gap": "4px"},
            )
            sections.append(self.get_detail_section("Domain → Range", relationship))
            # Always show this (with a "—" when empty) so the panel layout is consistent
            # as you flip between predicates.
            inverse_val = attributes.get("inverse")
            sections.append(self.get_detail_section(
                "Inverse predicate",
                chip(inverse_val, self.styles.chip_grey, self.styles.text) if inverse_val
                else self.format_detail_value(None)))

        # --- Association shape (subject -> predicate -> object) — the schema constraints
        # that define what this association connects. Predicate is a pinned predicate, an
        # enum of allowed predicates, or "any" when unconstrained. ---
        if graph_type == "assoc":
            subj = attributes.get("assoc_subject")
            obj = attributes.get("assoc_object")
            pred = attributes.get("assoc_predicate")

            def spo_arrow():
                return html.Span("→", style={"margin": "0 6px", "color": self.styles.text_muted,
                                             "fontSize": "14px"})
            pred_chip = (chip(pred, self.styles.chip_purple, self.styles.chip_purple_text, chip_value=pred)
                         if pred else
                         chip("any", self.styles.chip_grey, self.styles.text_muted, chip_value=None))
            spo = html.Div(
                [
                    chip(subj if subj else "—", self.styles.chip_domain, chip_value=subj),
                    spo_arrow(),
                    pred_chip,
                    spo_arrow(),
                    chip(obj if obj else "—", self.styles.chip_domain, chip_value=obj),
                ],
                style={"display": "flex", "alignItems": "center", "flexWrap": "wrap", "gap": "4px"},
            )
            sections.append(self.get_detail_section("Subject → Predicate → Object", spo))

        # --- Free-text metadata ---
        sections.append(self.get_detail_section("Description", self.format_detail_value(attributes.get("description"))))
        sections.append(self.get_detail_section("Notes", self.format_detail_value(attributes.get("notes"))))
        sections.append(self.get_detail_section("Aliases", self.format_detail_value(attributes.get("aliases"))))

        # 'Opposite of' lives at the very bottom — it points AWAY from this predicate (a
        # "see also"), so keeping it out of the main summary avoids muddying what this
        # predicate itself means.
        if is_predicate:
            opposite_val = attributes.get("opposite_of")
            sections.append(self.get_detail_section(
                "Opposite of",
                chip(opposite_val, self.styles.chip_grey, self.styles.text) if opposite_val
                else self.format_detail_value(None)))

        return sections

    def get_detail_section(self, label: str, value_component: Any) -> html.Div:
        """A labeled block in the detail panel (small uppercase label + value)."""
        return html.Div([
            html.Div(label, style=self.styles.detail_label_style),
            value_component,
        ])

    @staticmethod
    def get_target_icon(color: str) -> html.Img:
        """A target / focus icon (concentric circles, inline SVG), in the given color."""
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
            f'stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/>'
            '<circle cx="12" cy="12" r="1.4" fill="' + color + '"/></svg>'
        )
        src = "data:image/svg+xml;utf8," + urllib.parse.quote(svg)
        return html.Img(src=src, style={"width": "16px", "height": "16px", "display": "block"})

    @staticmethod
    def get_info_icon(color: str) -> html.Img:
        """An 'info' icon (inline SVG), stroked in the given color."""
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
            f'stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            '<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/>'
            '<line x1="12" y1="8" x2="12.01" y2="8"/></svg>'
        )
        src = "data:image/svg+xml;utf8," + urllib.parse.quote(svg)
        return html.Img(src=src, style={"width": "17px", "height": "17px", "display": "block"})

    def get_property_row(self, label: str, is_true: bool, tint: str, tint_text: str) -> html.Div:
        """
        A fixed row in the Properties grid: property name on the left, and a colored
        "Yes" pill (when true) or a muted "No" on the right. Rows are always present in
        the same order so the panel doesn't shift when flipping between nodes.
        """
        if is_true:
            value = html.Span("Yes", style={
                "backgroundColor": tint, "color": tint_text, "fontWeight": 600,
                "fontSize": "12.5px", "padding": "2px 10px", "borderRadius": "999px",
            })
        else:
            value = html.Span("No", style={"color": self.styles.text_muted, "fontSize": "13px"})
        return html.Div(
            [html.Span(label, style={"color": self.styles.text, "fontSize": "13px"}), value],
            style={"display": "flex", "justifyContent": "space-between", "alignItems": "center",
                   "padding": "6px 0", "borderBottom": f"1px solid {self.styles.border_subtle}"},
        )

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

    @staticmethod
    def count_nodes(elements: List[Dict[str, Any]]) -> int:
        """Number of node (not edge) elements in a Cytoscape-style element list."""
        return sum(1 for e in elements if "source" not in e.get("data", {}))

    def hidden_pill(self, count: int, label: str) -> Tuple[str, str]:
        """
        Count text + className for one 'hidden content' pill (mixins or non-canonical) —
        shown when that content is hidden but available in the current subgraph.
        """
        if count <= 0:
            return "", "bl-hidden-badge"
        return f"{count} {label} hidden", "bl-hidden-badge bl-hidden-badge-visible"

    @staticmethod
    def _mixins_label(count: int) -> str:
        return f"mixin{'s' if count != 1 else ''}"

    def remove_noncanonical(self, element_set: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filters predicate elements down to canonical predicates and their edges."""
        canonical_node_ids: Set[str] = {
            element["data"]["id"]
            for element in element_set
            if "id" in element.get("data", {})
               and element["data"].get("attributes", {}).get("is_canonical", False)
        }
        return self.filter_graph_to_certain_nodes(canonical_node_ids, element_set)

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

    def get_checkbox_filter(self, filter_id: str, label: str, show_by_default: bool = False) -> html.Div:
        """Creates an inline checkbox filter, e.g. '☐ Show mixins?'."""
        return html.Div(
            [
                dcc.Checklist(
                    id=filter_id,
                    className="bl-checkbox-filter",
                    options=[{"label": label, "value": "include"}],
                    value=["include"] if show_by_default else [],
                    style={"fontSize": "13px", "color": self.styles.text},
                    inputStyle={"marginRight": "6px"},
                ),
            ],
            # Nudge up from the bottom so the checkbox sits level with the dropdowns.
            style={"flex": "0 0 auto", "paddingBottom": "7px"},
        )

    def get_search_filter(self, filter_id: str, node_names: List[str]) -> html.Div:
        """Creates a search dropdown component."""
        label_text = ("Search predicates" if "pred" in filter_id
                      else "Search associations" if "assoc" in filter_id
                      else "Search categories")
        return html.Div(
            [
                html.Label(label_text, style=self.styles.filter_label_style),
                self.get_multiselect(filter_id, node_names, "Type to filter to lineages…",
                                     popup_width="405px" if "pred" in filter_id else "355px"),
            ],
            style={"width": "230px"},
        )

    def get_multiselect(self, filter_id: str, option_names: List[str], placeholder: str,
                        right_align: bool = False, multi: bool = True,
                        initial_value: Optional[str] = None, popup_width: str = "355px") -> html.Div:
        """
        A custom searchable multi-select control (replaces dcc.Dropdown, which virtualizes
        its option list and mis-sizes the popup on reopen). The selection lives in a plain,
        NON-virtualized dcc.Checklist with this ``filter_id`` — so its ``value`` is the same
        list shape the old dropdown exposed and existing callbacks work unchanged. Open/close,
        type-to-filter and the trigger's display text are wired up in assets/msdropdown.js and
        a small clientside callback (see register_callbacks).
        """
        # Options are plain clickable rows (NOT a dcc.Checklist / dcc.Dropdown — both
        # virtualize their option list, which is the whole source of the popup-height bug).
        # 150-ish rows render fine as plain DOM. Selection lives in the dcc.Store below.
        rows = [
            html.Div(
                [html.Span(className="bl-ms-check"), html.Span(name, className="bl-ms-optlabel")],
                className="bl-ms-option", **{"data-value": name},
            )
            for name in sorted(option_names)
        ]
        return html.Div(
            [
                # Trigger / control: shows the current selection (or the placeholder via CSS)
                html.Div(
                    [
                        html.Span(initial_value if (not multi and initial_value) else None,
                                  id=f"{filter_id}--display", className="bl-ms-display",
                                  **{"data-placeholder": placeholder}),
                        html.Span("×", className="bl-ms-clear", title="Clear selection",
                                  **{"aria-label": "Clear selection"}),
                        html.Img(src="data:image/svg+xml;utf8," + urllib.parse.quote(
                            '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" '
                            'viewBox="0 0 24 24" fill="none" stroke="#a29a8d" stroke-width="2.5" '
                            'stroke-linecap="round" stroke-linejoin="round">'
                            '<polyline points="6 9 12 15 18 9"/></svg>'),
                            className="bl-ms-arrow"),
                    ],
                    className="bl-ms-control",
                ),
                # Popup: a search box + the scrollable list of option rows
                html.Div(
                    [
                        dcc.Input(id=f"{filter_id}--search", type="search",
                                  placeholder="Search…", autoComplete="off",
                                  className="bl-ms-search"),
                        html.Div(rows, className="bl-ms-options"),
                    ],
                    className="bl-ms-popup",
                ),
                # The selection — the component the callbacks read via its "data" prop. For a
                # multi-select that's the list of values (same shape the old dropdown's "value"
                # had); for a single-select it's the one selected value (a string).
                dcc.Store(id=filter_id, data=(initial_value if not multi else [])),
            ],
            className="bl-ms-wrapper" + (" bl-ms-right" if right_align else "")
                      + ("" if multi else " bl-ms-single"),
            style={"--bl-ms-popup-w": popup_width},
            **{"data-store": filter_id},
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
            "padding": "2px 9px",
            "borderRadius": "999px" if circular else "6px",
            "backgroundColor": final_color,
            "marginLeft": margin_left,
            "fontSize": "12.5px",
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
            function(catElements, predElements, assocElements, tabTrigger) {
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
                draw("tree-assoc", assocElements, "selected-assoc", "assoc");
                return window.dash_clientside.no_update;
            }
            """,
            Output("render-signal", "data"),
            Input("elements-cats", "data"),
            Input("elements-preds", "data"),
            Input("elements-assoc", "data"),
            Input("tab-switch-trigger", "value"),
        )

        # Callbacks to filter graph elements based on dropdown/other selections

        @self.app.callback(
            Output("elements-preds", "data", allow_duplicate=True),
            Output("include-mixins-preds", "value"),
            Output("include-noncanonical-preds", "value"),
            Output("tree-preds--hiddencount-mixins", "children"),
            Output("tree-preds--hiddenbadge-mixins", "className"),
            Output("tree-preds--hiddencount-noncanon", "children"),
            Output("tree-preds--hiddenbadge-noncanon", "className"),
            Input("domain-filter", "data"),
            Input("range-filter", "data"),
            Input("include-mixins-preds", "value"),
            Input("include-noncanonical-preds", "value"),
            Input("node-search-preds", "data"),
            Input('tab-switch-trigger', 'value'),  # Trigger on tab switch
            State('session-biolink-version-store', 'data'),  # READ version from store
            prevent_initial_call=True  # Prevent initial call for filtering
        )
        def filter_graph_predicates(
            selected_domains: Optional[List[str]],
            selected_ranges: Optional[List[str]],
            include_mixins: List[str],
            include_noncanonical: List[str],
            search_nodes: Optional[List[str]],
            tab_trigger: int,
            version_tag: str
        ) -> Tuple[List[Dict[str, Any]], List[str], List[str], str, str, str, str]:
            """Filters predicate graph based on domain, range, mixins, canonical, and search."""

            # Get data from cache for the session's version
            version_data = self.get_biolink_data_for_version(version_tag)
            if not version_data or not version_data.get('bm'): # Check if data/bm loaded
                 # Return empty elements and original values if data is missing
                 return ([], include_mixins, include_noncanonical,
                         "", "bl-hidden-badge", "", "bl-hidden-badge")

            bm = version_data['bm'] # Use the BM instance for THIS version
            all_predicates = version_data['elements_predicates']  # full set (incl. non-canonical)

            include_mixins_updated = include_mixins # Start with user's selection
            include_noncanonical_updated = include_noncanonical
            if search_nodes:
                # If a mixin was searched, force 'include mixins'
                if any(bm.predicate_dag.nodes[node_id].get("is_mixin") for node_id in search_nodes):
                    include_mixins_updated = ["include"]
                # If a non-canonical predicate was searched, force 'show non-canonical'
                if any(not bm.predicate_dag.nodes[node_id].get("is_canonical") for node_id in search_nodes):
                    include_noncanonical_updated = ["include"]

            # Restrict to canonical predicates unless 'show non-canonical' is checked
            elements_predicates = (all_predicates if "include" in include_noncanonical_updated
                                   else self.remove_noncanonical(all_predicates))

            def flt(elements, mixins, dom=selected_domains, rng=selected_ranges):
                return self.filter_graph(elements, dom, rng, mixins, search_nodes, bm.predicate_dag, bm)

            result = flt(elements_predicates, include_mixins_updated)
            # How many nodes each hidden toggle would add, within the current subgraph.
            hidden_mixins = 0
            if "include" not in include_mixins_updated:
                hidden_mixins = self.count_nodes(flt(elements_predicates, ["include"])) - self.count_nodes(result)
            hidden_noncanonical = 0
            if "include" not in include_noncanonical_updated:
                hidden_noncanonical = self.count_nodes(flt(all_predicates, include_mixins_updated)) - self.count_nodes(result)
            mtext, mclass = self.hidden_pill(hidden_mixins, self._mixins_label(hidden_mixins))
            ntext, nclass = self.hidden_pill(hidden_noncanonical, "non-canonical")

            return (result, include_mixins_updated, include_noncanonical_updated,
                    mtext, mclass, ntext, nclass)

        @self.app.callback(
            Output("elements-cats", "data", allow_duplicate=True),
            Output("include-mixins-cats", "value"),
            Output("tree-cats--hiddencount-mixins", "children"),
            Output("tree-cats--hiddenbadge-mixins", "className"),
            Input("include-mixins-cats", "value"),
            Input("node-search-cats", "data"),
            Input('tab-switch-trigger', 'value'),  # Trigger on tab switch
            State('session-biolink-version-store', 'data'),  # READ version from store
            prevent_initial_call=True  # Prevent initial call for filtering
        )
        def filter_graph_categories(
            include_mixins: List[str],
            search_nodes: Optional[List[str]],
            tab_trigger: int,
            version_tag: str
        ) -> Tuple[List[Dict[str, Any]], List[str], str, str]:
            """Filters category graph based on mixins and search."""

            # Get data from cache for the session's version
            version_data = self.get_biolink_data_for_version(version_tag)
            if not version_data or not version_data.get('bm'): # Check if data/bm loaded
                 return [], include_mixins, "", "bl-hidden-badge"
            bm = version_data['bm'] # Use the BM instance for THIS version
            elements_categories = version_data['elements_categories'] # Use elements for THIS version

            include_mixins_updated = include_mixins # Start with user's selection
            if search_nodes:
                # If a mixin was searched, force 'include mixins' checkbox
                if any(bm.category_dag.nodes[node_id].get("is_mixin") for node_id in search_nodes):
                    include_mixins_updated = ["include"]

            result = self.filter_graph(elements_categories, [], [], include_mixins_updated,
                                       search_nodes, bm.category_dag, bm)
            hidden_mixins = 0
            if "include" not in include_mixins_updated:
                with_mixins = self.filter_graph(elements_categories, [], [], ["include"],
                                                search_nodes, bm.category_dag, bm)
                hidden_mixins = self.count_nodes(with_mixins) - self.count_nodes(result)
            mtext, mclass = self.hidden_pill(hidden_mixins, self._mixins_label(hidden_mixins))
            return result, include_mixins_updated, mtext, mclass

        @self.app.callback(
            Output("elements-assoc", "data", allow_duplicate=True),
            Output("include-mixins-assoc", "value"),
            Output("tree-assoc--hiddencount-mixins", "children"),
            Output("tree-assoc--hiddenbadge-mixins", "className"),
            Input("include-mixins-assoc", "value"),
            Input("node-search-assoc", "data"),
            Input('tab-switch-trigger', 'value'),
            State('session-biolink-version-store', 'data'),
            prevent_initial_call=True
        )
        def filter_graph_associations(
            include_mixins: List[str],
            search_nodes: Optional[List[str]],
            tab_trigger: int,
            version_tag: str
        ) -> Tuple[List[Dict[str, Any]], List[str], str, str]:
            """Filters the association graph based on mixins and search."""
            version_data = self.get_biolink_data_for_version(version_tag)
            if not version_data or not version_data.get('bm'):
                return [], include_mixins, "", "bl-hidden-badge"
            bm = version_data['bm']
            elements_associations = version_data['elements_associations']

            include_mixins_updated = include_mixins
            if search_nodes:
                if any(bm.association_dag.nodes[node_id].get("is_mixin") for node_id in search_nodes):
                    include_mixins_updated = ["include"]

            result = self.filter_graph(elements_associations, [], [], include_mixins_updated,
                                       search_nodes, bm.association_dag, bm)
            hidden_mixins = 0
            if "include" not in include_mixins_updated:
                with_mixins = self.filter_graph(elements_associations, [], [], ["include"],
                                                search_nodes, bm.association_dag, bm)
                hidden_mixins = self.count_nodes(with_mixins) - self.count_nodes(result)
            mtext, mclass = self.hidden_pill(hidden_mixins, self._mixins_label(hidden_mixins))
            return result, include_mixins_updated, mtext, mclass

        # Callback to display node info (Categories Tab)
        @self.app.callback(
            Output("node-info-cats", "children"),
            Input("selected-cats", "data"),
        )
        def display_node_info_categories(selected_nodes: Optional[List[Dict[str, Any]]]) -> Any:
            """Displays information for the selected category node."""
            return self.get_node_info(selected_nodes, "cats")

        # Callback to display node info (Predicates Tab)
        @self.app.callback(
            Output("node-info-preds", "children"),
            Input("selected-preds", "data"),
        )
        def display_node_info_predicates(selected_nodes: Optional[List[Dict[str, Any]]]) -> Any:
            """Displays information for the selected predicate node."""
            return self.get_node_info(selected_nodes, "preds")

        # Callback to display node info (Associations Tab)
        @self.app.callback(
            Output("node-info-assoc", "children"),
            Input("selected-assoc", "data"),
        )
        def display_node_info_associations(selected_nodes: Optional[List[Dict[str, Any]]]) -> Any:
            """Displays information for the selected association node."""
            return self.get_node_info(selected_nodes, "assoc")

        # "Filter graph to this node" buttons: add the selected node to the search dropdown
        def add_selected_to_search(n_clicks, selected_nodes, current_search):
            # Guard against the callback firing when the button is first rendered
            # (dynamically-added components fire once with n_clicks == 0).
            if not n_clicks or not selected_nodes:
                return no_update
            node_id = selected_nodes[0].get("id")
            current_search = current_search or []
            if not node_id or node_id in current_search:
                return no_update
            return current_search + [node_id]

        @self.app.callback(
            Output("node-search-cats", "data"),
            Input("filter-to-node-cats", "n_clicks"),
            State("selected-cats", "data"),
            State("node-search-cats", "data"),
            prevent_initial_call=True,
        )
        def filter_to_selected_category(n_clicks, selected_nodes, current_search):
            return add_selected_to_search(n_clicks, selected_nodes, current_search)

        @self.app.callback(
            Output("node-search-preds", "data"),
            Input("filter-to-node-preds", "n_clicks"),
            State("selected-preds", "data"),
            State("node-search-preds", "data"),
            prevent_initial_call=True,
        )
        def filter_to_selected_predicate(n_clicks, selected_nodes, current_search):
            return add_selected_to_search(n_clicks, selected_nodes, current_search)

        @self.app.callback(
            Output("node-search-assoc", "data"),
            Input("filter-to-node-assoc", "n_clicks"),
            State("selected-assoc", "data"),
            State("node-search-assoc", "data"),
            prevent_initial_call=True,
        )
        def filter_to_selected_association(n_clicks, selected_nodes, current_search):
            return add_selected_to_search(n_clicks, selected_nodes, current_search)

        # Keep each custom multiselect in sync with its selection (the Store data): update
        # the trigger text (empty -> the CSS :empty placeholder shows) and the checked state
        # of the option rows. Driven off the Store so it reflects programmatic changes too
        # (e.g. the "focus the graph on this item" button).
        for search_id in ["node-search-cats", "node-search-preds", "node-search-assoc",
                          "domain-filter", "range-filter"]:
            self.app.clientside_callback(
                f"""
                function(data) {{
                    // data is a list (multi-select) or a single string (single-select)
                    var arr = Array.isArray(data) ? data : (data ? [data] : []);
                    var sel = {{}}; arr.forEach(function(v) {{ sel[v] = 1; }});
                    var display = document.getElementById("{search_id}--display");
                    if (display) {{
                        var wrapper = display.closest(".bl-ms-wrapper");
                        if (wrapper) {{
                            wrapper.classList.toggle("bl-ms-has-value", arr.length > 0);
                            wrapper.querySelectorAll(".bl-ms-option").forEach(function(row) {{
                                row.classList.toggle("bl-ms-selected", !!sel[row.getAttribute("data-value")]);
                            }});
                        }}
                    }}
                    return arr.length ? arr.join(", ") : "";
                }}
                """,
                Output(f"{search_id}--display", "children"),
                Input(search_id, "data"),
                prevent_initial_call=True,
            )

        # Show each tab's "Filtered view" banner when that tab has any active filter, so it's
        # obvious you're looking at a subset (and can clear it in one click).
        self.app.clientside_callback(
            "function(s){ return (s && s.length) ? 'bl-filter-banner bl-filter-banner-visible'"
            " : 'bl-filter-banner'; }",
            Output("tree-cats--filterbanner", "className"),
            Input("node-search-cats", "data"),
            prevent_initial_call=True,
        )
        self.app.clientside_callback(
            "function(s, d, r){ var any = (s && s.length) || (d && d.length) || (r && r.length);"
            " return any ? 'bl-filter-banner bl-filter-banner-visible' : 'bl-filter-banner'; }",
            Output("tree-preds--filterbanner", "className"),
            Input("node-search-preds", "data"),
            Input("domain-filter", "data"),
            Input("range-filter", "data"),
            prevent_initial_call=True,
        )
        self.app.clientside_callback(
            "function(s){ return (s && s.length) ? 'bl-filter-banner bl-filter-banner-visible'"
            " : 'bl-filter-banner'; }",
            Output("tree-assoc--filterbanner", "className"),
            Input("node-search-assoc", "data"),
            prevent_initial_call=True,
        )

        # Update the session store when version dropdown changes
        @self.app.callback(
            Output('session-biolink-version-store', 'data'),
            Input('biolink-version-input', 'value')
            # Note: No prevent_initial_call=True, we want it to run on load
            # with the initial dropdown value
        )
        def update_session_version(version_tag):
            # Just record the chosen version (fast). The actual (potentially slow) schema
            # load is deferred to update_ui_for_version below — whose outputs live inside the
            # dcc.Loading wrapper, so the "thinking" spinner shows while a new version loads.
            return version_tag

        # Update graphs, filter options, and links when session version changes
        @self.app.callback(
            Output('elements-cats', 'data'),
            Output('elements-preds', 'data'),
            Output('elements-assoc', 'data'),
            Output('category-filters-container', 'children'),
            Output('predicate-filters-container', 'children'),
            Output('association-filters-container', 'children'),
            Output('biolink-version-link', 'children'),
            Input('session-biolink-version-store', 'data') # Triggered by store change
        )
        def update_ui_for_version(version_tag):
            if not version_tag:
                return [], [], [], [], [], [], html.A() # Handle initial or error state

            # Get data from cache for the session's version
            version_data = self.get_biolink_data_for_version(version_tag)
            if not version_data: # Handle case where loading failed
                 return [], [], [], [], [], [], html.A("Error loading version", href="#")

            # Generate filter divs using data for this version
            cat_filters = self.get_filter_divs_cats(version_data['all_categories'])
            pred_filters = self.get_filter_divs_preds(version_data['all_predicates'],
                                                      version_data['domains'],
                                                      version_data['ranges'])
            assoc_filters = self.get_filter_divs_assoc(version_data['all_associations'])

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
                    style=self.styles.header_link_style
                )

            # Return updated elements and filter components. Non-canonical predicates
            # are hidden by default (matching the unchecked "Show non-canonical?" box).
            return (version_data['elements_categories'],
                    self.remove_noncanonical(version_data['elements_predicates']),
                    version_data['elements_associations'],
                    cat_filters,
                    pred_filters,
                    assoc_filters,
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
