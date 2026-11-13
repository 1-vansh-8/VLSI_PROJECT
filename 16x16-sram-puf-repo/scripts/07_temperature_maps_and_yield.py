"""
07_temperature_maps_and_yield.py
================================
16x16 maps and stable/repaired/discarded breakdown at -100, -40, 0, 27 and 75 C (VDD = 0.9 V, +/-120 mV classification).
Source: notebooks/VLSI_project_SRAM_PUF.ipynb, cell(s) 33.
Usage: python scripts/07_temperature_maps_and_yield.py --data data/raw
"""

# --- added for the repository: run against the folder holding the raw mc_*.csv files
import argparse as _ap, os as _os
_p = _ap.ArgumentParser(description=__doc__, formatter_class=_ap.RawDescriptionHelpFormatter)
_p.add_argument("--data", default="data/raw", help="folder with the raw Cadence mc_*.csv files (outputs are written there)")
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
# 1. CONFIGURATION: EXPLICIT CSV FILE NAMES (16 x 16 = 256 CELLS AT ALL TEMPS)
# ==============================================================================
VDD_NOMINAL = 0.9
ARRAY_ROWS = 16                 # 16 rows x 16 cols = 256 cells for all temperatures
ARRAY_COLS = 16

MODE2_WINDOW = (37e-9, 43e-9)   # Mode 2 active window: 37ns - 43ns
MODE1_WINDOW = (97e-9, 103e-9)  # Mode 1 active window: 97ns - 103ns

# Tilt corners used to define preselection stability & bit classification
EVAL_TILTS = ["+120mV", "-120mV"]

TEMPERATURE_FILES = {
    -100: {
        "Nominal": "mc_-100_256_0.9_vdd.csv",
        "+50mV":   "mc_-100_256_0.9_vdd+50.csv",
        "+80mV":   "mc_-100_256_0.9_vdd+80.csv",
        "+120mV":  "mc_-100_256_0.9_vdd+120.csv",
        "-50mV":   "mc_-100_256_0.9_vdd-50.csv",
        "-80mV":   "mc_-100_256_0.9_vdd-80.csv",
        "-120mV":  "mc_-100_256_0.9_vdd-120.csv",
    },
    -40: {
        "Nominal": "mc_-40_256_0.9_vdd.csv",
        "+50mV":   "mc_-40_256_0.9_vdd+50.csv",
        "+80mV":   "mc_-40_256_0.9_vdd+80.csv",
        "+120mV":  "mc_-40_256_0.9_vdd+120.csv",
        "-50mV":   "mc_-40_256_0.9_vdd-50.csv",
        "-80mV":   "mc_-40_256_0.9_vdd-80.csv",
        "-120mV":  "mc_-40_256_0.9_vdd-120.csv",
    },
    0: {
        "Nominal": "mc_0_256_0.9_vdd.csv",
        "+50mV":   "mc_0_256_0.9_vdd+50.csv",
        "+80mV":   "mc_0_256_0.9_vdd+80.csv",
        "+120mV":  "mc_0_256_0.9_vdd+120.csv",
        "-50mV":   "mc_0_256_0.9_vdd-50.csv",
        "-80mV":   "mc_0_256_0.9_vdd-80.csv",
        "-120mV":  "mc_0_256_0.9_vdd-120.csv",
    },
    27: {
        # Room temperature (27°C) 256-cell CSVs without temperature in filename
        "Nominal": "mc_256_0.9_vdd.csv",
        "+50mV":   "mc_256_0.9_vdd+50.csv",
        "+80mV":   "mc_256_0.9_vdd+80.csv",
        "+120mV":  "mc_256_0.9_vdd+120.csv",
        "-50mV":   "mc_256_0.9_vdd-50.csv",
        "-80mV":   "mc_256_0.9_vdd-80.csv",
        "-120mV":  "mc_256_0.9_vdd-120.csv",
    },
    75: {
        # 75°C uses uppercase 'VDD' in file naming
        "Nominal": "mc_75_256_0.9_VDD.csv",
        "+50mV":   "mc_75_256_0.9_VDD+50.csv",
        "+80mV":   "mc_75_256_0.9_VDD+80.csv",
        "+120mV":  "mc_75_256_0.9_VDD+120.csv",
        "-50mV":   "mc_75_256_0.9_VDD-50.csv",
        "-80mV":   "mc_75_256_0.9_VDD-80.csv",
        "-120mV":  "mc_75_256_0.9_VDD-120.csv",
    },
}


# ==============================================================================
# 2. HELPER FUNCTIONS
# ==============================================================================
def extract_bits_from_csv(csv_path, target_temp=None, vdd=0.9):
    """Reads /BL (or complementary /BLb if /BL was omitted in Cadence export)
    and filters by target_temp if multiple temperature sweeps exist in one CSV.
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Could not find CSV file: {csv_path}")

    all_cols = pd.read_csv(csv_path, nrows=0).columns.tolist()
    threshold = vdd / 2.0

    bl_cols = [c for c in all_cols if re.search(r"(?:^|/)BL\s*\(", c.strip())]
    blb_cols = [c for c in all_cols if re.search(r"(?:^|/)BLb\s*\(", c.strip())]

    use_inverted_blb = False
    candidate_cols = bl_cols
    if not candidate_cols and blb_cols:
        candidate_cols = blb_cols
        use_inverted_blb = True

    if not candidate_cols:
        raise ValueError(f"No '/BL' or '/BLb' columns found in {csv_path}.")

    # Filter to target_temp if multiple temperature=... tags exist in the same file
    temps_in_cols = set(
        re.findall(r"temperature=([^,)]+)", " ".join(candidate_cols))
    )
    if len(temps_in_cols) > 1 and target_temp is not None:
        t_str = str(target_temp)
        filtered = [
            c
            for c in candidate_cols
            if f"temperature={t_str}," in c or f"temperature={t_str})" in c
        ]
        if filtered:
            candidate_cols = filtered

    df = pd.read_csv(csv_path, usecols=candidate_cols, low_memory=False)

    col_map = {}
    for c in df.columns:
        c_clean = c.strip()
        m_id = re.search(r"mcparamset=(\d+)", c_clean)
        if not m_id:
            continue
        mc_id = int(m_id.group(1))
        if c_clean.endswith(" X"):
            col_map.setdefault(mc_id, {})["X"] = c
        elif c_clean.endswith(" Y"):
            col_map.setdefault(mc_id, {})["Y"] = c

    paramset_ids = sorted(col_map.keys())
    m1_bits = np.zeros(len(paramset_ids), dtype=int)
    m2_bits = np.zeros(len(paramset_ids), dtype=int)

    for idx, mc_id in enumerate(paramset_ids):
        t_bl = pd.to_numeric(df[col_map[mc_id]["X"]], errors="coerce").values
        v_bl = pd.to_numeric(df[col_map[mc_id]["Y"]], errors="coerce").values

        v1 = np.nanmean(v_bl[(t_bl >= MODE1_WINDOW[0]) & (t_bl <= MODE1_WINDOW[1])])
        v2 = np.nanmean(v_bl[(t_bl >= MODE2_WINDOW[0]) & (t_bl <= MODE2_WINDOW[1])])

        if use_inverted_blb:
            m1_bits[idx] = 1 if v1 < threshold else 0
            m2_bits[idx] = 1 if v2 < threshold else 0
        else:
            m1_bits[idx] = 1 if v1 >= threshold else 0
            m2_bits[idx] = 1 if v2 >= threshold else 0

    return {"m1_bits": m1_bits, "m2_bits": m2_bits}


def plot_3panel_16x16_map(grid_a, grid_b, grid_c, temp_c):
    """Generates the 3-panel 16x16 spatial bit mapping for a given temperature."""
    cmap = mcolors.ListedColormap(
        ["#808080", "#FFFF54", "#00E600", "#FF7F00", "#B8B8B8"]
    )
    bounds = [-0.5, 0.5, 1.5, 2.5, 3.5, 4.5]
    norm = mcolors.BoundaryNorm(bounds, cmap.N)

    fig, axes = plt.subplots(1, 3, figsize=(12.5, 4.2), dpi=300)
    titles = [
        "(a) Raw Responses",
        "(b) After Preselection",
        "(c) After Self-Healing",
    ]
    grids = [grid_a, grid_b, grid_c]

    ticks = [3, 7, 11, 15]
    labels = ["4", "8", "12", "16"]

    for ax, grid, title in zip(axes, grids, titles):
        ax.imshow(grid, cmap=cmap, norm=norm, origin="lower", aspect="equal")

        ax.set_xticks(np.arange(-0.5, ARRAY_COLS, 1), minor=True)
        ax.set_yticks(np.arange(-0.5, ARRAY_ROWS, 1), minor=True)
        ax.grid(
            which="minor",
            color="#404040",
            linestyle="-",
            linewidth=0.35,
            alpha=0.55,
        )
        ax.tick_params(which="minor", bottom=False, left=False)

        ax.set_xticks(ticks)
        ax.set_xticklabels(labels, fontsize=9, fontweight="bold")
        ax.set_yticks(ticks)
        ax.set_yticklabels(labels, fontsize=9, fontweight="bold")
        ax.set_xlabel(title, fontsize=11, fontweight="bold", labelpad=8)

    legend_patches = [
        mpatches.Patch(facecolor="#FFFF54", edgecolor="black", label="Unstable Bits"),
        mpatches.Patch(facecolor="#00E600", edgecolor="black", label="Repaired Bits"),
        mpatches.Patch(facecolor="#FF7F00", edgecolor="black", label="Discarded Bits"),
        mpatches.Patch(facecolor="#808080", edgecolor="black", label="Stable Bits"),
    ]
    fig.legend(
        handles=legend_patches,
        loc="center left",
        bbox_to_anchor=(0.88, 0.52),
        frameon=False,
        fontsize=10,
        prop={"weight": "bold"},
    )

    plt.suptitle(
        f"Mapping of Proposed 16×16 SRAM PUF at {temp_c}°C: (a) Raw, (b) Preselection, and (c) Self-Healing",
        fontsize=12.5,
        fontweight="bold",
        y=0.98,
    )
    plt.subplots_adjust(left=0.05, right=0.86, top=0.85, bottom=0.18, wspace=0.18)

    out_png = f"puf_16x16_mapping_{temp_c}C.png"
    plt.savefig(out_png, dpi=300, bbox_inches="tight")
    print(f"Saved spatial map -> '{out_png}'")
    plt.show()


# ==============================================================================
# 3. MAIN EXECUTION: ANALYZE 16x16 BIT DISTRIBUTIONS ACROSS ALL 5 TEMPERATURES
# ==============================================================================
def run_multitemp_bit_distribution():
    summary_rows = []
    expected_cells = ARRAY_ROWS * ARRAY_COLS

    for temp_c, file_dict in TEMPERATURE_FILES.items():
        print(f"\nProcessing Temperature = {temp_c}°C ...")
        data_nom = extract_bits_from_csv(
            file_dict["Nominal"], target_temp=temp_c, vdd=VDD_NOMINAL
        )
        num_cells = len(data_nom["m1_bits"])
        assert (
            num_cells == expected_cells
        ), f"Expected {expected_cells} cells at {temp_c}°C, got {num_cells}"

        m1_stable = np.ones(num_cells, dtype=bool)
        m2_stable = np.ones(num_cells, dtype=bool)
        used_tilts = []

        for tilt_label in EVAL_TILTS:
            tilt_path = file_dict[tilt_label]
            if not os.path.exists(tilt_path):
                print(f"  [Note] Tilt file not found (skipped): {tilt_path}")
                continue
            data_tilt = extract_bits_from_csv(
                tilt_path, target_temp=temp_c, vdd=VDD_NOMINAL
            )
            m1_stable &= data_nom["m1_bits"] == data_tilt["m1_bits"]
            m2_stable &= data_nom["m2_bits"] == data_tilt["m2_bits"]
            used_tilts.append(tilt_label)

        if not used_tilts:
            raise FileNotFoundError(f"No tilt CSV files found for {temp_c}°C.")

        m1_unstable = ~m1_stable
        repaired_mask = m1_unstable & m2_stable
        discarded_mask = m1_unstable & (~m2_stable)

        map_a = np.where(m1_stable, 0, 1)

        map_b = np.zeros(num_cells, dtype=int)
        map_b[m1_stable] = 0
        map_b[repaired_mask] = 2
        map_b[discarded_mask] = 3

        map_c = np.zeros(num_cells, dtype=int)
        map_c[m1_stable | repaired_mask] = 0
        map_c[discarded_mask] = 4

        grid_a = map_a.reshape(ARRAY_ROWS, ARRAY_COLS)
        grid_b = map_b.reshape(ARRAY_ROWS, ARRAY_COLS)
        grid_c = map_c.reshape(ARRAY_ROWS, ARRAY_COLS)

        n_m1_stable = int(np.sum(m1_stable))
        n_m1_unstable = int(np.sum(m1_unstable))
        n_repaired = int(np.sum(repaired_mask))
        n_discarded = int(np.sum(discarded_mask))
        n_final_valid = n_m1_stable + n_repaired

        raw_instab_pct = (n_m1_unstable / num_cells) * 100.0
        healing_rate_pct = (
            (n_repaired / n_m1_unstable * 100.0) if n_m1_unstable > 0 else 100.0
        )
        valid_yield_pct = (n_final_valid / num_cells) * 100.0

        golden_key_array = np.where(
            m1_stable,
            data_nom["m1_bits"],
            np.where(repaired_mask, data_nom["m2_bits"], -1),
        )
        valid_golden_bits = golden_key_array[golden_key_array != -1]
        golden_hw = int(np.sum(valid_golden_bits))

        print("=" * 74)
        print(f"  16x16 (256-CELL) SRAM PUF BIT DISTRIBUTION @ {temp_c}°C (Tilts: {', '.join(used_tilts)})")
        print("=" * 74)
        print(f"Mode 1 Stable Bits (Grey)         : {n_m1_stable:3d} / {num_cells} ({n_m1_stable/num_cells*100:.2f}%)")
        print(f"Mode 1 Unstable Bits (Yellow)     : {n_m1_unstable:3d} / {num_cells} ({raw_instab_pct:.2f}% Unstable before preselection)")
        print("-" * 74)
        print(f"Repaired via Mode 2 (Green)       : {n_repaired:3d} ({healing_rate_pct:.2f}% of unstable bits healed)")
        print(f"Discarded Dark Bits (Orange)      : {n_discarded:3d} ({n_discarded/num_cells*100:.2f}% masked out)")
        print("-" * 74)
        print(f"Final Active Valid Golden Key Bits: {n_final_valid:3d} / {num_cells} ({valid_yield_pct:.2f}% Valid Bit Yield)")
        print(f"Golden Key Hamming Weight         : {golden_hw:3d} / {n_final_valid} ({golden_hw/n_final_valid*100:.2f}% ones)")
        print("=" * 74)

        plot_3panel_16x16_map(grid_a, grid_b, grid_c, temp_c)

        summary_rows.append(
            {
                "Temp_C": temp_c,
                "Total_Cells": num_cells,
                "M1_Stable_Count": n_m1_stable,
                "M1_Unstable_Count": n_m1_unstable,
                "Repaired_Count": n_repaired,
                "Discarded_Count": n_discarded,
                "Valid_Bits_Count": n_final_valid,
                "M1_Stable_Pct": n_m1_stable / num_cells * 100.0,
                "M1_Unstable_Pct": raw_instab_pct,
                "Repaired_Pct_of_Total": n_repaired / num_cells * 100.0,
                "Healing_Efficiency_Pct": healing_rate_pct,
                "Discarded_Pct": n_discarded / num_cells * 100.0,
                "Valid_Yield_Pct": valid_yield_pct,
                "Golden_HW_Pct": golden_hw / n_final_valid * 100.0,
            }
        )

    dist_df = pd.DataFrame(summary_rows)
    dist_df.to_csv("puf_16x16_bit_distribution_all_temps.csv", index=False)
    print("\nSaved cross-temperature bit distribution table -> 'puf_16x16_bit_distribution_all_temps.csv'")

    fig, ax = plt.subplots(figsize=(9.5, 5.2), dpi=300)
    x = np.arange(len(dist_df))
    temp_labels = [f"{t}°C" for t in dist_df["Temp_C"]]

    ax.bar(x, dist_df["M1_Stable_Pct"], width=0.55, color="#808080", edgecolor="black", label="Stable Bits (Mode 1)")
    ax.bar(x, dist_df["Repaired_Pct_of_Total"], width=0.55, bottom=dist_df["M1_Stable_Pct"], color="#00E600", edgecolor="black", label="Repaired Bits (Mode 2)")
    ax.bar(x, dist_df["Discarded_Pct"], width=0.55, bottom=dist_df["M1_Stable_Pct"] + dist_df["Repaired_Pct_of_Total"], color="#FF7F00", edgecolor="black", label="Discarded Dark Bits")

    for i, row in dist_df.iterrows():
        ax.text(
            i,
            row["Valid_Yield_Pct"] + 0.8,
            f"Yield: {row['Valid_Yield_Pct']:.1f}%\n({int(row['Valid_Bits_Count'])}/256)",
            ha="center",
            va="bottom",
            fontsize=8.5,
            fontweight="bold",
        )

    ax.set_xticks(x)
    ax.set_xticklabels(temp_labels, fontsize=11, fontweight="bold")
    ax.set_ylabel("Percentage of 16×16 Array (%)", fontsize=11, fontweight="bold")
    ax.set_xlabel("Operating Temperature (°C)", fontsize=11, fontweight="bold")
    ax.set_ylim(0, 115)
    ax.set_title("16×16 SRAM PUF Bit Classification Breakdown Across Temperature (-100°C to 75°C)", fontsize=12, fontweight="bold")
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.legend(loc="lower right", frameon=True, fontsize=9.5)

    plt.tight_layout()
    plt.savefig("puf_16x16_bit_distribution_vs_temp.png", dpi=300, bbox_inches="tight")
    print("Saved cross-temperature distribution chart -> 'puf_16x16_bit_distribution_vs_temp.png'")
    plt.show()


if __name__ == "__main__":
    run_multitemp_bit_distribution()
