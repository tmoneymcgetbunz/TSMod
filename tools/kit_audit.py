"""Whole-row audit of every NEW row in a build against all vanilla rows of its role (project working method).

  python tools/kit_audit.py <build_out_dir>        (the --out dir of build_mod.py, containing stage/)

Roles:
  UnitParam  *_PARTY            vs the 30 recruit params  BATTLE_UNITPARAM_CH_P001..P030
  Job        new class rows     vs every recruit class    BATTLE_JOB_CH_P0xx_*
  Weapon     rank n             vs recruit rank-n weapons
  Tree       rank n             vs recruit rank-n trees
  AttackParam weapon attack     vs recruit weapon attack params
  Ability    weapon skill       vs the vanilla weapon skills (bIsWeaponAbility)
             tree node          vs vanilla rows of the same family prefix (DAMAGE_UP, TP_REDUCTION, ...)
             command/passive    vs abilities learned by recruit classes, same eAbilityType
Prints MUST (all role rows agree, ours differs) and rare. Id-like fields are skipped (see role_diff.ID_LIKE).
"""
import glob, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dtparse
from role_diff import role_diff

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REC = re.compile(r'_P0(0[1-9]|[12][0-9]|30)')
LINKS = re.compile(r'^(JobType|LearnableAbility|RankUpWeapon|RankDownWeapon|WeaponAbilityTree|Ability$|AbilityId|FNameParam)')
FAMILIES = ('ABILITY_ABILITY_DAMAGE_UP', 'ABILITY_ABILITY_EFFECT_UP', 'ABILITY_ABILITY_EXTENSION', 'ABILITY_ABILITY_RANGE_UP',
            'ABILITY_TP_REDUCTION', 'ABILITY_WEAPON_BONUS', 'ABILITY_WEAPON_POWER_CORRECTION')


def vanilla(t):
    return json.load(open(os.path.join(ROOT, 'data', 'tables', t + '.json'), encoding='utf-8'))


def staged(out, t):
    f = glob.glob(os.path.join(out, 'stage', '**', t + '.uasset'), recursive=True)
    if not f: return None
    rows = dtparse.parse_bytes(open(f[0], 'rb').read(), open(f[0][:-7] + '.uexp', 'rb').read())[1]
    return {k: {f: (p['v'] if isinstance(p, dict) and 'v' in p else p) for f, p in r.items()} for k, r in rows.items()}


def report(table, cand, role, rows):
    must, rare = role_diff(rows, role, cand)
    must = [x for x in must if not LINKS.match(x[0])]; rare = [x for x in rare if not LINKS.match(x[0])]
    print(f'== {table} {cand}  (role: {len(role)} rows)')
    for f, v, s in must: print(f'   MUST  {f}: ours={v}  all role rows={s[0]}')
    for f, v, s in rare: print(f'   rare  {f}: ours={v}  role e.g. {s}')
    if not must and not rare: print('   ok')
    return len(must)


def main(out):
    n_must = 0
    for t in ('GOP_Battle_UnitParam', 'GOP_Battle_Job', 'GOP_Battle_Weapon', 'GOP_Battle_WeaponAbilityTree',
              'GOP_Battle_AttackParam', 'GOP_Battle_Ability'):
        st = staged(out, t)
        if st is None: continue
        va = vanilla(t)
        new = [k for k in st if k not in va]
        rows = {**va, **{k: st[k] for k in new}}
        for k in new:
            if t == 'GOP_Battle_UnitParam':
                role = [r for r in va if re.fullmatch(r'BATTLE_UNITPARAM_CH_P0(0[1-9]|[12][0-9]|30)', r)]
            elif t == 'GOP_Battle_Job':
                role = [r for r in va if REC.search(r)]
            elif t == 'GOP_Battle_Weapon':
                m = re.match(r'BATTLE_WEAPON_(RANK[23]_)?', k); pre = m.group(0)
                role = [r for r in va if re.fullmatch(re.escape(pre) + r'P0(0[1-9]|[12][0-9]|30)', r)]
            elif t == 'GOP_Battle_WeaponAbilityTree':
                rk = k[-5:]; role = [r for r in va if REC.search(r) and r.endswith(rk)]
            elif t == 'GOP_Battle_AttackParam':
                if not k.startswith('BATTLE_ATTACKPARAM_WEAPON_'): continue
                role = [r for r in va if r.startswith('BATTLE_ATTACKPARAM_WEAPON_RANK') and REC.search(r)]
            else:
                r0 = rows[k]
                if r0['bIsWeaponAbility']:
                    role = [r for r in va if va[r]['bIsWeaponAbility']]
                else:
                    fam = next((f for f in FAMILIES if k.startswith('BATTLE_' + f)), None)
                    if fam:
                        role = [r for r in va if r.startswith('BATTLE_' + fam)]
                    else:
                        jb = vanilla('GOP_Battle_Job')
                        learned = {j[f'LearnableAbility{i}'] for n, j in jb.items() if REC.search(n) for i in range(1, 11)}
                        role = [r for r in learned if r in va and va[r]['eAbilityType'] == r0['eAbilityType']]
            if role: n_must += report(t, k, role, rows)
            else: print(f'== {t} {k}: no role rows found')
    print(f'\n{n_must} MUST difference(s)')


if __name__ == '__main__':
    main(sys.argv[1])
