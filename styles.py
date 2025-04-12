from typing import Optional, Any, Dict


class Styles:

    def __init__(self):
        self.root_category = "NamedThing"
        self.root_predicate = "related_to"

        self.node_green = "#dae3b6"
        self.node_border_green = "#bece7f"
        self.node_grey = "#e9e9e9"
        self.node_border_grey = "#cfcfcf"
        self.highlight_orange = "#ff5500"
        self.highlight_border_orange = "#e64c00"
        self.edge_grey = "#b4b4b4"
        self.chip_green = "#E8EED2"
        self.chip_grey = "#ececec"
        self.chip_peach = "#FFEBC2"
        self.chip_purple = "#F7DEEA"
        self.link_blue = "#26a1c9"  # 2c9ab7
        self.regular_opacity = 0.7
        self.mixin_opacity = 0.4

        self.node_info_div_style = {
            "position": "absolute",
            "bottom": "0",
            "width": "100%",
            "padding": "20px",
            "background-color": "#f9f9f9",
            "border-top": "1px solid #ddd",
            "text-align": "center",
            "color": "black"
        }

        self.hyperlink_style = {
            "color": self.link_blue
        }

        self.main_styling = [
            # Style for nodes: small black circles with labels to the right, with colored label backgrounds
            {"selector": "node", "style": {
                "background-color": self.node_green,
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
                "background-opacity": self.regular_opacity,
                "border-width": "2px",
                "border-color": self.node_border_green,
                "border-opacity": self.regular_opacity
            }},
            # Special style for nodes with certain classes
            {"selector": ".mixin",
             "style": {
                 "border-width": "0px",
                 "color": "grey",
                 "background-opacity": self.mixin_opacity
             }},
            {"selector": ".unspecific",
             "style": {
                 "background-color": self.node_grey,
                 "border-color": self.node_border_grey
             }},
            {"selector": ".searched",
             "style": {
                 "border-width": "3px",
                 "border-color": self.highlight_orange
             }},
            # Style for edges: curved edges
            {"selector": "edge", "style": {
                "width": 0.5,
                "line-color": self.edge_grey,
                "target-arrow-shape": "triangle",
                "target-arrow-color": self.edge_grey,
                "arrow-scale": 0.6,
                'curve-style': 'bezier',
            }},
            # Optional: Style for selected nodes/edges
            {"selector": ":selected", "style": {
                "background-color": self.highlight_orange,
                "border-color": self.highlight_border_orange,
            }}
        ]

        self.filters_wrapper_style = {"margin": "10px", "display": "flex", "flex-direction": "row", "width": "100%"}

        self.layout_settings = {"name": "dagre",
                           "rankDir": "LR",  # Can be LR (left-to-right) or TB (top-to-bottom)
                           "spacingFactor": 0.34,  # Adjust spacing between nodes
                           "nodeDimensionsIncludeLabels": True,
                           # "nodeSep": 50,  # Adjust horizontal spacing
                           "rankSep": 640}  # Adjust vertical spacing (between ranks)

        self.tab_content_style = {
            "display": "flex",
            "flexDirection": "column",
            # Adjust height based on header and tabs
            "height": "calc(100vh - 110px)",
        }
        self.cytoscape_style = {"width": "100%", "height": "100%"}

    def get_chip_style(
            self,
            color: str,
            chip_value: Optional[Any] = "value_present",  # Use a sentinel instead of None directly
            opacity: Optional[float] = None,
            border: Optional[str] = None,
            circular: bool = False
    ) -> Dict[str, Any]:
        """
        Generates a style dictionary for visual 'chip' elements.
        Grey out chip if value is None or the root category.
        """
        final_color = color
        if chip_value is None or chip_value == self.root_category:
            final_color = self.chip_grey

        chip_style: Dict[str, Any] = {
            "padding": "2px 5px",
            "borderRadius": "10px" if circular else "3px",
            "backgroundColor": final_color,
            "marginLeft": "8px",
            "fontSize": "15px",
            "display": "inline-block",
            "color": "black",  # Ensure text visibility
        }
        if opacity is not None:
            chip_style["opacity"] = opacity
        if border:
            chip_style["border"] = border
        return chip_style