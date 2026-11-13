"""
make_flow_diagram.py
====================
Draws the preselection / self-healing decision flow used in the report.

Usage (from the repository root):  python scripts/make_flow_diagram.py
Writes figures/selfhealing_flow.png
"""
import os

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

F = "figures"
mpl.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "TeX Gyre Termes", "Liberation Serif", "DejaVu Serif"], "mathtext.fontset": "stix", "savefig.dpi": 300, "savefig.bbox": "tight"})

# 9. Self-healing decision flow -------------------------------------------------------
fig, ax = plt.subplots(figsize=(3.5, 4.2))
ax.set_xlim(0, 1); ax.set_ylim(0.05, 1.0); ax.axis("off")


def box(x, y, w, h, s, fc="white"):
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0.02", fc=fc, ec="black", lw=0.9))
    ax.text(x, y, s, ha="center", va="center", fontsize=7)


def arr(a, b, s=None, dx=0.02):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=8, lw=0.8, color="black"))
    if s:
        ax.text((a[0] + b[0]) / 2 + dx, (a[1] + b[1]) / 2, s, fontsize=6.5, va="center")


box(0.5, 0.94, 0.82, 0.07, "Read Mode 1 and Mode 2 at nominal supply\n(VDDL = VDDR = VDD)")
box(0.5, 0.81, 0.82, 0.07, "Repeat with tilted supplies VDDL = VDD $\\pm$ $V_d$,\nVDDR = VDD $\\mp$ $V_d$ ($V_d$ = 50, 80, 120 mV)")
box(0.5, 0.67, 0.62, 0.08, "Mode 1 bit identical\nin every condition?", "0.92")
box(0.15, 0.50, 0.26, 0.08, "STABLE\nkeep Mode 1 bit")
box(0.62, 0.50, 0.56, 0.08, "Mode 2 bit identical\nin every condition?", "0.92")
box(0.40, 0.31, 0.32, 0.08, "REPAIRED\nuse Mode 2 bit", "0.8")
box(0.82, 0.31, 0.30, 0.08, "DISCARDED\n(dark bit, masked)")
box(0.5, 0.12, 0.86, 0.09, "Healed key = Mode 1 (stable) $\\cup$ Mode 2 (repaired)\nper-cell mode-select / mask flags kept as helper data")
arr((0.5, 0.905), (0.5, 0.845)); arr((0.5, 0.775), (0.5, 0.71))
arr((0.24, 0.67), (0.15, 0.54), "yes", -0.09); arr((0.62, 0.63), (0.62, 0.54), "no")
arr((0.46, 0.46), (0.40, 0.35), "yes", -0.08); arr((0.78, 0.46), (0.82, 0.35), "no")
arr((0.15, 0.46), (0.15, 0.165)); arr((0.40, 0.27), (0.40, 0.165))
fig.savefig(os.path.join(F, "selfhealing_flow.png")); plt.close(fig)
print("wrote selfhealing_flow.png")
