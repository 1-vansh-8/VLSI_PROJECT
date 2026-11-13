#!/usr/bin/env bash
# Re-run the notebook analysis as scripts. Put the raw mc_*.csv files in data/raw/ first.
# Outputs (CSVs and PNGs) are written into data/raw/, exactly as the notebook wrote them into its working folder.
set -e
cd "$(dirname "$0")/.."
D=data/raw
python scripts/01_logic_counts_256.py --data $D
python scripts/02_logic_counts_2048.py --data $D
for V in 0.8 0.9 1.0; do for T in 50 80 120; do
  python scripts/03_preselection_map_16x16.py --data $D \
    --nominal mc_256_${V}_vdd.csv --plus mc_256_${V}_vdd+${T}.csv --minus mc_256_${V}_vdd-${T}.csv
  mv $D/puf_fig10_mapping.png $D/map16_27C_VDD${V}_tilt${T}.png
done; done
python scripts/04_preselection_map_32x64.py --data $D
python scripts/05_golden_key_ber_masking_summary.py --data $D
python scripts/06_directional_flips.py --data $D
python scripts/07_temperature_maps_and_yield.py --data $D
python scripts/08_temperature_ber_bler.py --data $D
# flow diagram (no raw data needed):

python scripts/make_flow_diagram.py
