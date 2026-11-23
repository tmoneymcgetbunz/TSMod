"""Generate DataTable edits for a full recruit kit from a spec.

  python tools/gen_recruit.py <mod_dir>      (reads <mod_dir>/spec.json, writes <mod_dir>/mod.json)

New ids use the pattern <..._CH_><id>P_<n> (e.g. BATTLE_JOB_CH_N106P_1). Everything references vanilla rows
as templates, and every referenced id is checked to exist (in vanilla or in this spec) before writing.
Lua parts (join hooks) are merged from an optional "lua_append" in the existing mod.json / spec.
"""
import json, os, statistics, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DT = 'Newera/Data/DataTables/'
TXT = DT + 'Text/en/'


def load(t):
    return json.load(open(os.path.join(ROOT, 'data', 'tables', t + '.json'), encoding='utf-8'))


def main(mod_dir):
    spec = json.load(open(os.path.join(mod_dir, 'spec.json'), encoding='utf-8'))
    cid = spec['id']; P = cid + 'P'
    up, jb, wp, ab, ap, wt, g = (load(t) for t in ('GOP_Battle_UnitParam', 'GOP_Battle_Job', 'GOP_Battle_Weapon',
                                                    'GOP_Battle_Ability', 'GOP_Battle_AttackParam',
                                                    'GOP_Battle_WeaponAbilityTree', 'GOP_Battle_UnitGrowth'))
    E = []
    new_ab = {t['id'] for t in spec['tree_abilities']}
    def need(table, key, extra=()):
        if key not in table and key not in extra: raise SystemExit(f'missing id: {key}')

    # ---- stats: Elite = source table, Recruit/Veteran scaled by recruit averages
    src = spec['stats']['elite_source']; keep = set(spec['stats']['keep_from_source'])
    fields = [f for f in g[f'{src}_01'] if f != 'SelfId']
    ratio = {}
    for lv in range(1, 61):
        for r in ('R1', 'R2'):
            for f in fields:
                vals = []
                for i in range(1, 31):
                    a = g.get(f'BATTLE_UNITGROWTH_CH_P{i:03d}_{r}_{lv:02d}'); b = g.get(f'BATTLE_UNITGROWTH_CH_P{i:03d}_R3_{lv:02d}')
                    if a and b and b[f]: vals.append(a[f] / b[f])
                ratio[(r, lv, f)] = statistics.mean(vals) if vals else 1.0
    tp = {}
    for r in ('R1', 'R2', 'R3'):
        for lv in range(1, 61):
            tp[(r, lv)] = statistics.mode(g[f'BATTLE_UNITGROWTH_CH_P{i:03d}_{r}_{lv:02d}']['fMaxTacticalPoint'] for i in range(1, 31))
    # Boss-source mode (Batch B1): Elite = boss value x "scale" multiplier; speed follows the recruit Elite speed curve,
    # scaled so Elite Lv50 = "speed_at_50". Rule from the 7 characters with both a guest and a boss table.
    scale = spec['stats'].get('scale', {}); spd50 = spec['stats'].get('speed_at_50')
    if spd50:
        avg_spd = {lv: statistics.mean(g[f'BATTLE_UNITGROWTH_CH_P{i:03d}_R3_{lv:02d}']['fUnitSpeed'] for i in range(1, 31)) for lv in range(1, 61)}
    def elite(f, lv, base):
        if spd50 and f == 'fUnitSpeed': return round(avg_spd[lv] * spd50 / avg_spd[50])
        return round(base[f] * scale[f]) if f in scale else base[f]
    rows = []
    for ri, r in enumerate(('R1', 'R2', 'R3')):
        for lv in range(1, 61):
            base = g[f'{src}_{lv:02d}']; s = {}
            for f in fields:
                if f in keep: continue
                if f == 'fMaxTacticalPoint': s[f] = tp[(r, lv)]; continue
                e = elite(f, lv, base)
                v = e if r == 'R3' else round(e * ratio[(r, lv, f)])
                if v != base[f]: s[f] = float(v)
            rows.append({'row': f'BATTLE_UNITGROWTH_CH_{P}_{r}_{lv:02d}', 'copy_from': f'{src}_{lv:02d}', 'set': s})
    E.append({'table': DT + 'GOP_Battle_UnitGrowth', 'add_rows': rows})

    # ---- weapon attack param (power like recruits)
    w = spec['weapon']; atk = f'BATTLE_ATTACKPARAM_WEAPON_{P}'
    need(ap, w['attack_template'])
    E.append({'table': DT + 'GOP_Battle_AttackParam', 'add_row': atk, 'copy_from': w['attack_template']})
    E += [{'table': DT + 'GOP_Battle_AttackParam', 'row': atk, 'field': f, 'value': w['power']} for f in ('fPower', 'fPowerMax')]

    # ---- own copies of abilities (e.g. a rebalanced NPC ability); the vanilla row stays untouched
    own = {o['id']: o for o in spec.get('own_abilities', [])}
    new_ab |= set(own)
    for o in own.values():
        need(ab, o['copy_from'])
        E.append({'table': DT + 'GOP_Battle_Ability', 'add_row': o['id'], 'copy_from': o['copy_from']})
        sets = dict(o.get('set', {}))
        if 'attack' in o:
            a = o['attack']; need(ap, a['copy_from'])
            E.append({'table': DT + 'GOP_Battle_AttackParam', 'add_row': a['id'], 'copy_from': a['copy_from']})
            E += [{'table': DT + 'GOP_Battle_AttackParam', 'row': a['id'], 'field': k, 'value': v} for k, v in a.get('set', {}).items()]
            sets['AttackParam'] = a['id']
        sets.setdefault('bEnableCopy', False)                     # like every recruit ability
        for kind, key in (('AbilityName', 'name'), ('AbilityHelp', 'help')):   # reskin: own text rows
            if key in o:
                tid = f"TEXT_ABILITY_{'NAME' if key == 'name' else 'HELP'}_{o['id'][15:]}"
                E.append({'table': TXT + 'GOP_Text_Ability', 'add_row': tid, 'copy_from': ab[o['copy_from']][kind]})
                E.append({'table': TXT + 'GOP_Text_Ability', 'row': tid, 'field': 'Text', 'value': o[key]})
                sets[kind] = tid
        E += [{'table': DT + 'GOP_Battle_Ability', 'row': o['id'], 'field': k, 'value': v} for k, v in sets.items()]
    sort_of = lambda a: own[a].get('set', {}).get('iSortNumber', ab[own[a]['copy_from']]['iSortNumber']) if a in own else ab[a]['iSortNumber']

    # ---- tree abilities + text
    # Node icon (cleanup 2026-11-20): templates carry their own icon (Fire Magic Damage Up = fire, Charm extension =
    # temptation), which showed on every node made from them. Damage nodes now take the target move's element; effect
    # nodes take the status the move applies; TP/range nodes keep the template's (TP down / no element).
    def target_rows(a):
        o = own.get(a)
        row = dict(ab[o['copy_from'] if o else a], **(o.get('set', {}) if o else {}))
        atk = dict(ap.get(o['attack']['copy_from'] if o and 'attack' in o else row['AttackParam'], {}),
                   **(o['attack'].get('set', {}) if o and 'attack' in o else {}))
        return row, atk
    STATUS_ICON = (('POISON', 'POISON'), ('SLEEP', 'SLEEP'), ('BLIND', 'BLIND'), ('DARKNESS', 'BLIND'),
                   ('IMMOVABLE', 'IMMOVABLE'), ('ANGRY', 'ANGRY'), ('TEMPTATION', 'TEMPTATION'), ('CHARM', 'TEMPTATION'))
    def node_icon(t):
        kind = t['template']
        if kind.endswith(('DAMAGE_UP_INTIMIDATION_SWORD', 'DAMAGE_UP_FIRE_MAGIC')):
            row, atk = target_rows(t['targets'][0])
            el = atk.get('eElementalType', 'EElementalType::NONE').split('::')[-1]
            return el if el in ('FIRE', 'ICE', 'WIND', 'THUNDER') else 'NOATTRIBUTE'
        if kind.endswith('EXTENSION_CHARM'):
            row, atk = target_rows(t['targets'][0])
            st = atk.get('StatusEffectId', 'None')
            for key, icon in STATUS_ICON:
                if key in st: return icon
            return 'BUFF' if row['eFunctionIconType'].endswith('BUFF') else 'DEBUFF'
        return None
    for t in spec['tree_abilities']:
        need(ab, t['template'])
        E.append({'table': DT + 'GOP_Battle_Ability', 'add_row': t['id'], 'copy_from': t['template']})
        nm, hp = f"TEXT_ABILITY_NAME_{t['id'][15:]}", f"TEXT_ABILITY_HELP_{t['id'][15:]}"
        for k, v in (('AbilityName', nm), ('AbilityHelp', hp)):
            E.append({'table': DT + 'GOP_Battle_Ability', 'row': t['id'], 'field': k, 'value': v})
        for i, target in enumerate(t['targets'], 1):
            E.append({'table': DT + 'GOP_Battle_Ability', 'row': t['id'], 'field': f'FNameParam{i}', 'value': target})
        E += [{'table': DT + 'GOP_Battle_Ability', 'row': t['id'], 'field': k, 'value': v} for k, v in t.get('set', {}).items()]
        icon = None if 'eFunctionIconTypeAbilityTree' in t.get('set', {}) else node_icon(t)
        if icon:
            E.append({'table': DT + 'GOP_Battle_Ability', 'row': t['id'], 'field': 'eFunctionIconTypeAbilityTree',
                      'value': 'EFunctionIconTypeAbilityTree::' + icon})
        tmpl = ab[t['template']]
        for kind, tid, text in (('AbilityName', nm, t['name']), ('AbilityHelp', hp, t['help'])):
            E.append({'table': TXT + 'GOP_Text_Ability', 'add_row': tid, 'copy_from': tmpl[kind]})
            E.append({'table': TXT + 'GOP_Text_Ability', 'row': tid, 'field': 'Text', 'value': text})

    # ---- weapon skill: the recruit gets its own copy (vanilla row stays untouched for the NPC/boss)
    ws_src = next((rk['weapon_skill'] for rk in spec['weapon']['ranks'] if 'weapon_skill' in rk), None)
    ws_own = ws_src in own                     # weapon skill may itself be an own (reskinned) ability
    ws_id = (ws_src if ws_own else (spec['weapon'].get('weapon_skill_id') or f'{ws_src}P')) if ws_src else None
    if ws_id: new_ab.add(ws_id)

    # ---- trees
    tree_ids = [f'BATTLE_WEAPONABILITYTREE_{P}_RANK{i}' for i in (1, 2, 3)]
    for tid, t in zip(tree_ids, spec['tree']):
        need(wt, t['template'])
        E.append({'table': DT + 'GOP_Battle_WeaponAbilityTree', 'add_row': tid, 'copy_from': t['template']})
        for i in range(1, 6):
            node = t['nodes'][i - 1] if i <= len(t['nodes']) else 'None'
            if ws_src and node == ws_src: node = ws_id
            if node != 'None': need(ab, node, new_ab)
            E.append({'table': DT + 'GOP_Battle_WeaponAbilityTree', 'row': tid, 'field': f'AbilityId{i}', 'value': node})

    # ---- weapons
    wids = [f'BATTLE_WEAPON_{P}', f'BATTLE_WEAPON_RANK2_{P}', f'BATTLE_WEAPON_RANK3_{P}']
    for i, (wid, rk) in enumerate(zip(wids, w['ranks'])):
        need(wp, rk['template'])
        E.append({'table': DT + 'GOP_Battle_Weapon', 'add_row': wid, 'copy_from': rk['template']})
        name_id = rk.get('name_text') or f'TEXT_WEAPON_NAME_RANK{i + 1}_{P}'
        sets = {'WeaponName': name_id, 'WeaponIconType': w['icon'], 'AttackParam': atk, 'WeaponAbilityTree': tree_ids[i],
                'RankUpWeapon': wids[i + 1] if i < 2 else 'None', 'RankDownWeapon': wids[i - 1] if i > 0 else 'None'}
        if 'rankup_material' in rk: sets['RankUpMaterial1'] = rk['rankup_material']
        # No Azure Crystal (RANKUP_BEAD): the sundry shop never sells it (Test 21; user rule, 2026-11-23).
        mat = sets.get('RankUpMaterial1') or wp[rk['template']].get('RankUpMaterial1')
        if 'RANKUP_BEAD' in str(mat):
            sys.exit(f'{wid}: rank-up material is Azure Crystal (RANKUP_BEAD), which the shop never sells; pick another')
        # Gold-only weapon tree (Test 21b crash): the Items > Materials panel lists every party member whose tree
        # uses the material, in 12 fixed slots with an off-by-one bound (exe +1048bd0). Vanilla fills exactly 12
        # per Lv-up material, so recruits must not use any. Own cost row = template's with materials cleared, gold kept.
        wam_src = wp[rk['template']]['WeaponAbilityMaterial']
        if wam_src != 'None':
            wam_id = f'BATTLE_WEAPONABILITYMATERIAL_{P}_RANK{i + 1}'
            E.append({'table': DT + 'GOP_Battle_WeaponAbilityMaterial', 'add_row': wam_id, 'copy_from': wam_src})
            for n in range(1, 6):
                for m in (1, 2):
                    E.append({'table': DT + 'GOP_Battle_WeaponAbilityMaterial', 'row': wam_id, 'field': f'MaterialId{m}_{n}', 'value': 'None'})
                    E.append({'table': DT + 'GOP_Battle_WeaponAbilityMaterial', 'row': wam_id, 'field': f'iMaterialNum{m}_{n}', 'value': 0})
            sets['WeaponAbilityMaterial'] = wam_id
        if i == 2 and 'weapon_skill' not in rk: sets['Ability'] = 'None'   # capstone is a passive tree node instead (Booker)
        if 'weapon_skill' in rk:
            if not ws_own: need(ab, rk['weapon_skill'])
            sets['Ability'] = ws_id
            # own copy of the source ability, flagged like all 30 vanilla weapon skills (Test 9/10):
            #   bIsWeaponAbility True  -> registered as the weapon skill on purchase + framed tree node
            #   eFunctionIconTypeAbilityTree UNIT_WEAPON -> weapon icon;  bEnableCopy False -> not Copycat-able
            if not ws_own: E.append({'table': DT + 'GOP_Battle_Ability', 'add_row': ws_id, 'copy_from': rk['weapon_skill']})
            # battle menu sorts commands by iSortNumber ascending; vanilla weapon skills use 999 so they come last,
            # but NPC abilities are numbered 1000+, so go above every ability in this unit's learn table
            learned = [a for c in spec['classes'] for _, a in c['learn'] if a in ab or a in own]
            ws_sort = max([999] + [sort_of(a) + 1 for a in learned])
            for f, v in (('bIsWeaponAbility', True), ('bEnableCopy', False), ('iSortNumber', ws_sort),
                         ('eFunctionIconTypeAbilityTree', 'EFunctionIconTypeAbilityTree::UNIT_WEAPON')):
                E.append({'table': DT + 'GOP_Battle_Ability', 'row': ws_id, 'field': f, 'value': v})
        E += [{'table': DT + 'GOP_Battle_Weapon', 'row': wid, 'field': k, 'value': v} for k, v in sets.items()]
        if 'name' in rk:
            E.append({'table': TXT + 'GOP_Text_Weapon', 'add_row': name_id, 'copy_from': wp[rk['template']]['WeaponName']})
            E.append({'table': TXT + 'GOP_Text_Weapon', 'row': name_id, 'field': 'Text', 'value': rk['name']})

    # ---- classes
    jids = [f'BATTLE_JOB_CH_{P}_{c["rank"]}' for c in spec['classes']]
    help_id = f'TEXT_JOB_HELP_{P}'
    for i, (jid, c) in enumerate(zip(jids, spec['classes'])):
        need(jb, c['template'])
        E.append({'table': DT + 'GOP_Battle_Job', 'add_row': jid, 'copy_from': c['template']})
        name_id = c.get('name_text') or f'TEXT_JOB_NAME_{P}_{c["rank"]}'
        sets = {'eJobType': spec['job_type'], 'JobName': name_id, 'JobHelp': help_id,
                'JobTypeBefore': jids[i - 1] if i > 0 else 'None', 'JobTypeAfter1': jids[i + 1] if i < 2 else 'None',
                'JobTypeAfter2': 'None', 'JobTypeAfter3': 'None', 'JobTypeParallel1': 'None', 'JobTypeParallel2': 'None'}
        for k in range(1, 11):
            lv, a = (c['learn'][k - 1] if k <= len(c['learn']) else (0, 'None'))
            if a != 'None': need(ab, a, new_ab)
            sets[f'iLearnableLevel{k}'] = lv; sets[f'LearnableAbility{k}'] = a
        E += [{'table': DT + 'GOP_Battle_Job', 'row': jid, 'field': k, 'value': v} for k, v in sets.items()]
        if 'name' in c:
            E.append({'table': TXT + 'GOP_Text_Job', 'add_row': name_id, 'copy_from': jb[c['template']]['JobName']})
            E.append({'table': TXT + 'GOP_Text_Job', 'row': name_id, 'field': 'Text', 'value': c['name']})
    # (vanilla job help rows aren't in the en table; copy any existing Text_Job row as the template)
    E.append({'table': TXT + 'GOP_Text_Job', 'add_row': help_id, 'copy_from': jb[spec['classes'][0]['template']]['JobName']})
    E.append({'table': TXT + 'GOP_Text_Job', 'row': help_id, 'field': 'Text', 'value': spec['class_help']})

    # ---- party param + unit master
    pp = spec['party_param']
    E.append({'table': DT + 'GOP_Battle_UnitParam', 'add_row': pp, 'copy_from': spec['param_template']})
    psets = {'eUnitAIType': 'EUnitAIType::NONE', 'bIsGuest': False, 'bIsIgnoreExperience': False,
             'UnitClass': jids[0], 'EquippedWeapon': wids[0],
             'UnitGrowthTable': f'BATTLE_UNITGROWTH_CH_{P}_R1', 'UnitGrowthTable2': f'BATTLE_UNITGROWTH_CH_{P}_R2',
             'UnitGrowthTable3': f'BATTLE_UNITGROWTH_CH_{P}_R3', **spec.get('param_set', {})}
    E += [{'table': DT + 'GOP_Battle_UnitParam', 'row': pp, 'field': k, 'value': v} for k, v in psets.items()]
    E += [{'table': DT + 'GOP_Unit_Master', 'row': spec['unit_master'], 'field': 'bGrowthUnit', 'value': True},
          {'table': DT + 'GOP_Unit_Master', 'row': spec['unit_master'], 'field': 'GrowthUnitBattleParamId', 'value': pp}]
    # raw dt_edits for rows the generator has no concept of (e.g. a new StatusEffectAtk row); table names short
    E += [{**e, 'table': DT + e['table']} for e in spec.get('extra_edits', [])]

    out =os.path.join(mod_dir, 'mod.json')
    old = json.load(open(out, encoding='utf-8')) if os.path.exists(out) else {}
    cfg = {'name': old.get('name', f'TSMod_Recruit_{cid}_Full'), **{k: v for k, v in old.items() if k in ('lua', 'lua_append')},
           'dt_edits': E, **{k: spec[k] for k in ('flipbook_static', 'sprite_clones', 'bp_sprite', 'unit_actor') if k in spec}}
    json.dump(cfg, open(out, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print(f'wrote {out}: {len(E)} edit entries ({len(rows)} stat rows), classes {jids}, weapons {wids}')
    # small stat preview
    for r in ('R1', 'R2', 'R3'):
        for lv in (10, 30, 50):
            rr = next(x for x in rows if x['row'].endswith(f'{r}_{lv:02d}'))
            b = g[rr['copy_from']]; s = {**{f: b[f] for f in fields}, **rr['set']}
            print(f"  {r} Lv{lv}: HP {s['fMaxHitPoint']:g} SPD {s['fUnitSpeed']:g} STR {s['fStrength']:g} INT {s['fIntelligence']:g} DEF {s['fDefence']:g} MDF {s['fMagicDefence']:g} TP {s['fMaxTacticalPoint']:g}")


if __name__ == '__main__':
    main(sys.argv[1])
