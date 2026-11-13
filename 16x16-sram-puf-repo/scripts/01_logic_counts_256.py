"""
01_logic_counts_256.py
======================
Counts logic 0/1 on BL and BLb in both mode windows for 256-cell Monte Carlo CSVs.
Source: notebooks/VLSI_project_SRAM_PUF.ipynb, cell(s) 1.
Usage: python scripts/01_logic_counts_256.py --data data/raw
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


def analyze_sram_puf_csv(csv_path, vdd=0.9):
    """Analyzes 256-cell SRAM BL/BLb Monte Carlo CSV file for Mode 1 and Mode 2 evaluation windows.

    Parameters:
    -----------
    csv_path : str
        Path to the CSV file.
    vdd : float
        Supply voltage (default 0.9V). Threshold for logic high/low is set to VDD/2.
    """
    print(f"Loading data from: {csv_path} ...")
    df = pd.read_csv(csv_path, low_memory=False)

    threshold = vdd / 2.0

    # Find all unique mcparamset IDs in the CSV header
    cols = df.columns
    paramset_ids = sorted(
        list(set(int(x) for x in re.findall(r"mcparamset=(\d+)", " ".join(cols))))
    )
    num_cells = len(paramset_ids)
    print(f"Detected {num_cells} Monte Carlo cells/instances.\n")

    # Time window definitions (in seconds)
    # Mode 2: 37ns to 43ns
    m2_t_min, m2_t_max = 37e-9, 43e-9
    # Mode 1: 97ns to 103ns
    m1_t_min, m1_t_max = 97e-9, 103e-9

    results = []

    for mc_id in paramset_ids:
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
        v_blb_m2 = (
            np.mean(v_blb[mask_m2_blb]) if np.any(mask_m2_blb) else np.nan
        )

        # Mode 1 extraction (97ns - 103ns)
        mask_m1_bl = (t_bl >= m1_t_min) & (t_bl <= m1_t_max)
        mask_m1_blb = (t_blb >= m1_t_min) & (t_blb <= m1_t_max)

        v_bl_m1 = np.mean(v_bl[mask_m1_bl]) if np.any(mask_m1_bl) else np.nan
        v_blb_m1 = (
            np.mean(v_blb[mask_m1_blb]) if np.any(mask_m1_blb) else np.nan
        )

        # Determine Logic Levels (1 if > threshold else 0)
        bit_bl_m2 = 1 if v_bl_m2 >= threshold else 0
        bit_blb_m2 = 1 if v_blb_m2 >= threshold else 0

        bit_bl_m1 = 1 if v_bl_m1 >= threshold else 0
        bit_blb_m1 = 1 if v_blb_m1 >= threshold else 0

        results.append(
            {
                "mc_id": mc_id,
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
    print(" SUMMARY OF LOGIC COUNTS (0s vs 1s) ACROSS ALL 256 CELLS")
    print("=" * 65)

    print("\n--- MODE 2 (37ns - 43ns) ---")
    m2_bl_1 = (res_df["BL_M2_bit"] == 1).sum()
    m2_bl_0 = (res_df["BL_M2_bit"] == 0).sum()
    m2_blb_1 = (res_df["BLb_M2_bit"] == 1).sum()
    m2_blb_0 = (res_df["BLb_M2_bit"] == 0).sum()

    print(f"BL  -> Logic 1: {m2_bl_1:3d} | Logic 0: {m2_bl_0:3d}")
    print(f"BLb -> Logic 1: {m2_blb_1:3d} | Logic 0: {m2_blb_0:3d}")

    print("\n--- MODE 1 (97ns - 103ns) ---")
    m1_bl_1 = (res_df["BL_M1_bit"] == 1).sum()
    m1_bl_0 = (res_df["BL_M1_bit"] == 0).sum()
    m1_blb_1 = (res_df["BLb_M1_bit"] == 1).sum()
    m1_blb_0 = (res_df["BLb_M1_bit"] == 0).sum()

    print(f"BL  -> Logic 1: {m1_bl_1:3d} | Logic 0: {m1_bl_0:3d}")
    print(f"BLb -> Logic 1: {m1_blb_1:3d} | Logic 0: {m1_blb_0:3d}")

    print("\n" + "=" * 65)

    # Save detailed per-cell results to CSV
    output_filename = "processed_256cells_summary.csv"
    res_df.to_csv(output_filename, index=False)
    print(f"Detailed per-cell recorded data saved to: '{output_filename}'")

    return res_df

if __name__ == "__main__":
    # Files analysed in notebook cells 4-15 (threshold VDD/2 = 0.45 V, as in the notebook).
    for f in ['mc_256_0.9_vdd-80.csv', 'mc_256_0.9_vdd+80.csv', 'mc_256_0.9_vdd+50.csv', 'mc_256_0.9_vdd-50.csv', 'mc_256_1.0_vdd.csv', 'mc_256_1.0_vdd-80.csv', 'mc_256_1.0_vdd+80.csv']:
        analyze_sram_puf_csv(f, vdd=0.9)

