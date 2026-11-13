"""
02_logic_counts_2048.py
=======================
Same as 01 for the 32x64 (2048-cell) array at VDD = 0.9 V, +/-120 mV.
Source: notebooks/VLSI_project_SRAM_PUF.ipynb, cell(s) 17.
Usage: python scripts/02_logic_counts_2048.py --data data/raw
"""

# --- added for the repository: run against the folder holding the raw mc_*.csv files
import argparse as _ap, os as _os
_p = _ap.ArgumentParser(description=__doc__, formatter_class=_ap.RawDescriptionHelpFormatter)
_p.add_argument("--data", default="data/raw", help="folder with the raw Cadence mc_*.csv files (outputs are written there)")
_args, _ = _p.parse_known_args()
_os.chdir(_args.data)

import re
import numpy as np
import pandas as pd


def analyze_sram_puf_csv(csv_path, vdd=0.9, rows=32, cols=64):
    """Analyzes a 32x64 (2048-cell) SRAM BL/BLb Monte Carlo CSV file for Mode 1 and Mode 2 windows.

    Parameters:
    -----------
    csv_path : str
        Path to the CSV file.
    vdd : float
        Supply voltage (default 0.9V). Threshold for logic high/low is set to VDD/2.
    rows : int
        Number of rows in the SRAM array (default 32).
    cols : int
        Number of columns in the SRAM array (default 64).
    """
    expected_cells = rows * cols
    print(f"Loading data from: {csv_path} ...")
    df = pd.read_csv(csv_path, low_memory=False)

    threshold = vdd / 2.0

    # Find all unique mcparamset IDs in the CSV header
    header_cols = df.columns
    paramset_ids = sorted(
        list(set(int(x) for x in re.findall(r"mcparamset=(\d+)", " ".join(header_cols))))
    )
    num_cells = len(paramset_ids)
    print(f"Detected {num_cells} Monte Carlo cells/instances (Target {rows}x{cols} = {expected_cells}).\n")

    if num_cells != expected_cells:
        print(f"Warning: Expected {expected_cells} cells for a {rows}x{cols} array, but found {num_cells}.\n")

    # Time window definitions (in seconds)
    # Mode 2: 37ns to 43ns
    m2_t_min, m2_t_max = 37e-9, 43e-9
    # Mode 1: 97ns to 103ns
    m1_t_min, m1_t_max = 97e-9, 103e-9

    results = []

    for idx, mc_id in enumerate(paramset_ids):
        # Map 1D cell index to 2D array coordinates (32 rows x 64 cols)
        row_idx = idx // cols
        col_idx = idx % cols

        col_bl_x = f"/BL (mcparamset={mc_id}) X"
        col_bl_y = f"/BL (mcparamset={mc_id}) Y"
        col_blb_x = f"/BLb (mcparamset={mc_id}) X"
        col_blb_y = f"/BLb (mcparamset={mc_id}) Y"

        # Read time and voltage arrays, converting to numeric
        t_bl = pd.to_numeric(df[col_bl_x], errors="coerce").values
        v_bl = pd.to_numeric(df[col_bl_y], errors="coerce").values

        t_blb = pd.to_numeric(df[col_blb_x], errors="coerce").values
        v_blb = pd.to_numeric(df[col_blb_y], errors="coerce").values

        # Mode 2 extraction (37ns - 43ns)
        mask_m2_bl = (t_bl >= m2_t_min) & (t_bl <= m2_t_max)
        mask_m2_blb = (t_blb >= m2_t_min) & (t_blb <= m2_t_max)

        v_bl_m2 = np.mean(v_bl[mask_m2_bl]) if np.any(mask_m2_bl) else np.nan
        v_blb_m2 = np.mean(v_blb[mask_m2_blb]) if np.any(mask_m2_blb) else np.nan

        # Mode 1 extraction (97ns - 103ns)
        mask_m1_bl = (t_bl >= m1_t_min) & (t_bl <= m1_t_max)
        mask_m1_blb = (t_blb >= m1_t_min) & (t_blb <= m1_t_max)

        v_bl_m1 = np.mean(v_bl[mask_m1_bl]) if np.any(mask_m1_bl) else np.nan
        v_blb_m1 = np.mean(v_blb[mask_m1_blb]) if np.any(mask_m1_blb) else np.nan

        # Determine Logic Levels (1 if >= threshold else 0)
        bit_bl_m2 = 1 if v_bl_m2 >= threshold else 0
        bit_blb_m2 = 1 if v_blb_m2 >= threshold else 0

        bit_bl_m1 = 1 if v_bl_m1 >= threshold else 0
        bit_blb_m1 = 1 if v_blb_m1 >= threshold else 0

        results.append(
            {
                "mc_id": mc_id,
                "row": row_idx,
                "col": col_idx,
                "BL_M2_V": v_bl_m2,
                "BLb_M2_V": v_blb_m2,
                "BL_M2_bit": bit_bl_m2,
                "BLb_M2_bit": bit_blb_m2,
                "BL_M1_V": v_bl_m1,
                "BLb_M1_V": v_blb_m1,
                "BL_M1_bit": bit_bl_m1,
                "BLb_M1_bit": bit_blb_m1,
            }
        )

    res_df = pd.DataFrame(results)

    # Output Summary Tables
    print("=" * 65)
    print(f" SUMMARY OF LOGIC COUNTS (0s vs 1s) ACROSS ALL {num_cells} CELLS ({rows}x{cols})")
    print("=" * 65)

    print("\n--- MODE 2 (37ns - 43ns) ---")
    m2_bl_1 = (res_df["BL_M2_bit"] == 1).sum()
    m2_bl_0 = (res_df["BL_M2_bit"] == 0).sum()
    m2_blb_1 = (res_df["BLb_M2_bit"] == 1).sum()
    m2_blb_0 = (res_df["BLb_M2_bit"] == 0).sum()

    print(f"BL  -> Logic 1: {m2_bl_1:4d} | Logic 0: {m2_bl_0:4d}")
    print(f"BLb -> Logic 1: {m2_blb_1:4d} | Logic 0: {m2_blb_0:4d}")

    print("\n--- MODE 1 (97ns - 103ns) ---")
    m1_bl_1 = (res_df["BL_M1_bit"] == 1).sum()
    m1_bl_0 = (res_df["BL_M1_bit"] == 0).sum()
    m1_blb_1 = (res_df["BLb_M1_bit"] == 1).sum()
    m1_blb_0 = (res_df["BLb_M1_bit"] == 0).sum()

    print(f"BL  -> Logic 1: {m1_bl_1:4d} | Logic 0: {m1_bl_0:4d}")
    print(f"BLb -> Logic 1: {m1_blb_1:4d} | Logic 0: {m1_blb_0:4d}")

    print("\n" + "=" * 65)

    # Save detailed per-cell results to CSV
    output_filename = f"processed_{num_cells}cells_{rows}x{cols}_summary.csv"
    res_df.to_csv(output_filename, index=False)
    print(f"Detailed per-cell recorded data saved to: '{output_filename}'")

    return res_df


# To run script on your file:
if __name__ == "__main__":
    df_results = analyze_sram_puf_csv("mc_2048_0.9_vdd-120.csv", vdd=0.9, rows=32, cols=64)


if __name__ == "__main__":
    df_results = analyze_sram_puf_csv("mc_2048_0.9_vdd+120.csv", vdd=0.9, rows=32, cols=64)
