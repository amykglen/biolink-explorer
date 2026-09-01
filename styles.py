"""
Central styling for the Biolink Explorer: a clean, modern-light design system.

All colors live here as named tokens so the look can be tuned in one place. The
Cytoscape stylesheet encodes the visual language of the graph:
  * categories / canonical predicates read as primary,
  * non-canonical predicates are visible but visually secondary (outlined, muted),
  * mixins are faded, and predicates with a non-specific domain/range are neutral.
"""


class Styles:

    def __init__(self):
        # ---- Palette (clean modern light) ---- #
        # Surfaces & text
        self.bg = "#f7f8fa"            # app canvas
        self.surface = "#ffffff"
        self.surface_alt = "#fbfcfe"
        self.border_subtle = "#e2e8f0"
        self.text = "#1e293b"          # slate-800
        self.text_muted = "#64748b"    # slate-500

        # Accent (indigo)
        self.accent = "#4f46e5"        # indigo-600
        self.accent_dark = "#4338ca"   # indigo-700
        self.accent_soft = "#6366f1"   # indigo-500
        self.accent_tint = "#eef2ff"   # indigo-50

        # Node fills
        self.node_fill = "#ffffff"
        self.node_border = self.accent_soft

        # Non-specific domain/range (neutral)
        self.node_grey = "#f1f5f9"     # slate-100
        self.node_border_grey = "#cbd5e1"  # slate-300

        # Non-canonical predicates (muted)
        self.noncanonical_fill = "#ffffff"
        self.noncanonical_border = "#cbd5e1"
        self.noncanonical_text = "#64748b"

        # Search highlight (amber) & selection (accent)
        self.highlight = "#f59e0b"     # amber-500
        self.highlight_dark = "#d97706"  # amber-600
        self.selected = self.accent
        self.selected_text = "#ffffff"

        # Edges
        self.edge = "#cbd5e1"
        self.edge_arrow = "#94a3b8"

        # Opacities
        self.regular_opacity = 1.0
        self.mixin_opacity = 0.45

        # ---- Chip colors (info panel badges) ---- #
        self.chip_domain = self.accent_tint      # domain/range category chips
        self.chip_grey = self.node_grey          # unset / root-category chips
        self.chip_canonical = "#ecfdf5"          # emerald-50  (canonical badge)
        self.chip_canonical_text = "#059669"     # emerald-600
        self.chip_peach = "#fff7ed"              # orange-50   (mixin badge)
        self.chip_peach_text = "#c2620c"
        self.chip_purple = "#faf5ff"             # purple-50   (symmetric badge)
        self.chip_purple_text = "#7e22ce"
        self.link_blue = self.accent             # hyperlink color

        # Back-compat tokens (still referenced by the legend); mapped to new palette
        self.node_green = self.accent_tint
        self.node_border_green = self.accent

        # ---- Shared component styles ---- #
        self.font_family = ("-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, "
                            "'Helvetica Neue', Arial, sans-serif")

        # Right-hand detail panel (shows info for the selected node)
        self.detail_panel_style = {
            "width": "340px",
            "flexShrink": 0,
            "height": "100%",
            "overflowY": "auto",
            "padding": "22px 22px 32px 22px",
            "backgroundColor": self.surface,
            "borderLeft": f"1px solid {self.border_subtle}",
            "color": self.text,
            "boxSizing": "border-box",
        }
        # Small, uppercase section label
        self.detail_label_style = {
            "fontSize": "11px",
            "fontWeight": 600,
            "letterSpacing": "0.06em",
            "textTransform": "uppercase",
            "color": self.text_muted,
            "marginBottom": "5px",
            "marginTop": "18px",
        }
        self.detail_value_style = {
            "fontSize": "14px",
            "lineHeight": "1.5",
            "color": self.text,
            "whiteSpace": "pre-wrap",
        }

        self.hyperlink_style = {
            "color": self.link_blue,
            "textDecoration": "none",
            "fontWeight": 500,
        }

        # ---- Cytoscape stylesheet ---- #
        # The graph itself is drawn by assets/tree.js (a D3 left-to-right tidy tree).
        # Its node/link colors mirror the palette tokens above; the visual language is:
        #   * categories & canonical predicates: solid accent border,
        #   * non-canonical predicates: dashed, muted border,
        #   * non-specific domain/range: neutral grey,
        #   * mixins: faded,
        #   * searched: amber ring,  selected: solid accent fill.

        self.filters_wrapper_style = {
            "margin": "12px 10px 6px 10px",
            "display": "flex",
            "flex-direction": "row",
            "width": "100%",
            "gap": "6px",
        }
