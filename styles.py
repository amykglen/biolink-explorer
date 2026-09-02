"""
Central styling for the Biolink Explorer: a warm, modern-light design system.

All colors live here as named tokens so the look can be tuned in one place. The
graph itself is drawn by assets/tree.js, whose palette mirrors these tokens. The
visual language of the graph:
  * categories / canonical predicates read as primary (filled accent circle),
  * non-canonical predicates are secondary (open/hollow circle),
  * predicates with a non-specific domain/range are neutral grey,
  * mixins are faded, searched nodes get a gold ring, selection fills the circle.
"""

# Loaded via Google Fonts (see main.py); falls back to the system stack.
FONT_STACK = ("'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, "
              "'Helvetica Neue', Arial, sans-serif")


class Styles:

    def __init__(self):
        # ---- Palette ---- #
        # The APP accent (chrome: header, tabs, links, buttons, highlights) is gold.
        # In the GRAPH, node color is a separate encoding: green = regular, gold = mixin.
        # Surfaces & (near-)neutral greys — just a whisper of warmth
        self.bg = "#f8f7f4"            # neutral canvas (graph background)
        self.surface = "#fefefc"
        self.surface_alt = "#efeee9"
        self.border_subtle = "#e6e3de"
        self.text = "#2a2825"          # neutral near-black
        self.text_muted = "#7c7871"    # neutral grey

        # App accent (teal) — chrome (header, tabs, links, buttons) AND regular nodes
        self.accent = "#2d8f83"
        self.accent_dark = "#1f6d64"   # darker teal, for readable text/links
        self.accent_soft = "#7bbcb4"
        self.accent_tint = "#e4f0ee"

        # Graph node colors: regular = teal (the primary), mixin = gold
        self.node_regular = self.accent
        self.node_regular_dark = self.accent_dark
        self.node_regular_tint = self.accent_tint
        self.node_mixin = "#bd901f"         # gold
        self.node_mixin_dark = "#93701a"
        self.node_mixin_tint = "#f6efd8"

        # Node fills
        self.node_fill = self.surface
        self.node_border = self.node_regular

        # Non-specific domain/range (neutral)
        self.node_grey = "#ebe9e5"
        self.node_border_grey = "#cecac3"

        # Non-canonical predicates (muted)
        self.noncanonical_fill = self.surface
        self.noncanonical_border = "#cecac3"
        self.noncanonical_text = "#7c7871"

        # Search highlight (rust, distinct from both green and gold)
        self.highlight = "#c0562f"
        self.highlight_dark = "#a3461f"
        self.selected = self.accent
        self.selected_text = "#ffffff"

        # Edges
        self.edge = "#dad6cf"
        self.edge_arrow = "#b5b0a7"

        # Opacities
        self.regular_opacity = 1.0
        self.mixin_opacity = 0.45

        # ---- Chip colors (detail-panel value colors) ---- #
        self.chip_domain = "#efedea"                 # domain/range category chips (neutral)
        self.chip_grey = self.node_grey              # unset / root-category chips
        self.chip_canonical = "#e7f0e3"              # green (canonical "Yes")
        self.chip_canonical_text = "#4e7038"
        self.chip_peach = self.node_mixin_tint        # gold (mixin "Yes", matches mixin node)
        self.chip_peach_text = self.node_mixin_dark
        self.chip_purple = "#e3edf5"                 # blue (symmetric "Yes")
        self.chip_purple_text = "#2f6690"
        self.link_blue = self.accent_dark            # hyperlink color (readable gold)

        # Legend back-compat tokens
        self.node_green = self.accent_tint
        self.node_border_green = self.accent

        # ---- Shared component styles ---- #
        self.font_family = FONT_STACK

        # Right-hand detail panel (width is a CSS var so it can be dragged; see resize.js)
        self.detail_panel_style = {
            "position": "relative",
            "width": "var(--bl-panel-width, 410px)",
            "flexShrink": 0,
            "height": "100%",
            "backgroundColor": self.surface,
            "borderLeft": f"1px solid {self.border_subtle}",
            "color": self.text,
            "boxSizing": "border-box",
        }
        # The scrollable content inside the panel (children replaced by callbacks)
        self.detail_content_style = {
            "height": "100%",
            "overflowY": "auto",
            "padding": "24px 24px 34px 24px",
            "boxSizing": "border-box",
        }
        # Drag handle on the panel's left edge
        self.panel_resize_handle_style = {
            "position": "absolute",
            "left": "-3px",
            "top": "0",
            "width": "7px",
            "height": "100%",
            "cursor": "col-resize",
            "zIndex": 5,
        }
        self.detail_label_style = {
            "fontSize": "10.5px",
            "fontWeight": 600,
            "letterSpacing": "0.07em",
            "textTransform": "uppercase",
            "color": self.text_muted,
            "marginBottom": "6px",
            "marginTop": "20px",
        }
        self.detail_value_style = {
            "fontSize": "13px",
            "lineHeight": "1.55",
            "color": self.text,
            "whiteSpace": "pre-wrap",
        }

        self.hyperlink_style = {
            "color": self.link_blue,
            "textDecoration": "none",
            "fontWeight": 500,
        }

        # "Filter graph to this node" icon button (top-right of the detail panel)
        self.filter_icon_button_style = {
            "display": "inline-flex",
            "alignItems": "center",
            "justifyContent": "center",
            "width": "30px",
            "height": "30px",
            "padding": "0",
            "flexShrink": 0,
            "backgroundColor": self.accent_tint,
            "border": f"1px solid {self.accent_soft}",
            "borderRadius": "7px",
            "cursor": "pointer",
        }

        # ---- Header bar (teal, light text) ---- #
        self.header_bg = self.accent
        self.header_style = {
            "display": "flex",
            "justifyContent": "space-between",
            "alignItems": "center",
            "padding": "6px 18px",
            "backgroundColor": self.header_bg,
        }
        self.header_title_style = {
            "fontSize": "15px",
            "fontWeight": 700,
            "color": "#fbfdfc",
            "letterSpacing": "-0.01em",
        }
        self.header_text_style = {
            "color": "rgba(255, 255, 255, 0.82)",
            "fontSize": "12.5px",
        }
        self.header_link_style = {
            "color": "#e9f4f2",
            "textDecoration": "underline",
            "fontWeight": 600,
        }
        # Info icon button in the header
        self.header_icon_button_style = {
            "display": "inline-flex",
            "alignItems": "center",
            "justifyContent": "center",
            "width": "30px",
            "height": "30px",
            "padding": "0",
            "backgroundColor": "transparent",
            "border": "none",
            "borderRadius": "7px",
            "cursor": "pointer",
        }

        # ---- About / info modal ---- #
        self.modal_backdrop_style = {
            "display": "none",          # toggled to "flex" by assets/modal.js
            "position": "fixed",
            "inset": "0",
            "backgroundColor": "rgba(30, 27, 22, 0.45)",
            "zIndex": 1000,
            "alignItems": "flex-start",
            "justifyContent": "center",
            "padding": "6vh 20px",
        }
        self.modal_card_style = {
            "position": "relative",
            "backgroundColor": self.surface,
            "borderRadius": "12px",
            "boxShadow": "0 24px 60px -20px rgba(30, 27, 22, 0.5)",
            "maxWidth": "720px",
            "width": "92%",
            "maxHeight": "84vh",
            "overflowY": "auto",
            "padding": "30px 34px 34px 34px",
            "boxSizing": "border-box",
            "color": self.text,
        }
        self.modal_close_style = {
            "position": "absolute",
            "top": "14px",
            "right": "16px",
            "width": "30px",
            "height": "30px",
            "padding": "0",
            "backgroundColor": "transparent",
            "border": "none",
            "borderRadius": "7px",
            "fontSize": "17px",
            "lineHeight": "1",
            "color": self.text_muted,
            "cursor": "pointer",
        }

        # ---- Toolbar (filter row) ---- #
        self.filters_wrapper_style = {
            "display": "flex",
            "flexDirection": "row",
            "flexWrap": "wrap",
            "alignItems": "flex-end",
            "gap": "20px",
            "width": "100%",
            "padding": "14px 18px",
            "backgroundColor": self.surface,
            "borderBottom": f"1px solid {self.border_subtle}",
            "boxSizing": "border-box",
        }
        self.filter_label_style = {
            "display": "block",
            "fontSize": "12px",
            "fontWeight": 600,
            "color": self.text_muted,
            "marginBottom": "7px",
            "letterSpacing": "0.01em",
        }

        # ---- Tabs (left-aligned, underline-style active) ---- #
        self.tabs_container_style = {
            "display": "flex",
            "justifyContent": "flex-start",
            "borderBottom": f"1px solid {self.border_subtle}",
            "backgroundColor": self.surface,
        }
        self.tab_style = {
            "flex": "0 0 auto",
            "padding": "11px 20px",
            "border": "none",
            "borderBottom": "2px solid transparent",
            "backgroundColor": "transparent",
            "color": self.text_muted,
            "fontFamily": self.font_family,
            "fontWeight": 500,
            "fontSize": "14px",
        }
        self.tab_selected_style = {
            "flex": "0 0 auto",
            "padding": "11px 20px",
            "border": "none",
            "borderBottom": f"2px solid {self.accent}",
            "backgroundColor": "transparent",
            "color": self.accent_dark,
            "fontFamily": self.font_family,
            "fontWeight": 600,
            "fontSize": "14px",
        }
