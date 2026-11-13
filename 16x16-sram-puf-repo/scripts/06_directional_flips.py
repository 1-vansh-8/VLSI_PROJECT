"""
06_directional_flips.py
=======================
Separate 1->0 and 0->1 flip counts for every (VDD, tilt) file against the golden key, with tilt and VDD sweeps.
Source: notebooks/VLSI_project_SRAM_PUF.ipynb, cell(s) 32.
Usage: python scripts/06_directional_flips.py --data data/raw
"""

# --- added for the repository: run against the folder holding the raw mc_*.csv files
import argparse as _ap, os as _os
_p = _ap.ArgumentParser(description=__doc__, formatter_class=_ap.RawDescriptionHelpFormatter)
_p.add_argument("--data", default="data/raw", help="folder with the raw Cadence mc_*.csv files (outputs are written there)")
_args, _ = _p.parse_known_args()
_os.chdir(_args.data)

import os
import re
import glob
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ==============================================================================
# 1. CONFIGURATION
# ==============================================================================
DATA_DIR = "."              # Folder containing your mc_*.csv files
ARRAY_SIZE = 256            # Set to 256 or 2048 (or None to auto-select largest group)
GOLDEN_VDD = 0.9            # Nominal reference VDD (V) at Tilt = 0 mV

# Choose specific operating points for the two requested sweeps:
SWEEP_VDD = 0.9             # Fixed VDD (V) -> sweep across all available tilts
SWEEP_TILT = 80             # Fixed Tilt (mV, e.g., -120, -80, 0, +80, +120) -> sweep across VDDs

# Reference baseline for counting flips:
#   "golden" -> compare every (VDD, Tilt) against Golden Key at (GOLDEN_VDD, 0mV)
#   "local"  -> compare each (VDD, Tilt) against that same VDD's own 0mV nominal file
BASELINE_MODE = "golden"

# Sense windows (seconds)
MODE2_WINDOW = (37e-9, 43e-9)   # 37 ns - 43 ns
MODE1_WINDOW = (97e-9, 103e-9)  # 97 ns - 103 ns


# ==============================================================================
# 2. WAVEFORM EXTRACTION HELPER
# ==============================================================================
def extract_bits_from_csv(csv_path, vdd):
    """Extracts Mode 1 and Mode 2 binary responses from a Cadence Monte Carlo CSV."""
    df = pd.read_csv(
        csv_path,
        usecols=lambda c: "/BL (" in c or c.strip().startswith("/BL "),
        low_memory=False,
    )
    threshold = vdd / 2.0
    paramset_ids = sorted(
        set(int(x) for x in re.findall(r"mcparamset=(\d+)", " ".join(df.columns)))
    )

    m1_bits = np.zeros(len(paramset_ids), dtype=int)
    m2_bits = np.zeros(len(paramset_ids), dtype=int)

    for idx, mc_id in enumerate(paramset_ids):
        t_bl = pd.to_numeric(df[f"/BL (mcparamset={mc_id}) X"], errors="coerce").values
        v_bl = pd.to_numeric(df[f"/BL (mcparamset={mc_id}) Y"], errors="coerce").values

        mask_m1 = (t_bl >= MODE1_WINDOW[0]) & (t_bl <= MODE1_WINDOW[1])
        mask_m2 = (t_bl >= MODE2_WINDOW[0]) & (t_bl <= MODE2_WINDOW[1])

        v1 = np.nanmean(v_bl[mask_m1]) if np.any(mask_m1) else np.nan
        v2 = np.nanmean(v_bl[mask_m2]) if np.any(mask_m2) else np.nan

        m1_bits[idx] = 1 if v1 >= threshold else 0
        m2_bits[idx] = 1 if v2 >= threshold else 0

    return m1_bits, m2_bits


# ==============================================================================
# 3. LOAD ALL MATCHING CSV FILES
# ==============================================================================
def load_all_datasets(data_dir=".", array_size=256):
    pattern = re.compile(r"mc_(\d+)_+([0-9.]+)_vdd([+-]\d+)?\.csv$", re.IGNORECASE)
    files = sorted(glob.glob(os.path.join(data_dir, "mc_*.csv")))

    parsed = []
    for fpath in files:
        fname = os.path.basename(fpath)
        m = pattern.match(fname)
        if not m:
            continue
        n_cells = int(m.group(1))
        vdd = float(m.group(2))
        tilt = int(m.group(3)) if m.group(3) else 0
        parsed.append((n_cells, vdd, tilt, fpath, fname))

    if not parsed:
        raise FileNotFoundError(f"No matching 'mc_*.csv' files found in '{data_dir}'.")

    if array_size is None:
        # Pick the cell count with the largest number of CSVs
        counts = pd.Series([p[0] for p in parsed]).value_counts()
        array_size = int(counts.index[0])

    dataset = {}
    for n_cells, vdd, tilt, fpath, fname in parsed:
        if n_cells != array_size:
            continue
        m1, m2 = extract_bits_from_csv(fpath, vdd)
        dataset[(vdd, tilt)] = {"M1": m1, "M2": m2, "file": fname}
        print(f"[LOADED] {fname:26s} -> N={len(m1)}, VDD={vdd:.2f}V, Tilt={tilt:+4d}mV")

    return dataset, array_size


# ==============================================================================
# 4. DIRECTIONAL BIT-FLIP ANALYSIS (1->0 AND 0->1 SEPARATELY)
# ==============================================================================
def compute_flip_stats(ref_bits, test_bits):
    """Returns separate 1->0 and 0->1 flip counts and percentages."""
    n_total = len(ref_bits)
    n_ones = int(np.sum(ref_bits == 1))
    n_zeros = int(np.sum(ref_bits == 0))

    flips_1to0 = int(np.sum((ref_bits == 1) & (test_bits == 0)))
    flips_0to1 = int(np.sum((ref_bits == 0) & (test_bits == 1)))
    total_flips = flips_1to0 + flips_0to1

    return {
        "N": n_total,
        "Ref_1s": n_ones,
        "Ref_0s": n_zeros,
        "M1_1to0_Count": flips_1to0,
        "M1_1to0_Pct_Total": round(flips_1to0 / n_total * 100.0, 4),
        "M1_1to0_Pct_Of_1s": round((flips_1to0 / n_ones * 100.0) if n_ones else 0.0, 4),
        "M1_0to1_Count": flips_0to1,
        "M1_0to1_Pct_Total": round(flips_0to1 / n_total * 100.0, 4),
        "M1_0to1_Pct_Of_0s": round((flips_0to1 / n_zeros * 100.0) if n_zeros else 0.0, 4),
        "Total_Flips": total_flips,
        "Total_BER_Pct": round(total_flips / n_total * 100.0, 4),
    }


def analyze_all_and_sweep(
    data_dir=DATA_DIR,
    array_size=ARRAY_SIZE,
    golden_vdd=GOLDEN_VDD,
    sweep_vdd=SWEEP_VDD,
    sweep_tilt=SWEEP_TILT,
    baseline_mode=BASELINE_MODE,
):
    dataset, array_size = load_all_datasets(data_dir, array_size)

    if baseline_mode == "golden" and (golden_vdd, 0) not in dataset:
        raise KeyError(f"Golden baseline (VDD={golden_vdd}V, Tilt=0mV) not found in loaded CSVs.")

    # Compute 1->0 and 0->1 flips for every single loaded (VDD, Tilt) CSV
    rows = []
    for (vdd, tilt) in sorted(dataset.keys(), key=lambda x: (x[0], x[1])):
        ref_key = (golden_vdd, 0) if baseline_mode == "golden" else (vdd, 0)
        if ref_key not in dataset:
            print(f"[WARNING] Missing local 0mV baseline for VDD={vdd}V; skipping {dataset[(vdd, tilt)]['file']}")
            continue

        m1_stats = compute_flip_stats(dataset[ref_key]["M1"], dataset[(vdd, tilt)]["M1"])

        # Also track Mode 2 separate flips
        m2_ref, m2_cur = dataset[ref_key]["M2"], dataset[(vdd, tilt)]["M2"]
        m2_1to0 = int(np.sum((m2_ref == 1) & (m2_cur == 0)))
        m2_0to1 = int(np.sum((m2_ref == 0) & (m2_cur == 1)))

        rows.append({
            "VDD_V": vdd,
            "Tilt_mV": tilt,
            "File": dataset[(vdd, tilt)]["file"],
            **m1_stats,
            "M2_1to0_Count": m2_1to0,
            "M2_0to1_Count": m2_0to1,
            "M2_BER_Pct": round((m2_1to0 + m2_0to1) / len(m2_ref) * 100.0, 4),
        })

    df_all = pd.DataFrame(rows)
    df_all.to_csv("bit_flips_1to0_0to1_all_cases.csv", index=False)

    print("\n" + "=" * 105)
    print(f"ALL CASES: SEPARATE 1->0 AND 0->1 BIT FLIPS (Baseline: {baseline_mode.upper()})")
    print("=" * 105)
    cols_display = [
        "VDD_V", "Tilt_mV",
        "M1_1to0_Count", "M1_1to0_Pct_Total",
        "M1_0to1_Count", "M1_0to1_Pct_Total",
        "Total_Flips", "Total_BER_Pct",
        "M2_1to0_Count", "M2_0to1_Count",
    ]
    print(df_all[cols_display].to_string(index=False))

    # --------------------------------------------------------------------------
    # SWEEP 1: Fixed VDD -> Sweep Across Different Tilts
    # --------------------------------------------------------------------------
    df_tilt_sweep = df_all[np.isclose(df_all["VDD_V"], sweep_vdd)].sort_values("Tilt_mV")
    print("\n" + "=" * 105)
    print(f"SWEEP 1: FIXED VDD = {sweep_vdd:.2f}V | SWEEPING ACROSS TILTS (mV)")
    print("=" * 105)
    if df_tilt_sweep.empty:
        print(f"No CSVs found for VDD = {sweep_vdd}V. Available VDDs: {sorted(df_all['VDD_V'].unique())}")
    else:
        print(df_tilt_sweep[cols_display].to_string(index=False))

    # --------------------------------------------------------------------------
    # SWEEP 2: Fixed Tilt -> Sweep Across Different VDDs
    # --------------------------------------------------------------------------
    df_vdd_sweep = df_all[df_all["Tilt_mV"] == sweep_tilt].sort_values("VDD_V")
    print("\n" + "=" * 105)
    print(f"SWEEP 2: FIXED TILT = {sweep_tilt:+d}mV | SWEEPING ACROSS VDDs (V)")
    print("=" * 105)
    if df_vdd_sweep.empty:
        print(f"No CSVs found for Tilt = {sweep_tilt}mV. Available Tilts: {sorted(df_all['Tilt_mV'].unique())}")
    else:
        print(df_vdd_sweep[cols_display].to_string(index=False))

    # --------------------------------------------------------------------------
    # PLOT BOTH SWEEPS SIDE-BY-SIDE
    # --------------------------------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(14, 5), dpi=150)
    width = 0.36

    # Left subplot: Fixed VDD, Sweep across Tilts
    if not df_tilt_sweep.empty:
        x1 = np.arange(len(df_tilt_sweep))
        b1 = axes[0].bar(x1 - width / 2, df_tilt_sweep["M1_1to0_Count"], width, label="1 → 0 Flips", color="#e67e22", edgecolor="black")
        b2 = axes[0].bar(x1 + width / 2, df_tilt_sweep["M1_0to1_Count"], width, label="0 → 1 Flips", color="#2ecc71", edgecolor="black")
        axes[0].bar_label(b1, padding=2, fontsize=8)
        axes[0].bar_label(b2, padding=2, fontsize=8)
        axes[0].set_xticks(x1)
        axes[0].set_xticklabels([f"{int(t):+d} mV" for t in df_tilt_sweep["Tilt_mV"]], fontsize=9)
        axes[0].set_title(f"Tilt Sweep at Fixed VDD = {sweep_vdd:.2f}V", fontsize=11.5, fontweight="bold")
        axes[0].set_xlabel("Voltage Tilt (mV)", fontsize=10.5)
        axes[0].set_ylabel(f"Flipped Bit Count (out of {array_size})", fontsize=10.5)
        axes[0].grid(True, axis="y", linestyle="--", alpha=0.5)
        axes[0].legend()

    # Right subplot: Fixed Tilt, Sweep across VDDs
    if not df_vdd_sweep.empty:
        x2 = np.arange(len(df_vdd_sweep))
        b3 = axes[1].bar(x2 - width / 2, df_vdd_sweep["M1_1to0_Count"], width, label="1 → 0 Flips", color="#e67e22", edgecolor="black")
        b4 = axes[1].bar(x2 + width / 2, df_vdd_sweep["M1_0to1_Count"], width, label="0 → 1 Flips", color="#2ecc71", edgecolor="black")
        axes[1].bar_label(b3, padding=2, fontsize=8)
        axes[1].bar_label(b4, padding=2, fontsize=8)
        axes[1].set_xticks(x2)
        axes[1].set_xticklabels([f"{v:.2f} V" for v in df_vdd_sweep["VDD_V"]], fontsize=9)
        axes[1].set_title(f"VDD Sweep at Fixed Tilt = {sweep_tilt:+d}mV", fontsize=11.5, fontweight="bold")
        axes[1].set_xlabel("Supply Voltage VDD (V)", fontsize=10.5)
        axes[1].set_ylabel(f"Flipped Bit Count (out of {array_size})", fontsize=10.5)
        axes[1].grid(True, axis="y", linestyle="--", alpha=0.5)
        axes[1].legend()

    plt.suptitle(f"Directional Bit Flips (1→0 vs. 0→1) | Baseline: {baseline_mode.upper()}", fontsize=13, fontweight="bold")
    plt.tight_layout()
    plt.savefig("directional_bit_flips_sweeps.png", dpi=150, bbox_inches="tight")
    plt.show()

    return df_all, df_tilt_sweep, df_vdd_sweep


if __name__ == "__main__":
    df_all, df_tilt_sweep, df_vdd_sweep = analyze_all_and_sweep()
