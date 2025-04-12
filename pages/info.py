from typing import List

import dash
from dash import html  # Use 'callback' decorator directly

from app import styles

# --- Register Page ---
dash.register_page(
    __name__,
    path='/info',  # Set as the default/home page route
    name='Info', # Name for navigation links
    title='Info' # Browser tab title
)


# --- Helper function --

def get_app_info_content() -> List[html.Div]:
    """Generates the content for the 'Info' tab."""
    chip_style_green = styles.get_chip_style(
        styles.node_green,
        opacity=styles.regular_opacity,
        border=f"2px solid {styles.node_border_green}",
    )
    chip_style_grey = styles.get_chip_style(
        styles.node_grey,
        opacity=styles.regular_opacity,
        border=f"2px solid {styles.node_border_grey}",
    )
    chip_style_green_transparent = styles.get_chip_style(
        styles.node_green,
        opacity=styles.mixin_opacity,
        border="0px solid black",
    )
    chip_style_grey_transparent = styles.get_chip_style(
        styles.node_grey,
        opacity=styles.mixin_opacity,
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
                "height": "calc(100vh - 150px)",  # Adjust based on header/tabs
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
                            style=styles.hyperlink_style,
                        ),
                        ", an open-source schema for biomedical knowledge graphs developed by the ",
                        html.A(
                            "NCATS Biomedical Data Translator",
                            href="https://ncats.nih.gov/research/research-activities/translator",
                            target="_blank",
                            style=styles.hyperlink_style,
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
                    The 'Predicates' tab shows the hierarchy of relationship predicates in the Biolink Model 
                    (non-canonical predicates are excluded).
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
                            style=styles.hyperlink_style,
                        ),
                        " about that item in the area below the graph. Scroll over the graph to zoom in or out.",
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
                            style=styles.hyperlink_style,
                        ),
                        " at ",
                        html.A(
                            "Phenome Health",
                            href="https://www.phenomehealth.org",
                            target="_blank",
                            style=styles.hyperlink_style,
                        ),
                        ". Its source code lives ",
                        html.A(
                            "here",
                            href="https://github.com/amykglen/biolink-explorer",
                            target="_blank",
                            style=styles.hyperlink_style,
                        ),
                        ".",
                    ]
                ),
            ],
        )
    ]
    return info_content


# --- Page Layout Definition ---
def layout() -> html.Div:
    return html.Div(get_app_info_content())


