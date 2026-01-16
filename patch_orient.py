import re
from typing import List
p = 'orient_sd.py'
with open(p, 'r', encoding='utf-8') as f:
    src = f.read()

# 1) Add `chains` field to Group dataclass
src, n1 = re.subn(
    r"(merged_from: List\[int\] = field\(default_factory=list\).*?\n)",
    r"\1    chains: List[List[int]] = field(default_factory=list)  # original series chains for parallel merge\n",
    src,
    flags=re.DOTALL,
)

# 2) Replace build_series_groups with new implementation
new_build = '''def build_series_groups(devs: List[Device], power_nets: Set[str], shared_nets: Optional[Set[str]] = None) -> Tuple[List[Group], Dict[int, int], List[str]]:
    """
    Build pure-series groups:
      - Union only via DS nets with degree==2, excluding power nets and shared_nets as linking points.
      - Endpoints arise naturally from degrees.
      - Extract an ordered chain within each component for orientation.
      - Merge parallel chains by unordered external ends to reduce graph complexity; device orientation remains per-chain.
    Returns:
      groups list, device_id -> group_id mapping, merge_notes
    """
    notes: List[str] = []
    if shared_nets is None:
        shared_nets = set()
    n = len(devs)
    if n == 0:
        return [], {}, notes

    # DS net -> device indices for linking (exclude power and shared nets)
    net_to_devs_link: Dict[str, List[int]] = defaultdict(list)
    for i, d in enumerate(devs):
        if d.d not in power_nets and d.d not in shared_nets:
            net_to_devs_link[d.d].append(i)
        if d.s not in power_nets and d.s not in shared_nets:
            net_to_devs_link[d.s].append(i)

    uf = UnionFind(n)
    # Link only on nets with exactly two devices
    for net, ids in net_to_devs_link.items():
        if len(ids) == 2:
            uf.union(ids[0], ids[1])

    comp: Dict[int, List[int]] = defaultdict(list)
    for i in range(n):
        comp[uf.find(i)].append(i)

    groups_raw: List[Group] = []
    dev_to_group_raw: Dict[int, int] = {}
    gid = 0

    for _, ids in comp.items():
        # Build DS incidence within this component (include power/shared to allow endpoints)
        ds_count: Dict[str, int] = defaultdict(int)
        net_to_devs_all: Dict[str, List[int]] = defaultdict(list)
        for i in ids:
            d = devs[i]
            for net in (d.d, d.s):
                ds_count[net] += 1
                net_to_devs_all[net].append(i)

        # Natural endpoints selection
        degree1_nonpower = [n for n, cnt in ds_count.items() if cnt == 1 and n not in power_nets]
        power_present = [n for n in ds_count.keys() if n in power_nets]

        if len(degree1_nonpower) >= 2:
            ends = [degree1_nonpower[0], degree1_nonpower[1]]
        elif len(degree1_nonpower) == 1 and power_present:
            ends = [degree1_nonpower[0], power_present[0]]
        elif len(power_present) >= 2:
            ends = [power_present[0], power_present[1]]
        else:
            nets_all = list(ds_count.keys())
            if len(nets_all) >= 2:
                a = nets_all[0]
                b = next((x for x in nets_all[1:] if x != a), a)
                ends = [a, b]
            elif len(nets_all) == 1:
                ends = [nets_all[0], nets_all[0]]
            else:
                ends = ["", ""]

        # Build an ordered chain (device order) starting from ends[0]
        order: List[int] = []
        visited: Set[int] = set()
        current_net = ends[0]
        steps = 0
        max_steps = len(ids) + 5

        while steps < max_steps and len(visited) < len(ids):
            cand = [i for i in net_to_devs_all.get(current_net, []) if i in ids and i not in visited]
            if not cand:
                remaining = [i for i in ids if i not in visited]
                if not remaining:
                    break
                i0 = remaining[0]
                d0 = devs[i0]
                current_net = d0.d
                continue
            i = cand[0]
            order.append(i)
            visited.add(i)
            d = devs[i]
            next_net = d.s if d.d == current_net else d.d
            current_net = next_net
            steps += 1

        # Internal nets: degree==2 and not power
        internal_nets: Set[str] = set(n for n, cnt in ds_count.items() if cnt == 2 and n not in power_nets)

        g = Group(
            id=gid,
            dev_ids=list(ids),
            ext_nets=(ends[0], ends[1]),
            _internal_nets=internal_nets,
            order=order,
            merged_from=[gid],
            chains=[order],
        )
        groups_raw.append(g)
        for i in ids:
            dev_to_group_raw[i] = gid
        gid += 1

    # Merge parallel groups by unordered end-pairs
    key_to_groups: Dict[frozenset, List[Group]] = defaultdict(list)
    for g in groups_raw:
        a, b = g.ext_nets
        key = frozenset((a, b))
        key_to_groups[key].append(g)

    groups: List[Group] = []
    dev_to_group: Dict[int, int] = {}
    new_gid = 0
    for key, glist in key_to_groups.items():
        if len(glist) == 1:
            g = glist[0]
            g.id = new_gid
            groups.append(g)
            for i in g.dev_ids:
                dev_to_group[i] = new_gid
            new_gid += 1
        else:
            # merge only for compute reduction; keep per-branch chains for later orientation
            all_devs: List[int] = []
            internal_union: Set[str] = set()
            merged_from: List[int] = []
            merged_chains: List[List[int]] = []
            for g in glist:
                all_devs.extend(g.dev_ids)
                internal_union |= g._internal_nets
                merged_from.extend(g.merged_from if g.merged_from else [g.id])
                # Preserve original series chain(s)
                if g.chains:
                    merged_chains.extend([list(c) for c in g.chains])
                elif g.order:
                    merged_chains.append(list(g.order))
            # choose a stable ext pair from the first group
            a, b = glist[0].ext_nets
            mg = Group(
                id=new_gid,
                dev_ids=all_devs,
                ext_nets=(a, b),
                _internal_nets=internal_union,
                order=[],
                merged_from=merged_from,
                chains=merged_chains,
            )
            groups.append(mg)
            for i in all_devs:
                dev_to_group[i] = new_gid
            notes.append(f"merged {len(glist)} parallel groups into one (unordered): ends=({a}, {b}), devs={len(all_devs)}")
            new_gid += 1

    return groups, dev_to_group, notes
'''

pattern_build = r"def build_series_groups\([\s\S]*?\)(?=\n\s*def find_shared_ds_nets\()"
src, n2 = re.subn(pattern_build, new_build, src)

# 3) Replace orient_chain_devices_in_group with chain-based orientation
new_orient = '''def orient_chain_devices_in_group(group: Group,
                                  devs: List[Device],
                                  src_net: str,
                                  dst_net: str) -> Dict[str, Tuple[str, str]]:
    """
    Orient devices inside a group.
    - For merged-parallel groups, keep per-branch chains and orient each chain independently along src->dst.
    - For single series group, orient along its order.
    """
    oriented: Dict[str, Tuple[str, str]] = {}

    def set_step(i: int, u: str, v: str):
        d = devs[i]
        # newS should be u, newD should be v
        oriented[d.name] = (v, u)

    def orient_series(order: List[int]):
        if not order:
            return
        ord2 = list(order)
        def touches(i: int, net: str) -> bool:
            dd = devs[i]
            return (dd.d == net) or (dd.s == net)
        if ord2 and not touches(ord2[0], src_net) and (ord2 and touches(ord2[-1], src_net)):
            ord2 = list(reversed(ord2))
        cur = src_net
        for i in ord2:
            d = devs[i]
            if d.d == cur:
                nxt = d.s
            elif d.s == cur:
                nxt = d.d
            else:
                if d.d == dst_net:
                    nxt = d.s
                    cur = d.d
                else:
                    nxt = d.d
                    cur = d.s
            set_step(i, cur, nxt)
            cur = nxt

    if getattr(group, 'chains', None):
        for ch in group.chains:
            orient_series(ch)
        return oriented

    if group.order:
        orient_series(group.order)
        return oriented

    # Fallback: stable per-device orientation when no chain info is available
    for i in group.dev_ids:
        d = devs[i]
        if d.d == src_net or d.s == src_net:
            other = d.s if d.d == src_net else d.d
            set_step(i, src_net, other)
        elif d.d == dst_net or d.s == dst_net:
            other = d.s if d.d == dst_net else d.d
            set_step(i, other, dst_net)
        else:
            # Arbitrary but stable
            set_step(i, d.s, d.d)
    return oriented
'''

pattern_orient = r"def orient_chain_devices_in_group\([\s\S]*?\)(?=\n\s*def orient_component\()"
src, n3 = re.subn(pattern_orient, new_orient, src)

with open(p, 'w', encoding='utf-8') as f:
    f.write(src)

print('patched: Group.chains added:', n1 > 0, ' build_series_groups:', n2, ' orient_chain_devices_in_group:', n3)
