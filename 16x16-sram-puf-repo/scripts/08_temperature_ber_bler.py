"""
08_temperature_ber_bler.py
==========================
BER, 128-/256-bit BLER and per-tilt BER against temperature; nominal drift against 27 C.
Source: notebooks/VLSI_project_SRAM_PUF.ipynb, cell(s) 34.
Usage: python scripts/08_temperature_ber_bler.py --data data/raw
"""

# --- added for the repository: run against the folder holding the raw mc_*.csv files
import argparse as _ap, os as _os
_p = _ap.ArgumentParser(description=__doc__, formatter_class=_ap.RawDescriptionHelpFormatter)
_p.add_argument("--data", default="data/raw", help="folder with the raw Cadence mc_*.csv files (outputs are written there)")
_args, _ = _p.parse_known_args()
_os.chdir(_args.data)

import os
import re
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ==============================================================================
# 1. CONFIGURATION: EXPLICIT CSV FILE NAMES (16 x 16 = 256 CELLS AT ALL TEMPS)
# ==============================================================================
VDD_NOMINAL = 0.9
MODE2_WINDOW = (37e-9, 43e-9)   # Mode 2 active window: 37ns - 43ns
MODE1_WINDOW = (97e-9, 103e-9)  # Mode 1 active window: 97ns - 103ns

TILT_ORDER = ["+50mV", "-50mV", "+80mV", "-80mV", "+120mV", "-120mV"]

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
def extract_bits(csv_path, target_temp=None, vdd=0.9):
    """Reads /BL (or complementary /BLb if /BL was omitted in Cadence export)
    and filters by target_temp if multiple temperature sweeps exist in one CSV.
    """
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

    return m1_bits, m2_bits


def ber_to_bler_pct(ber_pct, block_size):
    """Converts BER (%) to N-bit Block Error Rate BLER (%): 1 - (1 - BER)^N."""
    p_err = np.clip(ber_pct / 100.0, 0.0, 1.0)
    return (1.0 - (1.0 - p_err) ** block_size) * 100.0


# ==============================================================================
# 3. MAIN BER & BLER ANALYSIS + TEMPERATURE PLOTS
# ==============================================================================
def run_ber_bler_vs_temperature():
    overall_records = []
    per_tilt_records = []
    nom_responses = {}

    for temp_c, file_dict in TEMPERATURE_FILES.items():
        nom_path = file_dict["Nominal"]
        if not os.path.exists(nom_path):
            raise FileNotFoundError(f"Nominal file missing for {temp_c}°C: {nom_path}")
        nom_responses[temp_c] = extract_bits(
            nom_path, target_temp=temp_c, vdd=VDD_NOMINAL
        )

    m1_ref_27, m2_ref_27 = nom_responses[27]

    for temp_c, file_dict in TEMPERATURE_FILES.items():
        m1_nom, m2_nom = nom_responses[temp_c]
        n_cells = len(m1_nom)

        temp_drift_m1_ber = np.sum(m1_nom != m1_ref_27) / n_cells * 100.0
        temp_drift_m2_ber = np.sum(m2_nom != m2_ref_27) / n_cells * 100.0

        available_tilts = {}
        for tilt in TILT_ORDER:
            path = file_dict[tilt]
            if os.path.exists(path):
                available_tilts[tilt] = extract_bits(
                    path, target_temp=temp_c, vdd=VDD_NOMINAL
                )
            else:
                print(f"  [Note] Optional tilt file not found (skipped): {path}")

        m1_stable = np.ones(n_cells, dtype=bool)
        m2_stable = np.ones(n_cells, dtype=bool)
        for tilt, (m1_t, m2_t) in available_tilts.items():
            m1_stable &= m1_nom == m1_t
            m2_stable &= m2_nom == m2_t

        m1_unstable = ~m1_stable
        repaired_mask = m1_unstable & m2_stable
        valid_mask = m1_stable | repaired_mask
        n_valid = int(np.sum(valid_mask))

        healed_nom = np.where(m1_stable, m1_nom, m2_nom)

        m1_bers = []
        m2_bers = []
        healed_bers = []
        post_presel_bers = []

        print("\n" + "=" * 82)
        print(
            f"  TEMPERATURE = {temp_c}°C  (16×16 = {n_cells} Cells | {n_valid} Valid Bits | "
            f"Nom Drift vs 27°C: {temp_drift_m1_ber:.2f}%)"
        )
        print("=" * 82)
        print(f"{'Tilt Corner':<12} | {'Raw M1 BER':>11} | {'Raw M2 BER':>11} | {'Healed BER':>11} | {'Final BER':>10}")
        print("-" * 82)

        for tilt in TILT_ORDER:
            if tilt not in available_tilts:
                per_tilt_records.append(
                    {
                        "Temp_C": temp_c,
                        "Tilt": tilt,
                        "Raw_M1_BER_Pct": np.nan,
                        "Raw_M2_BER_Pct": np.nan,
                        "Healed_Unmasked_BER_Pct": np.nan,
                        "Final_Valid_BER_Pct": np.nan,
                    }
                )
                continue

            m1_t, m2_t = available_tilts[tilt]
            healed_t = np.where(m1_stable, m1_t, m2_t)

            ber_m1 = np.sum(m1_nom != m1_t) / n_cells * 100.0
            ber_m2 = np.sum(m2_nom != m2_t) / n_cells * 100.0
            ber_heal = np.sum(healed_nom != healed_t) / n_cells * 100.0
            ber_final = (
                np.sum(healed_nom[valid_mask] != healed_t[valid_mask]) / n_valid * 100.0
                if n_valid > 0
                else 0.0
            )

            m1_bers.append(ber_m1)
            m2_bers.append(ber_m2)
            healed_bers.append(ber_heal)
            post_presel_bers.append(ber_final)

            print(
                f"{tilt:<12} | {ber_m1:10.2f}% | {ber_m2:10.2f}% | {ber_heal:10.2f}% | {ber_final:9.2f}%"
            )

            per_tilt_records.append(
                {
                    "Temp_C": temp_c,
                    "Tilt": tilt,
                    "Raw_M1_BER_Pct": ber_m1,
                    "Raw_M2_BER_Pct": ber_m2,
                    "Healed_Unmasked_BER_Pct": ber_heal,
                    "Final_Valid_BER_Pct": ber_final,
                }
            )

        mean_m1_ber = float(np.mean(m1_bers))
        mean_m2_ber = float(np.mean(m2_bers))
        mean_heal_ber = float(np.mean(healed_bers))
        mean_final_ber = float(np.mean(post_presel_bers))

        print("-" * 82)
        print(
            f"{'MEAN (Tilts)':<12} | {mean_m1_ber:10.2f}% | {mean_m2_ber:10.2f}% | {mean_heal_ber:10.2f}% | {mean_final_ber:9.2f}%"
        )
        print(
            f"{'128b BLER':<12} | {ber_to_bler_pct(mean_m1_ber, 128):10.2f}% | "
            f"{ber_to_bler_pct(mean_m2_ber, 128):10.2f}% | "
            f"{ber_to_bler_pct(mean_heal_ber, 128):10.2f}% | "
            f"{ber_to_bler_pct(mean_final_ber, 128):9.2f}%"
        )
        print(
            f"{'256b BLER':<12} | {ber_to_bler_pct(mean_m1_ber, 256):10.2f}% | "
            f"{ber_to_bler_pct(mean_m2_ber, 256):10.2f}% | "
            f"{ber_to_bler_pct(mean_heal_ber, 256):10.2f}% | "
            f"{ber_to_bler_pct(mean_final_ber, 256):9.2f}%"
        )
        print("=" * 82)

        overall_records.append(
            {
                "Temp_C": temp_c,
                "Total_Cells": n_cells,
                "Valid_Cells": n_valid,
                "Temp_Drift_vs_27C_M1_BER_Pct": temp_drift_m1_ber,
                "Temp_Drift_vs_27C_M2_BER_Pct": temp_drift_m2_ber,
                "Mean_Raw_M1_BER_Pct": mean_m1_ber,
                "Mean_Raw_M2_BER_Pct": mean_m2_ber,
                "Mean_Healed_Unmasked_BER_Pct": mean_heal_ber,
                "Mean_Final_Valid_BER_Pct": mean_final_ber,
                "Raw_M1_BLER_128b_Pct": ber_to_bler_pct(mean_m1_ber, 128),
                "Healed_BLER_128b_Pct": ber_to_bler_pct(mean_heal_ber, 128),
                "Final_BLER_128b_Pct": ber_to_bler_pct(mean_final_ber, 128),
                "Raw_M1_BLER_256b_Pct": ber_to_bler_pct(mean_m1_ber, 256),
                "Healed_BLER_256b_Pct": ber_to_bler_pct(mean_heal_ber, 256),
                "Final_BLER_256b_Pct": ber_to_bler_pct(mean_final_ber, 256),
            }
        )

    df_overall = pd.DataFrame(overall_records)
    df_tilts = pd.DataFrame(per_tilt_records)

    df_overall.to_csv("puf_16x16_ber_bler_vs_temperature.csv", index=False)
    df_tilts.to_csv("puf_16x16_ber_per_tilt_vs_temperature.csv", index=False)
    print("\nSaved summary CSVs -> 'puf_16x16_ber_bler_vs_temperature.csv' & 'puf_16x16_ber_per_tilt_vs_temperature.csv'")

    # ==========================================================================
    # 4. PLOT 1: MEAN BER & 128-BIT BLER VARIATION WITH TEMPERATURE
    # ==========================================================================
    temps = df_overall["Temp_C"].values

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14.5, 5.2), dpi=300)

    ax1.plot(temps, df_overall["Mean_Raw_M1_BER_Pct"], "o-", lw=2.2, ms=7, color="#D95F02", label="Raw Mode 1 (Supply Tilts)")
    ax1.plot(temps, df_overall["Mean_Raw_M2_BER_Pct"], "s--", lw=2.0, ms=6.5, color="#7570B3", label="Raw Mode 2 (Supply Tilts)")
    ax1.plot(temps, df_overall["Mean_Healed_Unmasked_BER_Pct"], "^-", lw=2.2, ms=7.5, color="#1B9E77", label="Mode-2 Self-Healing (No Masking)")
    ax1.plot(temps, df_overall["Temp_Drift_vs_27C_M1_BER_Pct"], "x:", lw=2.0, ms=7, color="#E7298A", label="Nominal Temp Drift vs. 27°C")
    ax1.plot(temps, df_overall["Mean_Final_Valid_BER_Pct"], "D-", lw=2.2, ms=6.5, color="#000000", label="Preselection + Self-Healing")

    ax1.set_title("(a) Bit Error Rate (BER) vs. Temperature", fontsize=12, fontweight="bold")
    ax1.set_xlabel("Temperature (°C)", fontsize=11, fontweight="bold")
    ax1.set_ylabel("BER (%)", fontsize=11, fontweight="bold")
    ax1.set_xticks(temps)
    ax1.set_xticklabels([f"{t}°C" for t in temps], fontweight="bold")
    ax1.grid(True, linestyle="--", alpha=0.45)
    ax1.legend(loc="best", fontsize=9, frameon=True)

    ax2.plot(temps, df_overall["Raw_M1_BLER_128b_Pct"], "o-", lw=2.2, ms=7, color="#D95F02", label="Raw Mode 1 (128-bit BLER)")
    ax2.plot(temps, df_overall["Healed_BLER_128b_Pct"], "^-", lw=2.2, ms=7.5, color="#1B9E77", label="Mode-2 Self-Healing (128-bit BLER)")
    ax2.plot(temps, df_overall["Final_BLER_128b_Pct"], "D-", lw=2.2, ms=6.5, color="#000000", label="Preselection + Self-Healing (128-bit BLER)")

    ax2.set_title("(b) 128-Bit Block Error Rate (BLER) vs. Temperature", fontsize=12, fontweight="bold")
    ax2.set_xlabel("Temperature (°C)", fontsize=11, fontweight="bold")
    ax2.set_ylabel("128-Bit BLER (%)", fontsize=11, fontweight="bold")
    ax2.set_xticks(temps)
    ax2.set_xticklabels([f"{t}°C" for t in temps], fontweight="bold")
    ax2.set_ylim(-4, 108)
    ax2.grid(True, linestyle="--", alpha=0.45)
    ax2.legend(loc="best", fontsize=9, frameon=True)

    plt.suptitle("16×16 SRAM PUF Reliability Across Temperature (-100°C to 75°C)", fontsize=13.5, fontweight="bold", y=1.01)
    plt.tight_layout()
    plt.savefig("puf_16x16_ber_bler_vs_temperature.png", dpi=300, bbox_inches="tight")
    print("Saved BER & BLER vs. Temperature plot -> 'puf_16x16_ber_bler_vs_temperature.png'")
    plt.show()

    # ==========================================================================
    # 5. PLOT 2: PER-TILT CORNER BER (±50mV, ±80mV, ±120mV) VS. TEMPERATURE
    # ==========================================================================
    fig, (ax_raw, ax_heal) = plt.subplots(1, 2, figsize=(14, 5), dpi=300, sharey=True)
    tilt_colors = {
        "+50mV": "#66C2A5",
        "-50mV": "#8DA0CB",
        "+80mV": "#FC8D62",
        "-80mV": "#E78AC3",
        "+120mV": "#E41A1C",
        "-120mV": "#377EB8",
    }

    for tilt in TILT_ORDER:
        sub = df_tilts[df_tilts["Tilt"] == tilt].sort_values("Temp_C")
        ax_raw.plot(
            sub["Temp_C"],
            sub["Raw_M1_BER_Pct"],
            marker="o",
            lw=2,
            color=tilt_colors[tilt],
            label=tilt,
        )
        ax_heal.plot(
            sub["Temp_C"],
            sub["Healed_Unmasked_BER_Pct"],
            marker="^",
            lw=2,
            color=tilt_colors[tilt],
            label=tilt,
        )

    ax_raw.set_title("(a) Raw Mode 1 BER by Supply Tilt", fontsize=12, fontweight="bold")
    ax_raw.set_xlabel("Temperature (°C)", fontsize=11, fontweight="bold")
    ax_raw.set_ylabel("Bit Error Rate — BER (%)", fontsize=11, fontweight="bold")
    ax_raw.set_xticks(temps)
    ax_raw.set_xticklabels([f"{t}°C" for t in temps], fontweight="bold")
    ax_raw.grid(True, linestyle="--", alpha=0.45)
    ax_raw.legend(title="Supply Tilt", fontsize=9, frameon=True)

    ax_heal.set_title("(b) After Mode-2 Self-Healing (Unmasked) by Supply Tilt", fontsize=12, fontweight="bold")
    ax_heal.set_xlabel("Temperature (°C)", fontsize=11, fontweight="bold")
    ax_heal.set_xticks(temps)
    ax_heal.set_xticklabels([f"{t}°C" for t in temps], fontweight="bold")
    ax_heal.grid(True, linestyle="--", alpha=0.45)
    ax_heal.legend(title="Supply Tilt", fontsize=9, frameon=True)

    plt.suptitle("16×16 SRAM PUF Supply Tilt Sensitivity Across Temperature (-100°C to 75°C)", fontsize=13.5, fontweight="bold", y=1.01)
    plt.tight_layout()
    plt.savefig("puf_16x16_tilt_ber_vs_temperature.png", dpi=300, bbox_inches="tight")
    print("Saved per-tilt BER vs. Temperature plot -> 'puf_16x16_tilt_ber_vs_temperature.png'")
    plt.show()


if __name__ == "__main__":
    run_ber_bler_vs_temperature()
