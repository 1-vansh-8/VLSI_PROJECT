"""
05_golden_key_ber_masking_summary.py
====================================
Golden keys (0.9 V, 0 mV), BER / unstable bits / flip direction for raw, healed and masked keys across
VDD = 0.8-1.0 V and |Vd| = 0-120 mV, plus the BER-vs-tilt, BER-vs-VDD, flip and masking figures.
Source: notebooks/VLSI_project_SRAM_PUF.ipynb, cell(s) 31.
Usage: python scripts/05_golden_key_ber_masking_summary.py --data data/raw
"""

# --- added for the repository: run against the folder holding the raw mc_*.csv files
import argparse as _ap, os as _os
_p = _ap.ArgumentParser(description=__doc__, formatter_class=_ap.RawDescriptionHelpFormatter)
_p.add_argument("--data", default="data/raw", help="folder with the raw Cadence mc_*.csv files (outputs are written there)")
_args, _ = _p.parse_known_args()
_os.chdir(_args.data)

import os
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch


CSV_FILES = [
    # VDD = 0.8V
    "mc_256_0.8_vdd-120.csv",
    "mc_256_0.8_vdd-80.csv",
    "mc_256_0.8_vdd-50.csv",
    "mc_256_0.8_vdd.csv",
    "mc_256_0.8_vdd+50.csv",
    "mc_256_0.8_vdd+80.csv",
    "mc_256_0.8_vdd+120.csv",
    # VDD = 0.9V
    "mc_256_0.9_vdd-120.csv",
    "mc_256_0.9_vdd-80.csv",
    "mc_256_0.9_vdd-50.csv",
    "mc_256_0.9_vdd.csv",
    "mc_256_0.9_vdd+50.csv",
    "mc_256_0.9_vdd+80.csv",
    "mc_256_0.9_vdd+120.csv",
    # VDD = 1.0V
    "mc_256_1.0_vdd-120.csv",
    "mc_256_1.0_vdd-80.csv",
    "mc_256_1.0_vdd-50.csv",
    "mc_256_1.0_vdd.csv",
    "mc_256_1.0_vdd+50.csv",
    "mc_256_1.0_vdd+80.csv",
    "mc_256_1.0_vdd+120.csv",
]


def extract_cell_bits(csv_path, vdd):
    """Extracts 256-bit logic responses for Mode 1 (97-103ns) and Mode 2 (37-43ns)."""
    df = pd.read_csv(csv_path, low_memory=False)
    threshold = vdd / 2.0

    cols = df.columns
    paramset_ids = sorted(
        list(set(int(x) for x in re.findall(r"mcparamset=(\d+)", " ".join(cols))))
    )

    m2_t_min, m2_t_max = 37e-9, 43e-9
    m1_t_min, m1_t_max = 97e-9, 103e-9

    bits_m2 = np.zeros(len(paramset_ids), dtype=int)
    bits_m1 = np.zeros(len(paramset_ids), dtype=int)

    for idx, mc_id in enumerate(paramset_ids):
        t_bl = pd.to_numeric(df[f"/BL (mcparamset={mc_id}) X"], errors="coerce").values
        v_bl = pd.to_numeric(df[f"/BL (mcparamset={mc_id}) Y"], errors="coerce").values

        mask_m2 = (t_bl >= m2_t_min) & (t_bl <= m2_t_max)
        mask_m1 = (t_bl >= m1_t_min) & (t_bl <= m1_t_max)

        v_m2 = np.mean(v_bl[mask_m2]) if np.any(mask_m2) else np.nan
        v_m1 = np.mean(v_bl[mask_m1]) if np.any(mask_m1) else np.nan

        bits_m2[idx] = 1 if v_m2 >= threshold else 0
        bits_m1[idx] = 1 if v_m1 >= threshold else 0

    return paramset_ids, bits_m1, bits_m2


def bits_to_hex(bits):
    bit_str = "".join(str(b) for b in bits)
    hex_str = hex(int(bit_str, 2))[2:].upper().zfill(len(bits) // 4)
    return hex_str, bit_str


def get_symmetrical_responses(dataset, vdd, tilt_mag):
    """Returns [(M1, M2)] for tilt_mag=0, or [(M1_+Vd, M2_+Vd), (M1_-Vd, M2_-Vd)] for |Vd|>0."""
    if tilt_mag == 0:
        return [(dataset[(vdd, 0)]["M1"], dataset[(vdd, 0)]["M2"])] if (vdd, 0) in dataset else []
    pairs = []
    if (vdd, +tilt_mag) in dataset:
        pairs.append((dataset[(vdd, +tilt_mag)]["M1"], dataset[(vdd, +tilt_mag)]["M2"]))
    if (vdd, -tilt_mag) in dataset:
        pairs.append((dataset[(vdd, -tilt_mag)]["M1"], dataset[(vdd, -tilt_mag)]["M2"]))
    return pairs


def run_paper_analysis(csv_filenames=CSV_FILES, golden_vdd=0.9, heal_vd=80):
    dataset = {}
    pattern = re.compile(r"mc_256_([0-9.]+)_vdd([+-]\d+)?\.csv$")

    for fname in csv_filenames:
        if not os.path.isfile(fname):
            print(f"[SKIPPED - Not Uploaded] {fname}")
            continue
        m = pattern.match(fname)
        if not m:
            continue
        vdd = float(m.group(1))
        tilt = int(m.group(2)) if m.group(2) else 0
        ids, b_m1, b_m2 = extract_cell_bits(fname, vdd)
        dataset[(vdd, tilt)] = {"mc_ids": ids, "M1": b_m1, "M2": b_m2}
        print(f"[LOADED] {fname:26s} -> VDD={vdd:.1f}V, Tilt={tilt:+4d}mV")

    if (golden_vdd, 0) not in dataset:
        raise FileNotFoundError(f"Nominal baseline file 'mc_256_{golden_vdd}_vdd.csv' is required!")

    # 1. Extract and Print Golden Key (Nominal VDD = 0.9V, Tilt = 0mV)
    gk_m1 = dataset[(golden_vdd, 0)]["M1"]
    gk_m2 = dataset[(golden_vdd, 0)]["M2"]
    n_bits = len(gk_m1)

    hex_m1, bin_m1 = bits_to_hex(gk_m1)
    hex_m2, bin_m2 = bits_to_hex(gk_m2)

    print("\n" + "=" * 80)
    print(f"GOLDEN KEY (EXTRACTED AT NOMINAL VDD = {golden_vdd}V, Tilt = 0mV)")
    print("=" * 80)
    print(f"Mode 1 (97-103ns) HEX : {hex_m1}")
    print(f"Mode 1 (97-103ns) BIN : {bin_m1}")
    print("-" * 80)
    print(f"Mode 2 (37-43ns)  HEX : {hex_m2}")
    print(f"Mode 2 (37-43ns)  BIN : {bin_m2}")
    print("=" * 80 + "\n")

    pd.DataFrame({
        "mc_id": dataset[(golden_vdd, 0)]["mc_ids"],
        "Golden_Key_M1": gk_m1,
        "Golden_Key_M2": gk_m2,
    }).to_csv("golden_key_256bit.csv", index=False)

    # 2. Voltage-Tilt Preselection & Self-Healing (Paper Section III-B, Vd = 80mV)
    presel_vdd = None
    for cand in [golden_vdd, 0.8, 1.0]:
        if (cand, +heal_vd) in dataset and (cand, -heal_vd) in dataset:
            presel_vdd = cand
            break

    if presel_vdd is not None:
        m1_stable = dataset[(presel_vdd, +heal_vd)]["M1"] == dataset[(presel_vdd, -heal_vd)]["M1"]
        m2_stable = dataset[(presel_vdd, +heal_vd)]["M2"] == dataset[(presel_vdd, -heal_vd)]["M2"]
    else:
        m1_stable = np.ones(n_bits, dtype=bool)
        m2_stable = np.ones(n_bits, dtype=bool)

    repaired_mask = (~m1_stable) & m2_stable
    discarded_mask = (~m1_stable) & (~m2_stable)
    gk_healed = np.where(repaired_mask, gk_m2, gk_m1)

    # Pre-Irradiation Voltage Mask (cells stable across VDD corners 0.8V, 0.9V, 1.0V)
    volt_valid_mask = ~discarded_mask
    for v_corner in [0.8, 0.9, 1.0]:
        if (v_corner, 0) in dataset:
            healed_corner = np.where(
                repaired_mask, dataset[(v_corner, 0)]["M2"], dataset[(v_corner, 0)]["M1"]
            )
            volt_valid_mask &= (healed_corner == gk_healed)

    # Pre-Irradiation Tilt & Voltage Mask (also discards cells flipping at +/-120mV)
    full_valid_mask = volt_valid_mask.copy()
    for v_corner in [0.8, 0.9, 1.0]:
        for t_mag in [80, 120]:
            if (v_corner, +t_mag) in dataset and (v_corner, -t_mag) in dataset:
                h_pos = np.where(
                    repaired_mask, dataset[(v_corner, +t_mag)]["M2"], dataset[(v_corner, +t_mag)]["M1"]
                )
                h_neg = np.where(
                    repaired_mask, dataset[(v_corner, -t_mag)]["M2"], dataset[(v_corner, -t_mag)]["M1"]
                )
                full_valid_mask &= (h_pos == h_neg) & (h_pos == gk_healed)

    print(f"Self-Healing Preselection (Vd = +/-{heal_vd}mV at VDD = {presel_vdd}V):")
    print(f"  - Mode 1 Native Stable Bits : {m1_stable.sum():3d} / {n_bits} ({m1_stable.mean()*100:.2f}%)")
    print(f"  - Repaired via Mode 2       : {repaired_mask.sum():3d} / {n_bits} ({repaired_mask.mean()*100:.2f}%)")
    print(f"  - Discarded (Unstable Both) : {discarded_mask.sum():3d} / {n_bits} ({discarded_mask.mean()*100:.2f}%)\n")

    # 3. Compute Symmetrical Metrics Across VDDs and TID-Equivalent Tilts (0, 50, 80, 120 mV)
    vdds_ordered = [0.8, 0.9, 1.0]
    tilt_mags = [0, 50, 80, 120]
    records = []

    for vdd in vdds_ordered:
        for mag in tilt_mags:
            pairs = get_symmetrical_responses(dataset, vdd, mag)
            if not pairs:
                continue

            raw_m1_bers = [np.mean(m1 != gk_m1) * 100.0 for m1, _ in pairs]
            raw_m2_bers = [np.mean(m2 != gk_m2) * 100.0 for _, m2 in pairs]
            heal_bers = [
                np.mean(np.where(repaired_mask, m2, m1) != gk_healed) * 100.0
                for m1, m2 in pairs
            ]
            heal_vmask_bers = [
                np.mean(np.where(repaired_mask, m2, m1)[volt_valid_mask] != gk_healed[volt_valid_mask]) * 100.0
                for m1, m2 in pairs
            ]
            heal_fullmask_bers = [
                np.mean(np.where(repaired_mask, m2, m1)[full_valid_mask] != gk_healed[full_valid_mask]) * 100.0
                for m1, m2 in pairs
            ]

            if len(pairs) == 2:
                unst_m1 = np.mean(pairs[0][0] != pairs[1][0]) * 100.0
                unst_m2 = np.mean(pairs[0][1] != pairs[1][1]) * 100.0
                unst_heal = np.mean(
                    np.where(repaired_mask, pairs[0][1], pairs[0][0])
                    != np.where(repaired_mask, pairs[1][1], pairs[1][0])
                ) * 100.0
            else:
                unst_m1 = float(np.mean(raw_m1_bers))
                unst_m2 = float(np.mean(raw_m2_bers))
                unst_heal = float(np.mean(heal_bers))

            flip_1_to_0 = np.mean([np.mean((gk_m1 == 1) & (m1 == 0)) * 100.0 for m1, _ in pairs])
            flip_0_to_1 = np.mean([np.mean((gk_m1 == 0) & (m1 == 1)) * 100.0 for m1, _ in pairs])

            records.append({
                "VDD_V": vdd,
                "TID_Tilt_mV": mag,
                "Skew_Dirs": len(pairs),
                "Raw_M1_BER_pct": round(float(np.mean(raw_m1_bers)), 4),
                "Raw_M2_BER_pct": round(float(np.mean(raw_m2_bers)), 4),
                "SelfHeal_BER_pct": round(float(np.mean(heal_bers)), 4),
                "Heal_VoltMask_BER_pct": round(float(np.mean(heal_vmask_bers)), 4),
                "Heal_TiltVoltMask_BER_pct": round(float(np.mean(heal_fullmask_bers)), 4),
                "Unstable_M1_pct": round(float(unst_m1), 4),
                "Unstable_M2_pct": round(float(unst_m2), 4),
                "Unstable_Heal_pct": round(float(unst_heal), 4),
                "Flip_1to0_pct": round(float(flip_1_to_0), 4),
                "Flip_0to1_pct": round(float(flip_0_to_1), 4),
            })

    summary_df = pd.DataFrame(records)
    summary_df.to_csv("paper_symmetrical_tid_ber_summary.csv", index=False)
    print(summary_df.to_string(index=False))

    # =========================================================================
    # PLOT 1 (Paper Fig. 10): 16x16 Spatial Map of Raw vs Self-Healing Array
    # =========================================================================
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.3), dpi=150)
    cmap = ListedColormap(["#7f7f7f", "#ffeb3b", "#2ecc71", "#e67e22"])

    map_raw = np.where(m1_stable, 0, 1).reshape(16, 16)
    map_presel = np.zeros(n_bits, dtype=int)
    map_presel[repaired_mask] = 2
    map_presel[discarded_mask] = 3
    map_presel = map_presel.reshape(16, 16)
    map_final = np.where(discarded_mask, 1, 0).reshape(16, 16)

    titles_10 = [
        "(a) Raw Mode 1 Responses",
        "(b) Preselection & Healing Classification",
        "(c) After Self-Healing Mechanism",
    ]
    for ax, grid, title in zip(axes, [map_raw, map_presel, map_final], titles_10):
        ax.imshow(grid, cmap=cmap, vmin=0, vmax=3)
        ax.set_title(title, fontsize=10.5, fontweight="bold")
        ax.set_xticks([0, 4, 8, 12, 15])
        ax.set_yticks([0, 4, 8, 12, 15])

    legend_items = [
        Patch(facecolor="#7f7f7f", label="Stable Bits"),
        Patch(facecolor="#ffeb3b", label="Unstable Bits"),
        Patch(facecolor="#2ecc71", label="Repaired Bits (Mode 2)"),
        Patch(facecolor="#e67e22", label="Discarded Bits"),
    ]
    fig.legend(handles=legend_items, loc="center right", bbox_to_anchor=(1.13, 0.5), fontsize=9)
    fig.suptitle(
        f"Fig. 10: 256-Cell (16×16) Spatial Stability & Self-Healing Map (Vd = ±{heal_vd}mV)",
        fontsize=12, fontweight="bold"
    )
    fig.tight_layout()
    fig.savefig("Paper_Fig10_Spatial_SelfHealing_Map.png", bbox_inches="tight")
    plt.show()

    # =========================================================================
    # PLOT 2 (Paper Fig. 16): Symmetrical BER & Unstable Bits vs TID Tilt (mV)
    # =========================================================================
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.5, 4.8), dpi=150)
    vdd_styles = {
        0.8: ("o-", "#d62728", "VDD = 0.8V"),
        0.9: ("s-", "#1f77b4", "VDD = 0.9V (Nominal)"),
        1.0: ("^-", "#2ca02c", "VDD = 1.0V"),
    }

    for vdd, (style, col, lbl) in vdd_styles.items():
        sub = summary_df[summary_df["VDD_V"] == vdd].sort_values("TID_Tilt_mV")
        if sub.empty:
            continue
        ax1.plot(sub["TID_Tilt_mV"], sub["Raw_M1_BER_pct"], style, color=col, linewidth=2.2, markersize=7, label=f"{lbl} (Raw Mode 1)")
        ax1.plot(sub["TID_Tilt_mV"], sub["SelfHeal_BER_pct"], "--", marker=style[0], color=col, alpha=0.65, linewidth=1.8, markersize=6, label=f"{lbl} (Self-Healed)")

        ax2.plot(sub["TID_Tilt_mV"], sub["Unstable_M1_pct"], style, color=col, linewidth=2.2, markersize=7, label=f"{lbl} (Raw Mode 1)")
        ax2.plot(sub["TID_Tilt_mV"], sub["Unstable_Heal_pct"], "--", marker=style[0], color=col, alpha=0.65, linewidth=1.8, markersize=6, label=f"{lbl} (Self-Healed)")

    ax1.set_title("(a) Symmetrical BER vs. TID-Equivalent Tilt", fontsize=11.5, fontweight="bold")
    ax1.set_xlabel("TID-Equivalent Voltage Tilt |Vd| (mV)", fontsize=10.5)
    ax1.set_ylabel("Bit Error Rate — BER (%)", fontsize=10.5)
    ax1.set_xticks(tilt_mags)
    ax1.grid(True, linestyle="--", alpha=0.5)
    ax1.legend(fontsize=8)

    ax2.set_title("(b) Unstable Bits (%) vs. TID-Equivalent Tilt", fontsize=11.5, fontweight="bold")
    ax2.set_xlabel("TID-Equivalent Voltage Tilt |Vd| (mV)", fontsize=10.5)
    ax2.set_ylabel("Unstable Bits (%)", fontsize=10.5)
    ax2.set_xticks(tilt_mags)
    ax2.grid(True, linestyle="--", alpha=0.5)
    ax2.legend(fontsize=8)

    fig.suptitle("Fig. 16: Symmetrical BER & Unstable Bits vs. TID Radiation Stress (Voltage Tilt)", fontsize=12.5, fontweight="bold")
    fig.tight_layout()
    fig.savefig("Paper_Fig16_BER_and_UnstableBits_vs_Tilt.png")
    plt.show()

    # =========================================================================
    # PLOT 3 (Paper Fig. 12b): Symmetrical BER vs Supply Voltage (VDD)
    # =========================================================================
    fig, ax = plt.subplots(figsize=(8.5, 5.0), dpi=150)
    tilt_styles = {
        50: ("o-", "#1f77b4", "Tilt = ±50mV"),
        80: ("s-", "#d62728", "Tilt = ±80mV"),
        120: ("^-", "#2ca02c", "Tilt = ±120mV"),
    }
    for mag, (style, col, lbl) in tilt_styles.items():
        sub = summary_df[summary_df["TID_Tilt_mV"] == mag].sort_values("VDD_V")
        if sub.empty:
            continue
        ax.plot(sub["VDD_V"], sub["Raw_M1_BER_pct"], style, color=col, linewidth=2.2, markersize=7, label=f"Raw Mode 1 ({lbl})")
        ax.plot(sub["VDD_V"], sub["SelfHeal_BER_pct"], "--", marker=style[0], color=col, alpha=0.7, linewidth=1.8, markersize=6, label=f"Self-Healed ({lbl})")

    ax.set_title("Fig. 12(b): Symmetrical BER vs. Supply Voltage (VDD)", fontsize=12, fontweight="bold")
    ax.set_xlabel("Supply Voltage — VDD (V)", fontsize=11)
    ax.set_ylabel("Bit Error Rate — BER (%)", fontsize=11)
    ax.set_xticks(vdds_ordered)
    ax.set_xlim(0.75, 1.05)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(fontsize=8.5, ncol=2)
    fig.tight_layout()
    fig.savefig("Paper_Fig12b_BER_vs_VDD_Symmetrical.png")
    plt.show()

    # =========================================================================
    # PLOT 4 (Paper Fig. 19): Bit Flipping Direction (1->0 vs 0->1) vs Tilt
    # =========================================================================
    fig, ax = plt.subplots(figsize=(8.5, 4.8), dpi=150)
    sub_flip = summary_df[summary_df["TID_Tilt_mV"] > 0].copy()
    sub_flip["Label"] = sub_flip.apply(lambda r: f"{r['VDD_V']:.1f}V\n±{int(r['TID_Tilt_mV'])}mV", axis=1)
    x = np.arange(len(sub_flip))
    width = 0.36

    rects1 = ax.bar(x - width / 2, sub_flip["Flip_1to0_pct"], width, label="1 → 0 Bit Flipping (%)", color="#e67e22", edgecolor="black")
    rects2 = ax.bar(x + width / 2, sub_flip["Flip_0to1_pct"], width, label="0 → 1 Bit Flipping (%)", color="#2ecc71", edgecolor="black")

    ax.bar_label(rects1, fmt="%.2f%%", padding=2, fontsize=7.5)
    ax.bar_label(rects2, fmt="%.2f%%", padding=2, fontsize=7.5)

    ax.set_title("Fig. 19: Directional Bit Flipping (1→0 vs. 0→1) Under Symmetrical Tilt", fontsize=11.5, fontweight="bold")
    ax.set_ylabel("Bit Flipping (%)", fontsize=11)
    ax.set_xticks(x)
    ax.set_xticklabels(sub_flip["Label"], fontsize=9)
    ax.set_ylim(0, max(5.0, sub_flip[["Flip_1to0_pct", "Flip_0to1_pct"]].values.max() + 1.0))
    ax.grid(True, axis="y", linestyle="--", alpha=0.5)
    ax.legend(fontsize=9.5)
    fig.tight_layout()
    fig.savefig("Paper_Fig19_BitFlipping_Direction.png")
    plt.show()

    # =========================================================================
    # PLOT 5 (Paper Fig. 21): Raw vs Self-Heal vs Pre-Irradiation Masking
    # =========================================================================
    available_vdds = [v for v in vdds_ordered if not summary_df[summary_df["VDD_V"] == v].empty]
    fig, axes = plt.subplots(1, len(available_vdds), figsize=(6.5 * len(available_vdds), 5.0), dpi=150, squeeze=False)

    for idx, vdd in enumerate(available_vdds):
        ax = axes[0, idx]
        sub = summary_df[summary_df["VDD_V"] == vdd].sort_values("TID_Tilt_mV")
        tilts = sub["TID_Tilt_mV"].values

        ax.plot(tilts, sub["Raw_M1_BER_pct"], "o-", color="#d62728", linewidth=2.2, markersize=7, label="Raw PUF (Mode 1)")
        ax.plot(tilts, sub["SelfHeal_BER_pct"], "^-", color="#1f77b4", linewidth=2.2, markersize=7, label="Self-Heal (Mode 1 + Mode 2)")
        ax.plot(tilts, sub["Heal_VoltMask_BER_pct"], "d-", color="#9467bd", linewidth=2.0, markersize=7, label="Heal + Voltage Mask")
        ax.plot(tilts, sub["Heal_TiltVoltMask_BER_pct"], "s-", color="#2ca02c", linewidth=2.2, markersize=7, label="Heal + Tilt & Voltage Mask")

        for x_val, y_raw, y_heal in zip(tilts, sub["Raw_M1_BER_pct"], sub["SelfHeal_BER_pct"]):
            ax.annotate(f"{y_raw:.2f}%", (x_val, y_raw), textcoords="offset points", xytext=(0, 7),
                        ha="center", fontsize=8, color="#d62728", fontweight="bold")
            ax.annotate(f"{y_heal:.2f}%", (x_val, y_heal), textcoords="offset points", xytext=(0, -13),
                        ha="center", fontsize=8, color="#1f77b4", fontweight="bold")

        ax.set_title(f"VDD = {vdd:.1f}V", fontsize=11.5, fontweight="bold")
        ax.set_xlabel("TID-Equivalent Voltage Tilt |Vd| (mV)", fontsize=10.5)
        if idx == 0:
            ax.set_ylabel("Bit Error Rate — BER (%)", fontsize=10.5)
        ax.set_xticks(tilt_mags)
        ax.set_ylim(-0.5, max(7.0, sub["Raw_M1_BER_pct"].max() + 1.2))
        ax.grid(True, linestyle="--", alpha=0.5)
        ax.legend(loc="upper left", fontsize=8.2, frameon=True)

    fig.suptitle("Fig. 21: BER Reduction via Self-Healing & Pre-Irradiation Masking vs. TID Tilt", fontsize=12.5, fontweight="bold")
    fig.tight_layout()
    fig.savefig("Paper_Fig21_SelfHealing_and_Masking_BER.png")
    plt.show()


if __name__ == "__main__":
    run_paper_analysis()
