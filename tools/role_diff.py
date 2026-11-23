"""Whole-row comparison of candidate rows against every vanilla row of a role (project working method).

  python tools/role_diff.py <Table> <role-regex> <candidate-id> [<candidate-id> ...]
  e.g.  python tools/role_diff.py GOP_Battle_UnitParam "BATTLE_UNITPARAM_CH_P0(0[1-9]|[12][0-9]|30)$" BATTLE_UNITPARAM_CH_P042

Reports, per candidate:
  MUST  - fields where ALL role rows share one value and the candidate differs (strong signal)
  RARE  - candidate value used by no role row, though role rows vary (weaker signal)
Ignores id-like fields (SelfId, names/text ids) unless --all. Reads data/tables/<Table>.json.
"""
import json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ID_LIKE = re.compile(r'(SelfId|Name|Help|Text|Id\d?$|^Sprite|Effect(ID|Socket)$|SEID|AttackParam$|CorrectParam|Growth|UnitClass|EquippedWeapon|AITag|SortNumber)', re.I)


def role_diff(rows, role_ids, cand, all_fields=False):
    must, rare = [], []
    for f, v in rows[cand].items():
        if not all_fields and ID_LIKE.search(f): continue
        vals = [rows[r][f] for r in role_ids]
        sv = {json.dumps(x, sort_keys=True, default=str) for x in vals}
        cv = json.dumps(v, sort_keys=True, default=str)
        if cv in sv: continue
        (must if len(sv) == 1 else rare).append((f, v, sorted(sv)[:4]))
    return must, rare


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if a != '--all']
    table, role_re, cands = args[0], re.compile(args[1]), args[2:]
    rows = json.load(open(os.path.join(ROOT, 'data', 'tables', table + '.json'), encoding='utf-8'))
    role = [k for k in rows if role_re.search(k)]
    print(f'{table}: role = {len(role)} rows matching {args[1]}')
    for c in cands:
        must, rare = role_diff(rows, role, c, '--all' in sys.argv)
        print(f'== {c}')
        for f, v, s in must: print(f'   MUST  {f}: candidate={v}  all role rows={s[0]}')
        for f, v, s in rare: print(f'   rare  {f}: candidate={v}  role values e.g. {s}')
        if not must and not rare: print('   (no differences)')
