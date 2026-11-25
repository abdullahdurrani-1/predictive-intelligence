"""Shared visual identity for all figures in the project.

One place for colours and defaults, so every notebook, the paper, and the
dashboard look like parts of the same system.
"""

import matplotlib.pyplot as plt
import plotly.graph_objects as go
import plotly.io as pio

BACKGROUND = "#0f1722"   # deep navy
PANEL = "#16202e"        # slightly lighter plot area
GRID = "#263445"
TEXT = "#d5dde6"         # soft silver-white
MUTED = "#8a98a8"

TEAL = "#2ec4b6"
BLUE = "#4a90d9"
SILVER = "#b8c4d0"
AMBER = "#f4a340"
RED = "#e05d5d"

PALETTE = [TEAL, BLUE, AMBER, SILVER, RED]


def apply_theme() -> None:
    """Set the Matplotlib and Plotly defaults used across the project."""
    plt.rcParams.update(
        {
            "figure.facecolor": BACKGROUND,
            "axes.facecolor": PANEL,
            "savefig.facecolor": BACKGROUND,
            "axes.edgecolor": GRID,
            "axes.labelcolor": TEXT,
            "axes.titlecolor": TEXT,
            "axes.titlesize": 13,
            "axes.titleweight": "bold",
            "axes.titlelocation": "left",
            "axes.grid": True,
            "grid.color": GRID,
            "grid.linewidth": 0.6,
            # Show full tick values (2388.1) instead of an offset like "+2.388e3".
            "axes.formatter.useoffset": False,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "text.color": TEXT,
            "legend.frameon": False,
            "font.size": 10,
            "figure.dpi": 110,
            "axes.prop_cycle": plt.cycler(color=PALETTE),
        }
    )

    pio.templates["predictive_intelligence"] = go.layout.Template(
        layout=go.Layout(
            paper_bgcolor=BACKGROUND,
            plot_bgcolor=PANEL,
            font=dict(color=TEXT, family="Segoe UI, Arial, sans-serif", size=13),
            title=dict(x=0.02, xanchor="left"),
            colorway=PALETTE,
            xaxis=dict(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID),
            yaxis=dict(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID),
            legend=dict(bgcolor="rgba(0,0,0,0)"),
            hoverlabel=dict(bgcolor=PANEL, font_color=TEXT),
            margin=dict(l=60, r=30, t=70, b=55),
        )
    )
    pio.templates.default = "predictive_intelligence"
