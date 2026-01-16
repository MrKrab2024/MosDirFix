#!/usr/bin/env python3
# Randomly swap MOS D/S in a SPICE netlist (keeps only the first six tokens editable)
import argparse, os, re, random

# Matches: M<name> D G S B model [params...]
M_RE = re.compile(r"^\s*M(\S*)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)(.*)$", re.IGNORECASE)

def main():
    ap = argparse.ArgumentParser(description="Randomly swap MOS D/S in a SPICE netlist")
    ap.add_argument("--in", dest="inp", required=True, help="Input SPICE path (e.g., AsAp7.sp)")
    ap.add_argument("--out", dest="outp", required=True, help="Output randomized SPICE path")
    ap.add_argument("--prob", type=float, default=0.5, help="Probability to swap D/S per MOS [0..1], default 0.5")
    ap.add_argument("--seed", type=int, default=None, help="Optional RNG seed for reproducibility")
    args = ap.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    out_dir = os.path.dirname(args.outp)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    swapped = kept = 0
    with open(args.inp, "r", encoding="utf-8") as fin, open(args.outp, "w", encoding="utf-8") as fout:
        for raw in fin:
            line = raw.rstrip("\n")
            s = line.strip()
            m = M_RE.match(s)
            if m:
                mname = "M" + m.group(1)
                d, g, s_net, b = m.group(2), m.group(3), m.group(4), m.group(5)
                model, params = m.group(6), m.group(7)
                if random.random() < args.prob:
                    newD, newS = s_net, d
                    swapped += 1
                else:
                    newD, newS = d, s_net
                    kept += 1
                out = f"{mname} {newD} {g} {newS} {b} {model}{params}"
                fout.write(out + "\n")
            else:
                fout.write(line + "\n")
    print(f"[randomize_mos_ds] swapped={swapped}, kept={kept}, total={swapped+kept}")

if __name__ == "__main__":
    main()
