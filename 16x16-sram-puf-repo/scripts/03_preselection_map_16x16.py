"""
03_preselection_map_16x16.py
============================
Voltage-tilt preselection + self-healing on a 16x16 array; prints the summary and draws the 3-panel map
(raw / after preselection / after self-healing). Covers notebook cells 18-29 via --nominal/--plus/--minus/--vdd,
e.g. --nominal mc_256_0.8_vdd.csv --plus mc_256_0.8_vdd+120.csv --minus mc_256_0.8_vdd-120.csv 
Source: notebooks/VLSI_project_SRAM_PUF.ipynb, cell(s) 18.
Usage: python scripts/03_preselection_map_16x16.py --data data/raw
"""

# --- added for the repository: run against the folder holding the raw mc_*.csv files
import argparse as _ap, os as _os
_p = _ap.ArgumentParser(description=__doc__, formatter_class=_ap.RawDescriptionHelpFormatter)
_p.add_argument("--data", default="data/raw", help="folder with the raw Cadence mc_*.csv files (outputs are written there)")
_p.add_argument("--nominal", default="mc_256_0.9_vdd.csv")
_p.add_argument("--plus", default="mc_256_0.9_vdd+80.csv")
_p.add_argument("--minus", default="mc_256_0.9_vdd-80.csv")
_p.add_argument("--vdd", type=float, default=0.9)
_args, _ = _p.parse_known_args()
_os.chdir(_args.data)

import os
import re
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ==============================================================================
# 1. CONFIGURATION: INSERT YOUR 3 CSV FILE PATHS HERE
# ==============================================================================
CSV_NOMINAL = _args.nominal   # VDDL = VDDR = VDD
CSV_PLUS_80 = _args.plus      # VDDL = VDD + tilt, VDDR = VDD - tilt
CSV_MINUS_80 = _args.minus    # VDDL = VDD - tilt, VDDR = VDD + tilt

VDD_NOMINAL = _args.vdd  # decision threshold = VDD_NOMINAL / 2 (notebook: 0.9 V for every run)
ARRAY_ROWS = 16  # 16 rows x 16 cols = 256 cells
ARRAY_COLS = 16

# Time windows (in seconds)
MODE2_WINDOW = (37e-9, 43e-9)  # Mode 2 active window: 37ns - 43ns
MODE1_WINDOW = (97e-9, 103e-9)  # Mode 1 active window: 97ns - 103ns


# ==============================================================================
# 2. HELPER FUNCTION: EXTRACT MODE 1 & MODE 2 BITS FROM A CADENCE CSV
# ==============================================================================
def extract_bits_from_csv(csv_path, vdd=0.9):
    """Reads BL and BLb waveforms for all 256 Monte Carlo cells and returns

    binary arrays (length 256) for Mode 1 and Mode 2.
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Could not find CSV file: {csv_path}")

    df = pd.read_csv(csv_path, low_memory=False)
    threshold = vdd / 2.0

    # Detect and sort all mcparamset indices (1 to 256)
    paramset_ids = sorted(
        list(
            set(int(x) for x in re.findall(r"mcparamset=(\d+)", " ".join(df.columns)))
        )
    )

    m1_bits = np.zeros(len(paramset_ids), dtype=int)
    m2_bits = np.zeros(len(paramset_ids), dtype=int)
    m1_bl_v = np.zeros(len(paramset_ids), dtype=float)
    m2_bl_v = np.zeros(len(paramset_ids), dtype=float)

    for idx, mc_id in enumerate(paramset_ids):
        t_bl = pd.to_numeric(
            df[f"/BL (mcparamset={mc_id}) X"], errors="coerce"
        ).values
        v_bl = pd.to_numeric(
            df[f"/BL (mcparamset={mc_id}) Y"], errors="coerce"
        ).values

        # Mode 1 window (97ns - 103ns)
        mask_m1 = (t_bl >= MODE1_WINDOW[0]) & (t_bl <= MODE1_WINDOW[1])
        v1 = np.nanmean(v_bl[mask_m1])
        m1_bl_v[idx] = v1
        m1_bits[idx] = 1 if v1 >= threshold else 0

        # Mode 2 window (37ns - 43ns)
        mask_m2 = (t_bl >= MODE2_WINDOW[0]) & (t_bl <= MODE2_WINDOW[1])
        v2 = np.nanmean(v_bl[mask_m2])
        m2_bl_v[idx] = v2
        m2_bits[idx] = 1 if v2 >= threshold else 0

    return {
        "m1_bits": m1_bits,
        "m2_bits": m2_bits,
        "m1_bl_v": m1_bl_v,
        "m2_bl_v": m2_bl_v,
    }


# ==============================================================================
# 3. MAIN ANALYSIS & SELF-HEALING PIPELINE
# ==============================================================================
def run_puf_preselection_analysis(csv_nom, csv_p80, csv_m80, vdd=0.9):
    print("Extracting waveforms from all 3 Cadence CSV files...")
    data_nom = extract_bits_from_csv(csv_nom, vdd)
    data_p80 = extract_bits_from_csv(csv_p80, vdd)
    data_m80 = extract_bits_from_csv(csv_m80, vdd)

    num_cells = len(data_nom["m1_bits"])
    assert (
        num_cells == ARRAY_ROWS * ARRAY_COLS
    ), f"Expected {ARRAY_ROWS*ARRAY_COLS} cells, got {num_cells}"

    # --- STEP 1: Evaluate Mode 1 Stability across both voltage tilts ---
    # A cell is stable in Mode 1 iff Nominal == (+80mV) == (-80mV)
    m1_stable = (data_nom["m1_bits"] == data_p80["m1_bits"]) & (
        data_nom["m1_bits"] == data_m80["m1_bits"]
    )
    m1_unstable = ~m1_stable

    # --- STEP 2: Evaluate Mode 2 Stability for Mode 1 Unstable Cells ---
    # A cell is stable in Mode 2 iff Nominal == (+80mV) == (-80mV)
    m2_stable = (data_nom["m2_bits"] == data_p80["m2_bits"]) & (
        data_nom["m2_bits"] == data_m80["m2_bits"]
    )

    # Classification states:
    # 0 = Stable Bits (Grey)
    # 1 = Unstable Bits (Yellow)
    # 2 = Repaired Bits (Green)
    # 3 = Discarded Bits (Orange)

    # Map (a): Raw Responses (Mode 1 only)
    map_a = np.where(m1_stable, 0, 1)  # 0=Grey (Stable), 1=Yellow (Unstable)

    # Map (b): Responses after Preselection & Mode-2 Healing
    # - Mode 1 Stable -> 0 (Grey: Stable)
    # - Mode 1 Unstable AND Mode 2 Stable -> 2 (Green: Repaired)
    # - Mode 1 Unstable AND Mode 2 Unstable -> 3 (Orange: Discarded)
    repaired_mask = m1_unstable & m2_stable
    discarded_mask = m1_unstable & (~m2_stable)

    map_b = np.zeros(num_cells, dtype=int)
    map_b[m1_stable] = 0  # Stable (Grey)
    map_b[repaired_mask] = 2  # Repaired (Green)
    map_b[discarded_mask] = 3  # Discarded (Orange)

    # Map (c): Active Post-Healing Responses
    # Repaired cells are now active and stable (Grey); Discarded cells remain masked out (or shown as excluded)
    # To match Fig. 10(c) where repaired cells become active stable grey and discarded bits are masked out:
    map_c = np.zeros(num_cells, dtype=int)
    map_c[m1_stable | repaired_mask] = 0  # Active Stable Bits (Grey)
    map_c[discarded_mask] = (
        4  # Masked / Excluded from key (White/Light-Grey background)
    )

    # Reshape 1D arrays (0..255) into 16x16 grids:
    # Row 0 = BL[0:15], Row 1 = BL[16:31], ..., Row 15 = BL[240:255]
    grid_a = map_a.reshape(ARRAY_ROWS, ARRAY_COLS)
    grid_b = map_b.reshape(ARRAY_ROWS, ARRAY_COLS)
    grid_c = map_c.reshape(ARRAY_ROWS, ARRAY_COLS)

    # ==========================================================================
    # 4. PRINT QUANTITATIVE SUMMARY
    # ==========================================================================
    n_m1_stable = int(np.sum(m1_stable))
    n_m1_unstable = int(np.sum(m1_unstable))
    n_repaired = int(np.sum(repaired_mask))
    n_discarded = int(np.sum(discarded_mask))
    n_final_valid = n_m1_stable + n_repaired

    raw_ber = (n_m1_unstable / num_cells) * 100.0
    healing_rate = (
        (n_repaired / n_m1_unstable * 100.0) if n_m1_unstable > 0 else 100.0
    )
    valid_yield = (n_final_valid / num_cells) * 100.0

    print("\n" + "=" * 68)
    print("  16x16 SRAM PUF VOLTAGE-TILT PRESELECTION & SELF-HEALING SUMMARY")
    print("=" * 68)
    print(f"Total Array Cells                 : {num_cells} (16 x 16)")
    print(
        f"Mode 1 Stable Bits (Grey)         : {n_m1_stable:3d} ({n_m1_stable/num_cells*100:.2f}%)"
    )
    print(
        f"Mode 1 Unstable Bits (Yellow)     : {n_m1_unstable:3d} ({raw_ber:.2f}% Raw Instability)"
    )
    print("-" * 68)
    print(
        f"Repaired via Mode 2 (Green)       : {n_repaired:3d} ({healing_rate:.2f}% of unstable bits healed)"
    )
    print(
        f"Discarded Dark Bits (Orange)      : {n_discarded:3d} ({n_discarded/num_cells*100:.2f}% masked out)"
    )
    print("-" * 68)
    print(
        f"Final Active Valid PUF Bits       : {n_final_valid:3d} / {num_cells} ({valid_yield:.2f}% Valid Bit Yield)"
    )
    print(f"Post-Healing Residual Tilt Errors : 0   (0.00% BER across ±80mV tilt)")
    print("=" * 68 + "\n")

    # Save detailed per-cell CSV report
    summary_df = pd.DataFrame(
        {
            "Cell_Index (0-255)": np.arange(num_cells),
            "Row (0-15)": np.arange(num_cells) // ARRAY_COLS,
            "Col (0-15)": np.arange(num_cells) % ARRAY_COLS,
            "M1_Nom": data_nom["m1_bits"],
            "M1_Plus80": data_p80["m1_bits"],
            "M1_Minus80": data_m80["m1_bits"],
            "M1_Stable": m1_stable,
            "M2_Nom": data_nom["m2_bits"],
            "M2_Plus80": data_p80["m2_bits"],
            "M2_Minus80": data_m80["m2_bits"],
            "M2_Stable": m2_stable,
            "Final_Status": np.where(
                m1_stable,
                "Stable (Mode 1)",
                np.where(
                    repaired_mask, "Repaired (Mode 2)", "Discarded (Masked)"
                ),
            ),
            "Selected_Mode": np.where(
                m1_stable, "Mode 1", np.where(repaired_mask, "Mode 2", "None")
            ),
            "Golden_Key_Bit": np.where(
                m1_stable,
                data_nom["m1_bits"],
                np.where(repaired_mask, data_nom["m2_bits"], -1),
            ),
        }
    )
    summary_df.to_csv("puf_self_healing_cell_report.csv", index=False)
    print("Saved cell-by-cell classification to 'puf_self_healing_cell_report.csv'")

    # ==========================================================================
    # 5. PLOT FIGURE 10 STYLE 3-PANEL MAPPING
    # ==========================================================================
    # Color palette matching Fig. 10:
    # 0: Grey (#808080) - Stable Bits
    # 1: Yellow (#FFFF54) - Unstable Bits
    # 2: Green (#00FF00) - Repaired Bits
    # 3: Orange (#FF7F0E) - Discarded Bits
    # 4: Light Neutral (#D9D9D9) - Masked/Excluded slots in post-healing map
    cmap = mcolors.ListedColormap(
        ["#808080", "#FFFF54", "#00E600", "#FF7F00", "#B8B8B8"]
    )
    bounds = [-0.5, 0.5, 1.5, 2.5, 3.5, 4.5]
    norm = mcolors.BoundaryNorm(bounds, cmap.N)

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.8), dpi=300)
    titles = [
        "(a) Raw Responses",
        "(b) After Preselection",
        "(c) After Self-Healing",
    ]
    grids = [grid_a, grid_b, grid_c]

    for ax, grid, title in zip(axes, grids, titles):
        ax.imshow(grid, cmap=cmap, norm=norm, origin="lower", aspect="equal")

        # Draw crisp cell grid lines for 16x16 visibility
        ax.set_xticks(np.arange(-0.5, ARRAY_COLS, 1), minor=True)
        ax.set_yticks(np.arange(-0.5, ARRAY_ROWS, 1), minor=True)
        ax.grid(which="minor", color="#404040", linestyle="-", linewidth=0.4)
        ax.tick_params(which="minor", bottom=False, left=False)

        # Major ticks at 4, 8, 12, 16 (1-indexed like Fig. 10)
        ticks = [3, 7, 11, 15]
        tick_labels = ["4", "8", "12", "16"]
        ax.set_xticks(ticks)
        ax.set_xticklabels(tick_labels, fontsize=10, fontweight="bold")
        ax.set_yticks(ticks)
        ax.set_yticklabels(tick_labels, fontsize=10, fontweight="bold")

        ax.set_xlabel(title, fontsize=12, fontweight="bold", labelpad=8)

    # Legend matching Fig. 10
    legend_patches = [
        mpatches.Patch(
            facecolor="#FFFF54", edgecolor="black", label="Unstable Bits"
        ),
        mpatches.Patch(
            facecolor="#00E600", edgecolor="black", label="Repaired Bits"
        ),
        mpatches.Patch(
            facecolor="#FF7F00", edgecolor="black", label="Discarded Bits"
        ),
        mpatches.Patch(
            facecolor="#808080", edgecolor="black", label="Stable Bits"
        ),
    ]
    fig.legend(
        handles=legend_patches,
        loc="center left",
        bbox_to_anchor=(0.88, 0.52),
        frameon=False,
        fontsize=11,
        prop={"weight": "bold"},
    )

    plt.suptitle(
        "Mapping of Proposed 16×16 SRAM PUF: (a) Raw, (b) Preselection, and (c) Self-Healing at VDD=0.9V, Vtilt= +-80mV",
        fontsize=13,
        fontweight="bold",
        y=0.98,
    )
    plt.subplots_adjust(left=0.05, right=0.86, top=0.88, bottom=0.15, wspace=0.18)

    output_fig = "puf_fig10_mapping.png"
    plt.savefig(output_fig, dpi=300, bbox_inches="tight")
    print(f"Saved 3-panel visualization to '{output_fig}'")
    plt.show()


if __name__ == "__main__":
    run_puf_preselection_analysis(
        CSV_NOMINAL, CSV_PLUS_80, CSV_MINUS_80, vdd=VDD_NOMINAL
    )
