"""Vanilla kit vs recruit kit: does every move a character has in the base game appear in our recruit?

    python tools/kit_gaps.py                 # all recruits (mods/recruit_*_full/spec.json)
    python tools/kit_gaps.py N203 N102       # some

A character's vanilla kit = every BATTLE_ABILITY_* on the class rows (GOP_Battle_Job) of every battle param
they use in the base game (data/npc_reference.json), on those param rows themselves, on their weapons'
`Ability`, and on any job row named for them (`_<id>_`). The recruit kit = learn tables + tree nodes +
weapon skill in spec.json; an own copy counts as its source (`copy_from`). A deliberate exception is
recorded in the spec as `vanilla_covered: {ability: reason}` (e.g. the stronger II version unlocked by a tree node).
Rule (user, 2026-11-17): every vanilla move is in the kit under its own name unless there's a good reason.
Exit code 1 if anything is missing or renamed.
"""
import glob, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = lambda n: json.load(open(os.path.join(ROOT, 'data', 'tables', n + '.json'), encoding='utf-8'))


def load():
    return {'ab': T('GOP_Battle_Ability'), 'jb': T('GOP_Battle_Job'), 'up': T('GOP_Battle_UnitParam'),
            'wp': T('GOP_Battle_Weapon'),
            'ref': {c['character_id'][8:]: c for c in json.load(open(os.path.join(ROOT, 'data', 'npc_reference.json'),
                                                                      encoding='utf-8'))['characters']}}


def vanilla_kit(cid, D):
    """{ability_id: sorted list of where it comes from}."""
    src = {}
    def add(a, where):
        if a in D['ab']: src.setdefault(a, set()).add(where)
    def job(j):
        for x in D['jb'][j].values():
            if isinstance(x, str) and x.startswith('BATTLE_ABILITY_'): add(x, j[10:])
    for p in [p['id'] for p in D['ref'][cid]['battle_params']]:
        for f, v in D['up'].get(p, {}).items():
            if not isinstance(v, str): continue
            if v.startswith('BATTLE_ABILITY_'): add(v, p[20:])
            if v in D['jb']: job(v)
            if v in D['wp'] and D['wp'][v].get('Ability', 'None') != 'None': add(D['wp'][v]['Ability'], 'weapon ' + v[14:])
    for k in D['jb']:
        if re.search(rf'_{cid}(_|$)', k): job(k)
    return {a: sorted(w) for a, w in src.items()}


def recruit_kit(spec):
    """{ability_id (vanilla source for own copies): (how, our id, our name or None)}."""
    own = {o['id']: o for o in spec.get('own_abilities', [])}
    used = [a for c in spec['classes'] for _, a in c['learn']]
    used += [n for t in spec['tree'] for n in t['nodes'] if isinstance(n, str)]
    used += [rk['weapon_skill'] for rk in spec['weapon']['ranks'] if rk.get('weapon_skill')]
    kit = {}
    for u in used:
        if u in own: kit.setdefault(own[u]['copy_from'], ('own copy', u, own[u].get('name')))
        else: kit.setdefault(u, ('as is', u, None))
    return kit


def gaps(cid, spec, D):
    """[(ability_id, status, where)] for every vanilla-kit move; status is kept / own copy / RENAMED / MISSING."""
    have = recruit_kit(spec); out = []
    for a, where in sorted(vanilla_kit(cid, D).items()):
        if a in spec.get('vanilla_covered', {}): st = 'covered: ' + spec['vanilla_covered'][a]
        elif a not in have: st = 'MISSING'
        elif have[a][2]: st = f'RENAMED to "{have[a][2]}"'
        else: st = 'kept' if have[a][0] == 'as is' else 'kept (own copy)'
        out.append((a, st, where))
    return out


def specs():
    for p in sorted(glob.glob(os.path.join(ROOT, 'mods', 'recruit_*_full', 'spec.json'))):
        yield json.load(open(p, encoding='utf-8'))


if __name__ == '__main__':
    D = load(); want = set(sys.argv[1:]); bad = 0
    for s in specs():
        if want and s['id'] not in want: continue
        print(f"== {D['ref'][s['id']]['name']} ({s['id']})")
        for a, st, where in gaps(s['id'], s, D):
            bad += st.startswith(('MISSING', 'RENAMED'))
            print(f'   {st:28} {a[15:]:34} from {", ".join(where)}')
    print(f'{bad} missing/renamed')
    sys.exit(1 if bad else 0)
