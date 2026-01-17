# MosDirFix

Source/Drain orientation preprocessor for SPICE std-cell decks. It analyzes each subcircuit, infers MOS source/drain directions (PMOS toward VDD, NMOS toward VSS, flowing toward shared functional nets), and rewrites only the D/S fields of MOS lines. Tail parameters (e.g. w/width/l, etc.) are preserved verbatim.

- Default branch: `main`
- Generated artifacts are not tracked (see `.gitignore`); run commands locally to reproduce outputs.

## Key Files
- `orient_sd.py` — main orientation tool (MIT licensed)
- `randomize_mos_ds.py` — utility to create randomized D/S test netlists
- `AsAp7.sp` — example input deck
- `README.md`, `LICENSE`, `.gitignore`

## Requirements
- Python 3.8+; standard library only (no external dependencies)

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
- `.SUBCKT` / `.ENDS` / `M` matching is case-insensitive; leading whitespace is allowed.
- Only the first 6 MOS tokens (`Mname D G S B model`) are parsed; the tail params are preserved as-is.
- `--cells` can restrict to specific subcircuits (one name per line).

### 2) Generate a randomized D/S netlist (for testing)
```bash
python randomize_mos_ds.py --in AsAp7.sp --out out/randomized_ds.sp --prob 0.5 --seed 42
```
- Per MOS, swaps D/S with probability `--prob`; tail params untouched.

### 3) Re-orient a randomized netlist
```bash
python orient_sd.py --sp out/randomized_ds.sp --out_sp out/oriented_from_rand.sp \
  --report_json out/orient_from_rand_report.json --log out/orient_from_rand_log.txt
```

## Algorithm Highlights
- Build pure-series chains using DS nets of degree 2; power nets (VDD/VSS) and discovered shared nets are excluded as linking points.
- Shared nets = DS nets common to PMOS and NMOS sides (excluding power nets).
- Merge parallel chains when the unordered endpoint set matches; this reduces graph size only. Each original series chain is preserved (`chains`) and oriented independently.
- Orientation by components: from the start power net (PMOS: VDD, NMOS: VSS) toward shared nets; confirm edge directions along discovered paths; log conflicts.
- Transmission-gate-like groups whose both ends are shared (and appear on both sides) are skipped.

## Outputs
- `--out_sp`: oriented SPICE; only MOS D/S may change.
- `--report_json`: per-cell/per-side details — oriented/ambiguous counts, sequences, notes, TG-skipped devices, series groups (pre/post), components.
- `--log`: compact summary of processed/skipped cells.

## Repository Policy
- Artifacts under `out/` and test inputs under `rand/` are generated locally and ignored by Git.
- The repo keeps only key scripts and sample input; re-run the commands above to regenerate outputs.

## License
MIT — see header in `orient_sd.py` and `LICENSE`.


### Advanced options (feature/robustness)\n- --vdd_list / --vss_list: extra power/ground aliases (comma-separated)\n- --max_path_len: limit BFS path length (edges); 0 = unlimited\n- --stop_after_first_shared: early-stop after reaching any shared net\n- --preserve_ws: try preserving whitespace when rewriting MOS lines (no continuations)\n
