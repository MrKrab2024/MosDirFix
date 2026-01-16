# MosDirFix

Source/Drain orientation preprocessor for SPICE std-cell decks. It analyzes each subcircuit, infers MOS source/drain directions (PMOS toward VDD, NMOS toward VSS, flowing toward shared functional nets), and rewrites only the D/S fields of MOS lines. Tail parameters (e.g. w/width/l, etc.) are preserved verbatim.

## Features
- Robust parsing: case-insensitive `.SUBCKT`/`.ENDS`/`M` lines; ignores comments; only the first 6 MOS tokens are parsed (`Mname D G S B model`), tail params kept as-is.
- Series grouping via DS nets with degree==2 excluding power and shared nets; endpoints derived from degrees.
- Parallel merge by unordered end-pairs solely to reduce graph size; device orientation remains per original series chain.
- Orientation by components and path-confirmation: start from power net (PMOS: VDD, NMOS: VSS) toward shared DS nets seen on both sides.
- Transmission gate groups (endpoints both shared and present on both sides) are skipped.
- Detailed JSON report and a concise text log.

## Repository Layout
- `orient_sd.py` — main orientation tool (MIT Licensed)
- `randomize_mos_ds.py` — utility to create randomized D/S test netlists
- `AsAp7.sp` — example input deck
- `out/` — outputs: oriented netlists, reports, logs
- `rand/` — example randomized input(s)

## Requirements
- Python 3.8+; standard library only (no external deps)

## Usage
### 1) Orient a netlist
```bash
python orient_sd.py --sp AsAp7.sp \
  --vdd VDD --vss VSS \
  --out_sp out/oriented.sp \
  --report_json out/orient_report.json \
  --log out/orient_log.txt
```
Notes:
- `--cells` can restrict to specific subcircuits (one name per line).
- Only D/S are rewritten; gate/bulk/model/tail params are preserved.

### 2) Generate a randomized D/S netlist (for testing)
```bash
python randomize_mos_ds.py --in AsAp7.sp --out out/randomized_ds.sp --prob 0.5 --seed 42
```
- Randomly swaps D/S per MOS with probability `--prob`; tail params untouched.

### 3) Re-orient a randomized netlist
```bash
python orient_sd.py --sp out/randomized_ds.sp --out_sp out/oriented_from_rand.sp \
  --report_json out/orient_from_rand_report.json --log out/orient_from_rand_log.txt
```

## Algorithm Highlights
- Build pure-series chains using DS nets of degree 2; ignore power nets (VDD/VSS) and discovered shared nets as linking points.
- Shared nets are DS nets common to PMOS and NMOS sides (excluding power).
- Merge parallel chains whose unordered endpoint set matches; store each original chain (`chains`) and orient chains independently along confirmed net-paths.
- BFS enumerates net-paths from the start power net to any shared net; each path confirms edge directions; conflicts are logged.

## Outputs
- `--out_sp`: oriented SPICE; only MOS D/S possibly swapped.
- `--report_json`: per-cell/per-side details: oriented/ambiguous counts, sequences, notes, TG-skipped devices, series groups (pre/post), components.
- `--log`: compact summary of processed/skipped cells.

## Limitations
- Device type detection relies on model name containing `pmos`/`nmos`.
- TG-like structures are skipped intentionally.
- If a component has no shared net or no path to it, some devices may remain ambiguous (left unchanged).

## License
MIT — see header in `orient_sd.py`.
