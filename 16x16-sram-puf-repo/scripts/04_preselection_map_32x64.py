"""
04_preselection_map_32x64.py
============================
Preselection + self-healing on the 32x64 (2048-cell) array; also writes the 2028-bit golden key.
Source: notebooks/VLSI_project_SRAM_PUF.ipynb, cell(s) 30.
Usage: python scripts/04_preselection_map_32x64.py --data data/raw
"""

# --- added for the repository: run against the folder holding the raw mc_*.csv files
import argparse as _ap, os as _os
_p = _ap.ArgumentParser(description=__doc__, formatter_class=_ap.RawDescriptionHelpFormatter)
_p.add_argument("--data", default="data/raw", help="folder with the raw Cadence mc_*.csv files (outputs are written there)")
_p.add_argument("--nominal", default="mc_2048__0.9_vdd.csv")
_p.add_argument("--plus", default="mc_2048_0.9_vdd+120.csv")
_p.add_argument("--minus", default="mc_2048_0.9_vdd-120.csv")
_p.add_argument("--vdd", type=float, default=0.9)
_args, _ = _p.parse_known_args()
_os.chdir(_args.data)

import os
import re
import matplotlib
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ==============================================================================
# 1. CONFIGURATION: INSERT YOUR 3 CSV FILE PATHS HERE (2048 CELLS EACH)
# ==============================================================================
CSV_NOMINAL = _args.nominal
CSV_PLUS_80 = _args.plus
CSV_MINUS_80 = _args.minus

VDD_NOMINAL = _args.vdd
ARRAY_ROWS = 32    # 32 rows x 64 cols = 2048 cells
ARRAY_COLS = 64

# Time windows (in seconds)
MODE2_WINDOW = (37e-9, 43e-9)    # Mode 2 active window: 37ns - 43ns
MODE1_WINDOW = (97e-9, 103e-9)   # Mode 1 active window: 97ns - 103ns


# ==============================================================================
# 2. HELPER FUNCTION: EXTRACT MODE 1 & MODE 2 BITS FROM A 2048-CELL CADENCE CSV
# ==============================================================================
def extract_bits_from_csv(csv_path, vdd=0.9):
    """Reads BL waveforms for all 2048 Monte Carlo cells and returns
    binary arrays (length 2048) for Mode 1 and Mode 2.
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Could not find CSV file: {csv_path}")

    df = pd.read_csv(
        csv_path,
        usecols=lambda c: "/BL (" in c or c.strip().startswith("/BL "),
        low_memory=False,
    )
    threshold = vdd / 2.0

    paramset_ids = sorted(
        list(
            set(
                int(x)
                for x in re.findall(r"mcparamset=(\d+)", " ".join(df.columns))
            )
        )
    )

    if not paramset_ids:
        raise ValueError(
            f"No '/BL (mcparamset=...)' columns found in {csv_path}. "
            "Check if the net name changed in Cadence."
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

        # Auto-detect if Cadence exported time in nanoseconds instead of seconds
        valid_t = t_bl[~np.isnan(t_bl)]
        if idx == 0:
            t_min, t_max = np.min(valid_t), np.max(valid_t)
            print(f"  [{os.path.basename(csv_path)}] Time range: {t_min:.3e} to {t_max:.3e}")

        # If max time > 1.0, timestamps are in nanoseconds -> convert to seconds
        if np.nanmax(valid_t) > 1.0:
            t_bl = t_bl * 1e-9

        # Mode 1 window (97ns - 103ns)
        mask_m1 = (t_bl >= MODE1_WINDOW[0]) & (t_bl <= MODE1_WINDOW[1])
        v1 = np.nanmean(v_bl[mask_m1]) if np.any(mask_m1) else np.nan
        m1_bl_v[idx] = v1
        m1_bits[idx] = 1 if v1 >= threshold else 0

        # Mode 2 window (37ns - 43ns)
        mask_m2 = (t_bl >= MODE2_WINDOW[0]) & (t_bl <= MODE2_WINDOW[1])
        v2 = np.nanmean(v_bl[mask_m2]) if np.any(mask_m2) else np.nan
        m2_bl_v[idx] = v2
        m2_bits[idx] = 1 if v2 >= threshold else 0

    # Catch empty windows before they silently turn into all-0 bit arrays
    if np.isnan(m1_bl_v).all() or np.isnan(m2_bl_v).all():
        raise ValueError(
            f"Time windows {MODE2_WINDOW} or {MODE1_WINDOW} matched NO data in {csv_path}! "
            "Adjust MODE1_WINDOW / MODE2_WINDOW to match the printed time range above."
        )

    print(
        f"  [{os.path.basename(csv_path)}] "
        f"M1 mean V={np.nanmean(m1_bl_v):.3f}V (1s={np.sum(m1_bits)}), "
        f"M2 mean V={np.nanmean(m2_bl_v):.3f}V (1s={np.sum(m2_bits)})"
    )

    return {
        "m1_bits": m1_bits,
        "m2_bits": m2_bits,
        "m1_bl_v": m1_bl_v,
        "m2_bl_v": m2_bl_v,
    }


# ==============================================================================
# 3. MAIN ANALYSIS & SELF-HEALING PIPELINE (32 x 64 = 2048 CELLS)
# ==============================================================================
def run_puf_preselection_analysis(csv_nom, csv_p80, csv_m80, vdd=0.9):
    print("Extracting waveforms from all 3 Cadence CSV files (2048 cells)...")
    data_nom = extract_bits_from_csv(csv_nom, vdd)
    data_p80 = extract_bits_from_csv(csv_p80, vdd)
    data_m80 = extract_bits_from_csv(csv_m80, vdd)

    num_cells = len(data_nom["m1_bits"])
    assert (
        num_cells == ARRAY_ROWS * ARRAY_COLS
    ), f"Expected {ARRAY_ROWS * ARRAY_COLS} cells, got {num_cells}"

    # --- STEP 1: Evaluate Mode 1 Stability across both voltage tilts ---
    m1_stable = (data_nom["m1_bits"] == data_p80["m1_bits"]) & (
        data_nom["m1_bits"] == data_m80["m1_bits"]
    )
    m1_unstable = ~m1_stable

    # --- STEP 2: Evaluate Mode 2 Stability for Mode 1 Unstable Cells ---
    m2_stable = (data_nom["m2_bits"] == data_p80["m2_bits"]) & (
        data_nom["m2_bits"] == data_m80["m2_bits"]
    )

    # Map (a): Raw Responses (Mode 1 only)
    map_a = np.where(m1_stable, 0, 1)  # 0=Grey (Stable), 1=Yellow (Unstable)

    # Map (b): Responses after Preselection & Mode-2 Healing
    repaired_mask = m1_unstable & m2_stable
    discarded_mask = m1_unstable & (~m2_stable)

    map_b = np.zeros(num_cells, dtype=int)
    map_b[m1_stable] = 0       # Stable (Grey)
    map_b[repaired_mask] = 2   # Repaired (Green)
    map_b[discarded_mask] = 3  # Discarded (Orange)

    # Map (c): Active Post-Healing Responses
    map_c = np.zeros(num_cells, dtype=int)
    map_c[m1_stable | repaired_mask] = 0  # Active Stable Bits (Grey)
    map_c[discarded_mask] = 4             # Masked / Excluded from key

    grid_a = map_a.reshape(ARRAY_ROWS, ARRAY_COLS)
    grid_b = map_b.reshape(ARRAY_ROWS, ARRAY_COLS)
    grid_c = map_c.reshape(ARRAY_ROWS, ARRAY_COLS)

    # ==========================================================================
    # 4. PRINT QUANTITATIVE SUMMARY & GOLDEN KEY
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

    golden_key_array = np.where(
        m1_stable,
        data_nom["m1_bits"],
        np.where(repaired_mask, data_nom["m2_bits"], -1),
    )
    valid_golden_bits = golden_key_array[golden_key_array != -1]
    golden_bit_str = "".join(str(b) for b in valid_golden_bits)
    golden_hw = int(np.sum(valid_golden_bits))

    print("\n" + "=" * 72)
    print("  32x64 (2048-CELL) SRAM PUF PRESELECTION & SELF-HEALING SUMMARY")
    print("=" * 72)
    print(f"Total Array Cells                 : {num_cells} (32 x 64)")
    print(
        f"Mode 1 Stable Bits (Grey)         : {n_m1_stable:4d} ({n_m1_stable/num_cells*100:.2f}%)"
    )
    print(
        f"Mode 1 Unstable Bits (Yellow)     : {n_m1_unstable:4d} ({raw_ber:.2f}% Raw Instability)"
    )
    print("-" * 72)
    print(
        f"Repaired via Mode 2 (Green)       : {n_repaired:4d} ({healing_rate:.2f}% of unstable bits healed)"
    )
    print(
        f"Discarded Dark Bits (Orange)      : {n_discarded:4d} ({n_discarded/num_cells*100:.2f}% masked out)"
    )
    print("-" * 72)
    print(
        f"Final Active Valid Golden Key Bits: {n_final_valid:4d} / {num_cells} ({valid_yield:.2f}% Valid Bit Yield)"
    )
    print(
        f"Golden Key Hamming Weight         : {golden_hw} / {n_final_valid} ({golden_hw/n_final_valid*100:.2f}% ones)"
    )
    print(
        f"Post-Healing Residual Tilt Errors : 0    (0.00% BER across tilt)"
    )
    print("=" * 72 + "\n")

    with open("golden_key_2048.txt", "w") as f:
        f.write(
            f"Valid Golden Key Length: {n_final_valid} bits (masked bits excluded)\n"
        )
        f.write(
            f"Hamming Weight: {golden_hw}/{n_final_valid} ({golden_hw/n_final_valid*100:.2f}%)\n\n"
        )
        f.write("Binary String:\n" + golden_bit_str + "\n")
    print("Saved valid Golden Key bitstream to 'golden_key_2048.txt'")

    summary_df = pd.DataFrame(
        {
            "Cell_Index (0-2047)": np.arange(num_cells),
            "Row (0-31)": np.arange(num_cells) // ARRAY_COLS,
            "Col (0-63)": np.arange(num_cells) % ARRAY_COLS,
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
            "Golden_Key_Bit": golden_key_array,
        }
    )
    summary_df.to_csv("puf_self_healing_2048_report.csv", index=False)
    print(
        "Saved cell-by-cell classification to 'puf_self_healing_2048_report.csv'"
    )

    # ==========================================================================
    # 5. PLOT FIGURE 10 STYLE 3-PANEL MAPPING (32 x 64)
    # ==========================================================================
    cmap = mcolors.ListedColormap(
        ["#808080", "#FFFF54", "#00E600", "#FF7F00", "#B8B8B8"]
    )
    bounds = [-0.5, 0.5, 1.5, 2.5, 3.5, 4.5]
    norm = mcolors.BoundaryNorm(bounds, cmap.N)

    fig, axes = plt.subplots(1, 3, figsize=(16, 4.2), dpi=300)
    titles = [
        "(a) Raw Responses",
        "(b) After Preselection",
        "(c) After Self-Healing",
    ]
    grids = [grid_a, grid_b, grid_c]

    for ax, grid, title in zip(axes, grids, titles):
        ax.imshow(grid, cmap=cmap, norm=norm, origin="lower", aspect="equal")

        ax.set_xticks(np.arange(-0.5, ARRAY_COLS, 1), minor=True)
        ax.set_yticks(np.arange(-0.5, ARRAY_ROWS, 1), minor=True)
        ax.grid(
            which="minor",
            color="#404040",
            linestyle="-",
            linewidth=0.2,
            alpha=0.5,
        )
        ax.tick_params(which="minor", bottom=False, left=False)

        x_ticks = [7, 15, 23, 31, 39, 47, 55, 63]
        x_labels = ["8", "16", "24", "32", "40", "48", "56", "64"]
        y_ticks = [7, 15, 23, 31]
        y_labels = ["8", "16", "24", "32"]

        ax.set_xticks(x_ticks)
        ax.set_xticklabels(x_labels, fontsize=9, fontweight="bold")
        ax.set_yticks(y_ticks)
        ax.set_yticklabels(y_labels, fontsize=9, fontweight="bold")

        ax.set_xlabel(title, fontsize=12, fontweight="bold", labelpad=8)

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
        "Mapping of Proposed 32×64 SRAM PUF: (a) Raw, (b) Preselection, and (c) Self-Healing",
        fontsize=13,
        fontweight="bold",
        y=0.98,
    )
    plt.subplots_adjust(left=0.04, right=0.86, top=0.86, bottom=0.18, wspace=0.15)

    output_fig = "puf_fig10_mapping_32x64.png"
    plt.savefig(output_fig, dpi=300, bbox_inches="tight")
    print(f"Saved 3-panel visualization to '{os.path.abspath(output_fig)}'")

    if matplotlib.get_backend().lower() != "agg":
        plt.show()
    else:
        print("Headless backend ('Agg') detected; open the saved PNG file to view.")


if __name__ == "__main__":
    run_puf_preselection_analysis(
        CSV_NOMINAL, CSV_PLUS_80, CSV_MINUS_80, vdd=VDD_NOMINAL
    )
