# 16×16 Dual-Mode Self-Healing SRAM PUF in UMC 28 nm (Cadence Virtuoso)

**Authors:** Vansh Goel (24110379) · Himani Goel (24110134)
**Course:** EE 617: VLSI Design, IIT Gandhinagar · **Instructor:** Prof. Joycee Mekie
**Reference design:** Z. Chen *et al.*, IEEE TVLSI 2024 [1]

A **15-transistor dual-mode SRAM physical unclonable function (PUF)** with **voltage-tilt preselection and
self-healing**, implemented as a **16×16 array** in **UMC 28 nm HPC CMOS** (`l28hpc_mm_v1201.lib.scs`) in Cadence
Virtuoso, with its full periphery: 7-bit capacitive tilt DAC, 4-to-16 row decoder, mode/wordline drivers, bitline
precharge and write drivers, sense-amplifier key readout and stability-decision circuit. Monte Carlo simulation of
the 16×16 array and a 32×64 array characterises reliability across supply tilt, supply voltage (0.8–1.0 V, nominal
0.9 V) and temperature (−100 to 75 °C).

**Report (IEEE two-column, 14 pages):** [`report/16x16_SRAM_PUF_Technical_Report.pdf`](report/16x16_SRAM_PUF_Technical_Report.pdf)
**Notebook with all results:** [`notebooks/VLSI_project_SRAM_PUF.ipynb`](notebooks/VLSI_project_SRAM_PUF.ipynb) · **Tables:** [`results/`](results/)

---

## Contents
1. [Headline results](#1-headline-results)
2. [Motivation](#2-motivation)
3. [Reference design and self-healing principle](#3-reference-design-and-self-healing-principle)
4. [Array architecture](#4-array-architecture)
5. [Circuit schematics (Cadence)](#5-circuit-schematics-cadence)
6. [Functional verification and timing](#6-functional-verification-and-timing)
7. [Cadence server directory structure](#7-cadence-virtuoso-server-design--simulation-directory-structure)
8. [Monte Carlo results and comparisons](#8-monte-carlo-results)
9. [Limitations and future work](#9-limitations-and-future-work)
10. [Repository layout and how to run](#10-repository-layout-and-how-to-run)
11. [References](#11-references)

---

## 1. Headline results

| Quantity | Value |
|---|---|
| Mode 1 unstable cells, 16×16, 27 °C, 0.9 V, \|Vd\| = 50 / 80 / 120 mV | 5.47 / 8.20 / 11.72 % |
| Healing efficiency (unstable cells repaired by Mode 2), 16×16 | 93.3–100 % |
| 32×64 array, ±120 mV: unstable → repaired → discarded | 211 → 191 → 20 (valid yield **99.02 %**) |
| Mode 1 vs. Mode 2 golden keys (256 bits) differ in | 125 bits (48.8 %) |
| Raw → healed BER, 0.9 V, ±120 mV (healing chosen at ±80 mV) | 5.86 % → 1.76 % (3.3×; paper: 2.3–2.7×) |
| Valid-bit yield at −100 / −40 / 0 / 27 / 75 °C | 100 / 100 / 99.61 / 99.61 / 96.88 % |
| Mean raw Mode 1 tilt BER, −100 → 75 °C | 0.26 % → 6.12 % |
| Mean healed tilt BER (unmasked), −100 → 75 °C | 0.00 % → 0.91 % |
| Healed 128-bit BLER at 27 °C / 75 °C | 15.4 % / 69.0 % (raw: 99.6 % / 99.97 %) |

---

## 2. Motivation

Secure devices such as satellites need a secret key to prove they are genuine, but a key stored in memory can be
read or copied. A PUF instead derives the key from tiny random manufacturing variations that are unique to each
chip, so it never has to be stored. Some PUF bits, however, are unstable and flip with noise, temperature, voltage
or radiation, causing authentication failures. Existing fixes (ECC, majority voting, burn-in, dark-bit masking) are
costly or need extensive or destructive testing [1]. The design of [1] detects its own weak bits and replaces them
with a backup mode inside the same cell, reducing the post-irradiation BER from about 5 % to 0.018 %.

## 3. Reference design and self-healing principle

<p align="center"><img src="docs/reference_paper/paper_15T_cell_annotated_phase0.png" width="540"><br>
<em>Reference 15T multimode cell and sizes, from [1, Fig. 2(a)], block colouring from our Phase 0 presentation [2].</em></p>

| Mode | EN0 | EN1 | Discharge path |
|---|---|---|---|
| Mode 1 | 0 | 1 | Q/QB → M3/M4 → M13 → M15 → GND |
| Mode 2 | 1 | 0 | Q/QB → M11/M12 → M14 → M15 → GND |
| Sleep / precharge | 0 | 0 | none; Q = QB = VDD |

**One evaluation [3]:** precharge (EN0 = EN1 = 0, Q = QB = VDD, no path to ground) → evaluate (one enable high,
precharge off, both nodes discharge through the selected pair) → race (mismatch makes one node fall faster) →
resolve (|VQ − VQB| > Vsep, positive feedback gives a full 0/1) → read (WL high, bit onto BL) → sleep.

<p align="center"><img src="docs/reference_paper/paper_voltage_tilt_procedure.png" width="260"><br>
<em>Voltage-tilt preselection, from [1, Fig. 3(b)].</em></p>

**Voltage tilt:** read with VDDL = VDD + Vd, VDDR = VDD − Vd, then with the tilt reversed. Same bit → stable; different
→ unstable in that mode, retry in the other mode.

<p align="center"><img src="figures/selfhealing_flow.png" width="330"></p>

* **Stable**: Mode 1 never flips → keep Mode 1.  **Repaired**: Mode 1 flips, Mode 2 never flips → use Mode 2.
  **Discarded (dark)**: both flip → mask.

## 4. Array architecture

<p align="center"><img src="docs/schematics/00_architecture_16x16.png" width="900"><br>
<em>Implemented 16×16 architecture (library <code>project</code>, cell <code>16x16array</code>, UMC 28 nm HPC, Spectre).</em></p>

| Block | Instance | Function |
|---|---|---|
| Row decoder | I531 | 4-to-16 (two 2-to-4 predecoders I4, I5 + 2-to-4 decoders I0–I3): ROW_ADDR<3:0> → DEC_B<15:0> (active low) |
| Mode / WL driver | I530 | 16 × `wl_driver-1bit` (inverters + NORs): DEC_B, MODE_0, MODE_1, READ_EN → EN0<15:0>, EN1<15:0>, WL<15:0> |
| Precharge | I_PRECHARGE<15:0> | BL/BLb → VDD when PCH = 0 |
| Bit-cell array | 256 × `sram15T` | Column c → BL<c>/BLb<c>; row r → WL<r>, EN0<r>, EN1<r>; supplies VDDL, VDDR |
| Write driver | I_WD<15:0> | Drives BL = din, BLb = din̄ when WEN; high-Z otherwise |
| Key readout | 16 × `keyreadout` | Single-ended SA (BL vs. Vref) → glitch filter → SR latch → DFF → PUF_OUT<15:0> |
| Stability decision | 16 × `stability` | DFF (PUF_OUT↑) + DFF (PUF_OUT↓ via inverter) → NOR → STABLE<15:0> |
| Power control | I532 `pwrctrl` | Two 7-bit capacitive DACs: VDDL from A<6:0>, VDDR from B<6:0>; reset by PCH |

Rows are evaluated and read one at a time: only 16 cells draw current at once and unselected rows stay in sleep.

## 5. Circuit schematics (Cadence)

### 5.1 15T bit-cell

<p align="center"><img src="docs/schematics/01_sram15T_bitcell.png" width="620"></p>

Pins BL, BLb, EN0, EN1, GND, VDD, VDDL, VDDR, WL. Cross-coupled pMOS PM0/PM1 on VDDR/VDDL; two nMOS pull-down pairs
(NM7/NM8, NM5/NM6) selected by NM3 (EN1) and NM4 (EN0); weak footer NM2 (W/L = 120 nm/1 µm) so the core, not the
footer, decides the race; precharge PM2/PM3; WL-gated readout NM0/NM1 → BL and NM9/NM10 → BLb; OR(EN0, EN1) built
from NM11, NM12, PM4, PM5 (NOR) and PM6/NM13 (inverter).

### 5.2 Power-control DAC (`pwrctrl`)

<p align="center"><img src="docs/peripherals/01_power_control_dac_VDDL_VDDR.png" width="480">
<img src="docs/peripherals/02_power_control_dac_one_half.png" width="420"></p>

Two identical halves (top → VDDL, bottom → VDDR), each a 7-bit binary-weighted capacitor DAC (10 fF → 640 fF) with
all top plates on the output node and each bottom plate driven by an inverter acting as a VDD/VSS switch.
1) Reset: PCH turns on an nMOS, output → 0 V. 2) The 7-bit code ties selected bottom plates to VDD, the rest to VSS.
3) Charge redistributes: V_out = VDD × code/127 (≈ 7–8 mV per step). VDD/VSS and PCH are shared; codes A<6:0> and
B<6:0> are separate, so VDDL and VDDR are set independently. Capacitive DAC: almost no static power, programmable Vd,
compact.

### 5.3 Row control: decoder, WL drivers, mode/WL driver

<p align="center"><img src="docs/peripherals/08_decoder_2x4.png" width="300">
<img src="docs/peripherals/09_decoder_4x16.png" width="300"><br><em>2-to-4 decoder and the 4-to-16 decoder built from it.</em></p>

<p align="center"><img src="docs/peripherals/06_wl_driver_1bit.png" width="430">
<img src="docs/peripherals/07_wl_driver_16bit.png" width="380"><br><em>WL/mode driver for one row and for 16 rows
(each output is a NOR with active-low inputs, inverters on the active-high inputs).</em></p>

<p align="center"><img src="docs/peripherals/13_mode_wl_driver.png" width="300"><br><em><code>mode_wl_driver</code>.</em></p>

ROW_ADDR = k → DEC_B<k> = 0. MODE_0 or MODE_1 = 1 raises only EN0<k> or EN1<k> (row k evaluates in that mode; other
rows sleep). READ_EN = 1 raises only WL<k>; the row's 16 bits go to the 16 readouts. Repeat k = 0…15 for all 256 bits.

### 5.4 Bitline precharge and write driver

<p align="center"><img src="docs/peripherals/10_precharge.png" width="300">
<img src="docs/peripherals/12_write_driver.png" width="430"></p>

Precharge pulls BL and BLb to VDD when PCH is asserted. The write driver forces BL = din, BLb = din̄ when write is
enabled and goes high-Z when disabled (write driver, sense amplifier and DFF adapted from TA-provided cells).

### 5.5 Key readout and sense amplifier

<p align="center"><img src="docs/peripherals/03_key_readout.png" width="760"></p>
<p align="center"><img src="docs/peripherals/11_single_ended_sense_amplifier.png" width="560"></p>

1) Precharge: PCH = 0, BL → VDD, SAE off. 2) WL enable: stored 0 discharges BL slowly; stored 1 keeps it high.
3) Sense: SAE fires; the single-ended SA compares BL with VREF and gives a full-swing 0/1 by positive feedback.
4) Glitch filter: the direct output and a delayed copy (2-inverter buffer + 1 inverter) drive a 4-transistor stack, so
the output flips only if the new value outlasts the delay. 5) An SR latch (NOR pair, reset by PCH) holds the value;
D_TRAP clocks it into a DFF → PUF_OUT, which goes to the stability-decision circuit.

### 5.6 Stability decision and DFF

<p align="center"><img src="docs/peripherals/04_stability_detection.png" width="560"></p>
<p align="center"><img src="docs/peripherals/05_dff_with_reset.png" width="760"></p>

1) Pulse RN: both DFFs (D = 1) → 0, NOR → STABLE = 1. 2) Stage 1: tilt A (VDDL high), bit on PUF_OUT. 3) Stage 2:
tilt B (VDDR high), PUF_OUT updates. 4) Unchanged → no edge, STABLE = 1 (stable). 0→1 → DFF1 clocks → STABLE = 0.
1→0 → inverted to a rising edge → DFF2 clocks → STABLE = 0. A DFF with D = 1 is an edge detector with memory; the DFF
was given a reset pin for the active-low RN.

### 5.7 Full 16×16 array and 2×2 test array

<p align="center"><img src="docs/schematics/02_array_16x16_full.png" width="820"></p>
<p align="center">
<img src="docs/schematics/03_array_16x16_zoom1.png" width="400">
<img src="docs/schematics/04_array_16x16_zoom2.png" width="400"><br>
<img src="docs/schematics/05_array_16x16_zoom3.png" width="400">
<img src="docs/schematics/06_array_16x16_zoom4.png" width="400"><br><em>Zoomed views of the 16×16 array.</em></p>

<p align="center">
<img src="docs/schematics/07_array_2x2_test_a.png" width="440">
<img src="docs/schematics/08_array_2x2_test_b.png" width="300">
<img src="docs/schematics/09_array_2x2_test_c.png" width="300"><br><em>2×2 test array with all peripherals.</em></p>

## 6. Functional verification and timing

| Test | Waveform / output |
|---|---|
| Single cell under voltage tilt (VDDR, VDDL, WL, BLb, EN1, EN0, BL) | <img src="docs/simulations/01_single_cell_tilt_transient.png" width="430"> |
| Key readout (PCH, SAE, BL, Vref, D_TRAP, PUF_OUT) | <img src="docs/simulations/02_key_readout_transient.png" width="430"> |
| Stability decision (STABLE, PUF_OUT, RN) | <img src="docs/simulations/03_stability_detection_transient.png" width="430"> |
| 2×2 array, 0–90 ns (rails, EN0/EN1, RN, BL, STABLE) | <img src="docs/simulations/04_array_2x2_transient_a.png" width="430"> |
| 2×2 array, second view | <img src="docs/simulations/05_array_2x2_transient_b.png" width="430"> |
| Full-circuit sanity check | <img src="docs/simulations/07_full_circuit_sanity_check.png" width="430"> |
| 16×16 nominal verification: all 256 cells respond, 0 unstable (10 evaluations, TMV × 3) | <img src="docs/simulations/06_array_16x16_nominal_verification.png" width="430"> |
| Monte Carlo setup in ADE Explorer (PUF_OUT, STABLE for 16 columns) | <img src="docs/simulations/08_monte_carlo_setup_maestro.png" width="430"> |

Each block was simulated alone, then a 2×2 array with all peripherals, then the full 16×16 array. The nominal
(no-mismatch) 16×16 run shows every cell resolving to the same value, as expected without mismatch.

### Single-cell timing (0–500 ns)

![Single-cell timing diagram](docs/timing/single_cell_timing_diagram.png)

| Time (ns) | Signals | What happens |
|---|---|---|
| 0–10 | EN0 = EN1 = 0 | Precharge: Q and Qbar high, BL/BLb high |
| ≈10 | EN1 ↑ | Latch resolves: Qbar falls, Q stays high |
| 40–60 | WL and EN1 high | `/BL` discharges |
| 60 / 70 | EN1 ↓, EN0 ↑ | Qbar precharged; cell re-evaluates through the other pull-down pair and Q falls |
| 160–180, 280–300, 400–420 | WL and EN1 high | In later cycles `/BLb` discharges instead |

Period 120 ns: EN1 high ≈ 10–60, 130–180, 250–300, 370–420 ns; EN0 ≈ 70–120, 190–240, 310–360, 430–480 ns;
WL ≈ 40–90, 160–210, 280–330, 400–450 ns.

**Monte Carlo testbench:** 0–125 ns transient per run, two evaluations; bit = mean `/BL` in the window vs. VDD/2 = 0.45 V;
**Mode 2 window 37–43 ns, Mode 1 window 97–103 ns**. Arrays: 16×16 (256 cells) and 32×64 (2048 cells).

## 7. Cadence Virtuoso server design & simulation directory structure

| Purpose | Path on server |
|---|---|
| All the circuits used in the project | `/home/himani/Work/UMC28_test/cds/project/` |
| All the testing done on the SRAM cell | `/home/himani/Work/UMC28_test/cds/project_testing/sram15T_test/` |
| All the CSV files generated for the MC simulations | `/home/himani/simulation/project_testing/sram15T_test/` |
| Single-cell transient results (ViVA status bar) | `/home/himani/simulation/sram15T_test/spectre/schematic/psf` (dataset `tran-tran`) |

| Item | Value |
|---|---|
| Array | library `project`, cell `16x16array`, view `schematic` |
| Single-cell testbench | library `project_testing`, cell `sram15T_test`, view `schematic` |
| Probed nets (single cell) | `/BL`, `/BLb`, `/EN1`, `/WL`, `/I0/Qbar`, `/I0/Q`, `/EN0` |
| PDK model file | `l28hpc_mm_v1201.lib.scs` |

```text
/home/himani/
├── Work/
│   └── UMC28_test/
│       └── cds/
│           ├── project/                         # all circuits (incl. 16x16array, sram15T, pwrctrl, keyreadout, ...)
│           └── project_testing/
│               └── sram15T_test/                # SRAM cell testbench
└── simulation/
    ├── project_testing/
    │   └── sram15T_test/                        # Monte Carlo CSV exports (mc_*.csv)
    └── sram15T_test/
        └── spectre/
            └── schematic/
                └── psf/                         # single-cell transient results (tran-tran)
```

## 8. Monte Carlo results

All numbers from the executed notebook; 16×16 = 256 cells, 32×64 = 2048 cells.

### 8.1 Logic balance (BL / BLb counts)

| Run | Mode 2 ones | Mode 1 ones |
|---|---|---|
| 0.9 V, −80 mV | 157 / 256 | 150 / 256 |
| 0.9 V, −50 mV | 153 | 147 |
| 0.9 V, +50 mV | 142 | 133 |
| 0.9 V, +80 mV | 140 | 129 |
| 1.0 V, 0 mV | 142 | 135 |
| 1.0 V, −80 / +80 mV | 155 / 134 | 147 / 124 |
| 2048 cells, 0.9 V, −120 / +120 mV | 1226 / 999 | 1205 / 994 |

BLb was the exact complement of BL in every run, so every cell resolved fully in both windows. The tilt acts in
one direction: −tilt (VDDL < VDDR) adds ones, +tilt removes them.

### 8.2 Preselection and self-healing at 27 °C

| VDD | \|Vd\| | Unstable M1 | Repaired | Discarded | Healing eff. | Valid yield |
|---|---|---|---|---|---|---|
| 0.8 V | 50 mV | 12 (4.69 %) | 12 | 0 | 100 % | 100 % |
| 0.8 V | 80 mV | 17 (6.64 %) | 17 | 0 | 100 % | 100 % |
| 0.8 V | 120 mV | 29 (11.33 %) | 29 | 0 | 100 % | 100 % |
| 0.9 V | 50 mV | 14 (5.47 %) | 14 | 0 | 100 % | 100 % |
| 0.9 V | 80 mV | 21 (8.20 %) | 21 | 0 | 100 % | 100 % |
| 0.9 V | 120 mV | 30 (11.72 %) | 29 | 1 | 96.67 % | 99.61 % |
| 1.0 V | 50 mV | 15 (5.86 %) | 14 | 1 | 93.33 % | 99.61 % |
| 1.0 V | 80 mV | 23 (8.98 %) | 22 | 1 | 95.65 % | 99.61 % |
| 1.0 V | 120 mV | 19 (7.42 %) | 19 | 0 | 100 % | 100 % |
| **0.9 V, 32×64** | 120 mV | 211 (10.30 %) | 191 | 20 (0.98 %) | 90.52 % | 99.02 % |


<p align="center"><img src="figures/notebook/nb18_map16_27C_VDD0.9_tilt80.png" width="680"><br>
<em>16×16 map, 0.9 V, ±80 mV: (a) raw, (b) after preselection, (c) after self-healing. Yellow unstable, green repaired, orange discarded, grey stable.</em></p>

<p align="center"><img src="figures/notebook/nb20_map16_27C_VDD0.9_tilt120.png" width="680"><br><em>0.9 V, ±120 mV.</em></p>

<p align="center"><img src="figures/notebook/nb30_map32x64_27C_VDD0.9_tilt120.png" width="760"><br><em>32×64 array, 0.9 V, ±120 mV.</em></p>

Other maps: [0.8 V ±50](figures/notebook/nb25_map16_27C_VDD0.8_tilt50.png) ·
[0.8 V ±80](figures/notebook/nb27_map16_27C_VDD0.8_tilt80.png) · [0.8 V ±120](figures/notebook/nb29_map16_27C_VDD0.8_tilt120.png) ·
[0.9 V ±50](figures/notebook/nb19_map16_27C_VDD0.9_tilt50.png) · [1.0 V ±50](figures/notebook/nb23_map16_27C_VDD1.0_tilt50.png) ·
[1.0 V ±80](figures/notebook/nb21_map16_27C_VDD1.0_tilt80.png) · [1.0 V ±120](figures/notebook/nb22_map16_27C_VDD1.0_tilt120.png).

The unstable fraction rises with Vd (more cells have a mismatch smaller than the tilt). With 10.30 % of cells
unstable in Mode 1 and 11.08 % (227 cells, from the logic counts) in Mode 2 in the 32×64 array, independent modes
would leave about 2048 × 0.103 × 0.111 ≈ 23 cells unstable in both; 20 were discarded. Together with the 48.8 %
distance between the two golden keys, this supports the claim that the two modes give independent bits.

### 8.3 Golden keys (27 °C, 0.9 V, 0 mV)

| Key | Hex | Ones |
|---|---|---|
| Mode 1 (97–103 ns) | `6CD4700EC8EA3BF8C95537B1C4FA3B0E768F2F738BCD9DAB41C9BF3732E5A732` | 139 (54.3 %) |
| Mode 2 (37–43 ns) | `75476AB764D4FB2AC3AF6D5636C75B77D34F2EB34C74ABEFEA6924D6AE735345` | 146 (57.0 %) |

Both keys, and the healed 2028-bit key (54.49 %), lean towards 1. For 2028 bits that is about four standard
deviations from 50 %, so it is a systematic bias (cell asymmetry, BL/BLb loading or the VDD/2 threshold).

### 8.4 BER against supply and tilt

Golden key: 0.9 V, 0 mV; healing chosen at 0.9 V, ±80 mV; BER averaged over +tilt and −tilt (cell 31). All in %.

| VDD | \|Vd\| | Raw M1 | Raw M2 | Self-healed | Healed + V mask | Healed + tilt & V mask | Unstable M1 | Unstable healed |
|---|---|---|---|---|---|---|---|---|
| 0.8 V | 0 | 2.34 | 1.95 | 0.00 | 0.00 | 0.00 | 2.34 | 0.00 |
| 0.8 V | 50 | 2.73 | 1.95 | 0.20 | 0.20 | 0.00 | 4.69 | 0.39 |
| 0.8 V | 80 | 3.32 | 3.32 | 0.78 | 0.78 | 0.00 | 6.64 | 1.56 |
| 0.8 V | 120 | 5.66 | 4.10 | 1.56 | 1.56 | 0.00 | 11.33 | 3.13 |
| 0.9 V | 0 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 0.9 V | 50 | 2.73 | 2.15 | 0.00 | 0.00 | 0.00 | 5.47 | 0.00 |
| 0.9 V | 80 | 4.10 | 3.32 | 0.00* | 0.00 | 0.00 | 8.20 | 0.00 |
| 0.9 V | 120 | 5.86 | 4.49 | 1.76 | 1.76 | 0.00 | 11.72 | 3.52 |
| 1.0 V | 0 | 1.56 | 1.56 | 0.00 | 0.00 | 0.00 | 1.56 | 0.00 |
| 1.0 V | 50 | 2.93 | 1.95 | 0.78 | 0.78 | 0.00 | 5.86 | 1.56 |
| 1.0 V | 80 | 4.49 | 4.10 | 0.98 | 0.98 | 0.00 | 8.98 | 1.95 |
| 1.0 V | 120 | 4.49 | 4.30 | 0.78 | 0.78 | 0.00 | 2.73 | 1.56 |

\* The condition used to choose the healing (zero by construction). The tilt-and-voltage mask is built from the
±80/±120 mV runs and evaluated on them, so its 0 % is also by construction (§9).

<p align="center"><img src="figures/notebook/nb31_ber_unstable_vs_tilt.png" width="700"></p>
<p align="center"><img src="figures/notebook/nb31_ber_vs_vdd.png" width="460"></p>
<p align="center"><img src="figures/notebook/nb31_ber_selfheal_masking_vs_tilt.png" width="760"></p>

* Outside the healing condition, self-healing lowers BER 3–4× (0.9 V ±120 mV: 5.86 → 1.76 %; 0.8 V ±120 mV:
  5.66 → 1.56 %), comparable to the 2.3–2.7× that [1] reports for healing alone after 100 krad(Si).
* With no tilt, the healed key has 0 % BER at 0.8, 0.9 and 1.0 V, against 2.34 % and 1.56 % raw at 0.8 V and 1.0 V.
* At 0.9 V the unstable fraction is exactly twice the BER: an unstable cell matches the golden key in one tilt
  direction and not the other.

### 8.5 Flip direction

<p align="center"><img src="figures/notebook/nb32_directional_flips_tilt_and_vdd_sweeps.png" width="760"></p>

Every flip follows the tilt sign: +tilt gives only 1→0, −tilt only 0→1 (e.g. 0.9 V: +120 mV → 14 flips 1→0,
−120 mV → 16 flips 0→1). Supply alone also biases the cell: at 0.8 V nominal all 6 errors are 0→1, at 1.0 V all 4
are 1→0. A symmetric tilt cannot reproduce the radiation-induced dominance of 1→0 flips reported in [1].

### 8.6 Temperature sweep (VDD = 0.9 V)

Bit classification with ±120 mV at each temperature (cell 33):

| T | Unstable M1 | Repaired | Discarded | Healing eff. | Valid yield | Healed-key HW |
|---|---|---|---|---|---|---|
| −100 °C | 3 (1.17 %) | 3 | 0 | 100 % | 100 % | 55.47 % |
| −40 °C | 15 (5.86 %) | 15 | 0 | 100 % | 100 % | 55.47 % |
| 0 °C | 27 (10.55 %) | 26 | 1 | 96.30 % | 99.61 % | 54.90 % |
| 27 °C | 30 (11.72 %) | 29 | 1 | 96.67 % | 99.61 % | 55.29 % |
| 75 °C | 44 (17.19 %) | 36 | 8 | 81.82 % | 96.88 % | 54.44 % |

BER against each temperature's own nominal key, all available tilts, healing from all tilts (cell 34):

| T | Drift vs. 27 °C (M1) | Mean raw M1 | Mean raw M2 | Mean healed | Raw M1 BLER-128 | Healed BLER-128 | Healed BLER-256 |
|---|---|---|---|---|---|---|---|
| −100 °C | 1.56 % | 0.26 % | 0.72 % | 0.00 % | 28.38 % | 0.00 % | 0.00 % |
| −40 °C | 0.39 % | 1.72 % | 2.11 % | 0.00 % | 89.13 % | 0.00 % | 0.00 % |
| 0 °C | 0.00 % | 3.84 % | 3.12 % | 0.13 % | 99.34 % | 15.36 % | 28.36 % |
| 27 °C | 0.00 % | 4.23 % | 3.32 % | 0.13 % | 99.61 % | 15.36 % | 28.36 % |
| 75 °C | 0.00 % | 6.12 % | 5.79 % | 0.91 % | 99.97 % | 69.03 % | 90.41 % |

BLER = 1 − (1 − BER)^N, independent errors assumed. With preselection the BER over the
remaining valid bits is 0 % at every temperature, by construction.

<p align="center"><img src="figures/notebook/nb33_yield_breakdown_vs_temperature.png" width="560"></p>
<p align="center"><img src="figures/notebook/nb34_ber_bler_vs_temperature.png" width="760"></p>
<p align="center"><img src="figures/notebook/nb34_tilt_ber_vs_temperature.png" width="760"></p>
<p align="center"><img src="figures/notebook/nb33_map16_T75C.png" width="680"><br><em>75 °C: 44 unstable, 36 repaired, 8 discarded.</em></p>

Maps at [−100 °C](figures/notebook/nb33_map16_T-100C.png) · [−40 °C](figures/notebook/nb33_map16_T-40C.png) ·
[0 °C](figures/notebook/nb33_map16_T0C.png) · [27 °C](figures/notebook/nb33_map16_T27C.png).

The same tilt flags 3 cells at −100 °C and 44 at 75 °C: the latch's regenerative gain falls with temperature, so
mismatch margins shrink relative to the tilt. Healing keeps up to 27 °C; at 75 °C 8 cells are unstable in both
modes. The nominal Mode 1 key does not change between 0 °C and 75 °C; it differs from 27 °C in 4 bits at −100 °C.

### 8.7 Comparisons within this work

* **Mode 1 vs. Mode 2.** The two golden keys differ in 48.8 % of positions, and the 2048-cell array has 20 cells
  unstable in both modes against ≈23 expected for independent modes. At 27 °C Mode 2 is never less stable than Mode 1
  (0.9 V ±120 mV: 8.98 % vs. 11.72 % unstable) and its raw BER is at or below Mode 1's at every supply and tilt.
  This reverses when cold: raw Mode 2 BER is higher at −100 °C (0.72 vs. 0.26 %) and −40 °C (2.11 vs. 1.72 %).
  Mode 2 also has more ones (57.0 vs. 54.3 %).
* **Tilt magnitude.** At 0.8 and 0.9 V unstable cells grow roughly linearly with |Vd| (0.9 V: 5.5 → 8.2 → 11.7 %); at
  1.0 V they peak at ±80 mV (8.98 %) and are 7.42 % at ±120 mV. Discards appear only at 0.9 V ±120 mV and 1.0 V ±50/±80 mV,
  so a larger tilt mainly costs healing effort, not yield.
* **Supply vs. temperature.** At ±120 mV the unstable fraction barely moves with supply (11.3 % at 0.8 V, 11.7 % at
  0.9 V) but changes fifteen-fold with temperature (1.2 % at −100 °C → 17.2 % at 75 °C). Temperature is the dominant
  stress, and 75 °C is the only condition with healing efficiency below 90 %. Supply sets the direction of nominal
  errors (0→1 at 0.8 V, 1→0 at 1.0 V); tilt sets the direction of tilt errors.
* **256 vs. 2048 cells** (0.9 V, ±120 mV): 11.72 vs. 10.30 % unstable, 96.7 vs. 90.5 % healed, 0.39 vs. 0.98 %
  discarded. The gaps are within 256-cell sampling error (one cell = 0.39 %; σ ≈ 2 points), so quote the 2048-cell values.
* **Consistency checks.** The 27 °C row of the temperature sweep (cell 33) reproduces the 0.9 V ±120 mV map
  (cell 20) exactly (30 / 29 / 1), and the cell 31 healing map reproduces cell 18 (21 repaired). At 0.9 V the unstable
  fraction is exactly twice the BER at every tilt.
* **In vs. out of sample.** Healing chosen at 0.9 V ±80 mV gives zero BER there and at ±50 mV by construction; elsewhere
  it gives 0.20–1.76 % against 2.73–5.86 % raw (3–4× lower).

### 8.8 Comparison with Chen et al. [1]

Trends, not absolute values: [1] measures 55 nm silicon at 1.2 V with noise and radiation; this is a 28 nm
simulation at 0.9 V without noise, using supply tilt instead of dose.

| Quantity | Chen et al. (silicon) | This work (simulation) | Comparable? |
|---|---|---|---|
| Technology, supply, array | 55 nm, 1.2 V, 64×64, 5 chips | UMC 28 nm, 0.9 V, 16×16 and 32×64 | Setup differs |
| Cell | 15T multimode, 2763 F² | 15T multimode, schematic level | Same topology |
| Tilt generator | 7-bit capacitive DAC | 7-bit capacitive DAC (10–640 fF) | Same |
| Tilt for preselection | Vd = 80 mV | 50, 80, 120 mV | Yes at 80 mV |
| Native BER at nominal, raw / healed | 0.863 % / 0.136 % | 0 % / 0 % (no noise; golden key is this run) | No |
| Unstable bits at nominal, raw / healed | 5.102 % / 1.635 % (1000 reads) | 8.20 % / 0 % (flagged by ±80 mV tilt) | Different definitions |
| Worst BER over supply, raw / healed | 3.11 % / 1.23 % (1.08–1.32 V) | 2.34 % / 0 % (0.8–1.0 V, no tilt) | Trend yes |
| Worst BER over temperature, raw / healed | 3.76 % / 0.72 % (−40 to 125 °C) | 6.12 % / 0.91 % mean tilt BER at 75 °C; nominal drift ≤ 1.56 % | Trend yes |
| Healing-only BER reduction | 2.7× / 2.3× after 100 krad(Si) | 3.3× (0.9 V), 3.6× (0.8 V) at ±120 mV | Same order |
| Unstable bits at max. stress, raw / healed | 14.62 % / 4.675 % (Chip 1, 100 krad) | 11.72 % / 3.52 % (0.9 V, ±120 mV) | Proxy only |
| Bits discarded after healing | not stated | 0.98 % (2048 cells, ±120 mV); 3.1 % at 75 °C | n/a |
| Masking for zero BER | 25–32 % masked | 0 % with tilt + V mask, in sample; ratio not reported | No |
| Final BER, heal + pre-irradiation masks | 0.0168 % / 0.0183 % | — | Not studied |
| Dominant flip direction | 1→0 (4.26 vs. 1.68 %, Chip 1) | follows tilt sign; symmetric overall | No (symmetric stress) |
| Two modes independent | claimed, not quantified | inter-mode HD 48.8 %; 20 vs. 23 discards | Supports claim |
| Uniformity / uniqueness | inter-die HD 0.494 (healed 0.4835) | HW 54–57 %; one die | Partly |
| Randomness | NIST SP 800-22: 10/10 passed | not tested | No |
| Power, area | 0.20 µW/bit static; 140 fJ/b; 2763 F² | not measured | No |

**Agreements:** mode switching heals most tilt-flagged cells (90–100 % here; [1] lowers nominal unstable bits from
5.10 to 1.64 %), and healing cuts stressed BER 2–4× in both. In both, healing alone is not enough for a key:
healed 128-bit BLER here is 15 % at 27 °C and 69 % at 75 °C, and [1] needs pre-irradiation masks plus ECC for 0.018 %.
**Differences** come from the setup: no temporal noise (so no native BER and no growth with reads, [1] Fig. 11), a
symmetric tilt (so no 1→0 bias), and one die without layout (so no uniqueness, randomness, power or area).

### 8.9 All notebook figures

Every plot from the notebook, in cell order:

| Cell | Figure |
|---|---|
| 18 — 0.9 V, ±80 mV | <img src="figures/notebook/nb18_map16_27C_VDD0.9_tilt80.png" width="520"> |
| 19 — 0.9 V, ±50 mV | <img src="figures/notebook/nb19_map16_27C_VDD0.9_tilt50.png" width="520"> |
| 20 — 0.9 V, ±120 mV | <img src="figures/notebook/nb20_map16_27C_VDD0.9_tilt120.png" width="520"> |
| 21 — 1.0 V, ±80 mV | <img src="figures/notebook/nb21_map16_27C_VDD1.0_tilt80.png" width="520"> |
| 22 — 1.0 V, ±120 mV | <img src="figures/notebook/nb22_map16_27C_VDD1.0_tilt120.png" width="520"> |
| 23 — 1.0 V, ±50 mV | <img src="figures/notebook/nb23_map16_27C_VDD1.0_tilt50.png" width="520"> |
| 25 — 0.8 V, ±50 mV | <img src="figures/notebook/nb25_map16_27C_VDD0.8_tilt50.png" width="520"> |
| 27 — 0.8 V, ±80 mV | <img src="figures/notebook/nb27_map16_27C_VDD0.8_tilt80.png" width="520"> |
| 29 — 0.8 V, ±120 mV | <img src="figures/notebook/nb29_map16_27C_VDD0.8_tilt120.png" width="520"> |
| 30 — 32×64, 0.9 V, ±120 mV | <img src="figures/notebook/nb30_map32x64_27C_VDD0.9_tilt120.png" width="520"> |
| 31 — healing map, 0.9 V, ±80 mV | <img src="figures/notebook/nb31_healing_map_VDD0.9_tilt80.png" width="520"> |
| 31 — BER and unstable bits vs. tilt | <img src="figures/notebook/nb31_ber_unstable_vs_tilt.png" width="520"> |
| 31 — BER vs. VDD | <img src="figures/notebook/nb31_ber_vs_vdd.png" width="400"> |
| 31 — flip direction, symmetric tilt | <img src="figures/notebook/nb31_flip_direction_symmetric_tilt.png" width="400"> |
| 31 — healing and masking vs. tilt | <img src="figures/notebook/nb31_ber_selfheal_masking_vs_tilt.png" width="520"> |
| 32 — directional flips, tilt and VDD sweeps | <img src="figures/notebook/nb32_directional_flips_tilt_and_vdd_sweeps.png" width="520"> |
| 33 — −100 °C | <img src="figures/notebook/nb33_map16_T-100C.png" width="520"> |
| 33 — −40 °C | <img src="figures/notebook/nb33_map16_T-40C.png" width="520"> |
| 33 — 0 °C | <img src="figures/notebook/nb33_map16_T0C.png" width="520"> |
| 33 — 27 °C | <img src="figures/notebook/nb33_map16_T27C.png" width="520"> |
| 33 — 75 °C | <img src="figures/notebook/nb33_map16_T75C.png" width="520"> |
| 33 — yield breakdown vs. temperature | <img src="figures/notebook/nb33_yield_breakdown_vs_temperature.png" width="460"> |
| 34 — BER and BLER vs. temperature | <img src="figures/notebook/nb34_ber_bler_vs_temperature.png" width="520"> |
| 34 — per-tilt BER vs. temperature | <img src="figures/notebook/nb34_tilt_ber_vs_temperature.png" width="520"> |

## 9. Limitations and future work

* Each Monte Carlo condition is one deterministic transient: no temporal noise, so the nominal BER is 0 by definition.
  Transient-noise runs and temporal majority voting would add the noise-driven errors measured in [1].
* Supply tilt is an enrollment stress, not a radiation model.
* One array instance: inter-chip Hamming distance, autocorrelation and NIST tests need several MC chip instances.
* Masks evaluated on the conditions they were built from give 0 % by construction; hold out a condition and report the masking ratio.
* Planned [2, 3]: uniqueness across MC chip instances, process corners and wider PVT, Vd sweep vs. discarded bits,
  Vth-shift emulation of total ionizing dose, bias-aware tilt.

## 10. Repository layout and how to run

```text
16x16-sram-puf-repo/
├── README.md
├── requirements.txt
├── .gitignore                         # excludes mc_*.csv, __pycache__, .ipynb_checkpoints
├── data/raw/                          # put the exported mc_*.csv here (not tracked)
├── docs/
│   ├── schematics/                    # architecture, 15T cell, 16x16 array (+4 zooms), 2x2 test array (Cadence)
│   ├── peripherals/                   # pwrctrl DAC, key readout, stability, DFF, WL drivers, decoders,
│   │                                  # precharge, sense amp, write driver, mode_wl_driver (Cadence)
│   ├── simulations/                   # block, 2x2, 16x16 and Monte Carlo setup waveforms (Cadence)
│   ├── timing/                        # single_cell_timing_diagram.png
│   ├── reference_paper/               # two figures of [1] used for comparison (cited)
│   └── server/                        # server-path screenshot
├── notebooks/VLSI_project_SRAM_PUF.ipynb    # notebook, all outputs preserved
├── scripts/
│   ├── 01_logic_counts_256.py         # notebook cells 1-15
│   ├── 02_logic_counts_2048.py        # cell 17
│   ├── 03_preselection_map_16x16.py   # cells 18-29 (any VDD / tilt via arguments)
│   ├── 04_preselection_map_32x64.py   # cell 30
│   ├── 05_golden_key_ber_masking_summary.py   # cell 31
│   ├── 06_directional_flips.py        # cell 32
│   ├── 07_temperature_maps_and_yield.py       # cell 33
│   ├── 08_temperature_ber_bler.py     # cell 34
│   ├── make_flow_diagram.py           # self-healing flow figure
│   └── run_all.sh
├── figures/
│   ├── notebook/                      # all 24 notebook figures
│   └── selfhealing_flow.png
├── results/                           # 8 summary CSVs transcribed from the notebook outputs
└── report/                            # IEEEtran LaTeX source, img/, PDF
```

```bash
pip install -r requirements.txt
cp /path/to/mc_*.csv data/raw/
bash scripts/run_all.sh
# or one analysis, e.g.
python scripts/03_preselection_map_16x16.py --data data/raw \
       --nominal mc_256_0.8_vdd.csv --plus mc_256_0.8_vdd+120.csv --minus mc_256_0.8_vdd-120.csv
```

The report rebuilds with `pdflatex` in `report/` (or on Overleaf; `IEEEtran.cls` is included).

## 11. References

1. Z. Chen, W. Yang, J. Chen, Z. Wang, and D. Ding, "Improving radiation reliability of SRAM-based physical
   unclonable function with self-healing and pre-irradiation masking techniques," *IEEE Trans. VLSI Syst.*,
   vol. 32, no. 2, pp. 372–381, Feb. 2024, doi: 10.1109/TVLSI.2023.3332010.
2. H. Goel and V. Goel, "Improving radiation reliability of SRAM-based PUF with self-healing and pre-irradiation
   masking techniques," EE 617 paper presentation (Phase 0), IIT Gandhinagar, Oct. 2026.
3. H. Goel and V. Goel, "16×16 multimode SRAM PUF in UMC 28 nm: architecture, schematics and simulations,"
   EE 617 project presentation (Phase 2), IIT Gandhinagar, Oct. 2026.
