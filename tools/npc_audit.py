"""Audit every named non-playable character in TRIANGLE STRATEGY.

Inputs : extracted/ DataTables (Unit_Master, Battle_UnitParam/Job/Weapon/UnitGrowth/
         WeaponAbilityTree, text tables) and decompiled/ Lua scripts.
Outputs: data/npc_reference.json, plus a printed summary.

Run: .venv/Scripts/python tools/npc_audit.py
"""
import collections, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import dtparse as D

DT = os.path.join(ROOT, 'extracted', 'TRIANGLE_STRATEGY', 'Content', 'Newera', 'Data', 'DataTables')
LUA = os.path.join(ROOT, 'decompiled', 'Newera_Handling')


def table(name):
    _, rows = D.parse(os.path.join(DT, name + '.uasset'))
    return {k: {f: p['v'] for f, p in r.items()} for k, r in rows.items()}


UM = table('GOP_Unit_Master'); UP = table('GOP_Battle_UnitParam'); JOB = table('GOP_Battle_Job')
WPN = table('GOP_Battle_Weapon'); GRO = table('GOP_Battle_UnitGrowth'); TREE = table('GOP_Battle_WeaponAbilityTree')
ABL = table('GOP_Battle_Ability'); FACE = table('Gop_Character_Face'); ATT = table('GOP_Unit_Attached_Data_Set')
TXT = {}
for t in ['Common', 'Job', 'Weapon', 'Ability', 'Character_Profile']:
    TXT.update({k: v['Text'] for k, v in table('Text/en/GOP_Text_' + t).items()})


def tx(key):
    return TXT.get(key) if key and key != 'None' else None


def short(enum):
    return str(enum).split('::')[-1] if enum is not None else None


# ---------------------------------------------------------------- growth ranges
growth_levels = collections.defaultdict(list)
for k in GRO:
    m = re.match(r'(.+)_(\d+)$', k)
    if m: growth_levels[m.group(1)].append(int(m.group(2)))


def growth_info(gt):
    lv = sorted(growth_levels.get(gt, []))
    if not lv: return None
    pick = lambda L: {s: GRO[f'{gt}_{L:02d}' if f'{gt}_{L:02d}' in GRO else f'{gt}_{L}'].get(s) for s in
                      ('fMaxHitPoint', 'fStrength', 'fIntelligence', 'fDefence', 'fMagicDefence', 'fDexterity', 'fAgility', 'fLuck', 'fUnitSpeed')}
    return {'table': gt, 'levels': f'{lv[0]}-{lv[-1]}', 'count': len(lv),
            'lv1': pick(lv[0]), f'lv{lv[-1]}': pick(lv[-1])}


def job_info(j):
    r = JOB.get(j)
    if not r: return {'id': j, 'missing': True}
    learn = []
    for i in range(1, 11):
        a = r.get(f'LearnableAbility{i}')
        if a and a != 'None':
            learn.append({'lv': r.get(f'iLearnableLevel{i}'), 'id': a, 'name': tx(ABL.get(a, {}).get('AbilityName'))})
    nxt = [r.get(f'JobTypeAfter{i}') for i in (1, 2, 3) if r.get(f'JobTypeAfter{i}') not in (None, 'None')]
    return {'id': j, 'name': tx(r.get('JobName')), 'type': short(r.get('eJobType')), 'rank': short(r.get('eJobRank')),
            'promotes_to': nxt, 'abilities': learn,
            'support': [a for a in (r.get('AutoSupportAbility1'), r.get('AutoSupportAbility2')) if a not in (None, 'None')]}


def weapon_info(w):
    r = WPN.get(w)
    if not r: return {'id': w, 'missing': True}
    tree = r.get('WeaponAbilityTree')
    return {'id': w, 'name': tx(r.get('WeaponName')), 'type': short(r.get('eWeaponType')),
            'tree': None if tree in (None, 'None') else tree,
            'rank_up': None if r.get('RankUpWeapon') in (None, 'None') else r.get('RankUpWeapon'),
            'upgradable': r.get('iUpgradeMoney', 0) not in (0, None)}


def param_info(p):
    r = UP.get(p)
    if not r: return {'id': p, 'missing': True}
    gts = sorted({r.get(f) for f in ('UnitGrowthTable', 'UnitGrowthTable2', 'UnitGrowthTable3')} - {None, 'None'})
    return {'id': p, 'camp': short(r.get('eUnitCamp')), 'ai': short(r.get('eUnitAIType')), 'guest': r.get('bIsGuest'),
            'ignore_exp': r.get('bIsIgnoreExperience'), 'armor': short(r.get('eSpecificEffectType')),
            'mount': short(r.get('eSpecificEffectType2')),
            'job': job_info(r.get('UnitClass')), 'weapon': weapon_info(r.get('EquippedWeapon')),
            'growth': [growth_info(g) for g in gts], 'drop': r.get('DropItem')}


# ---------------------------------------------------------------- scripts
chapter_re = re.compile(r'Story/(ms\d+[a-z]?_[a-z]\d+[a-z]?)/|CharaStory/(cs\d+)|/(cs_e_\d+)|Develop/|Debug')
battle_name = {}
for dp, _, fs in os.walk(LUA):
    for f in fs:
        if not f.endswith('.lua'): continue
        s = open(os.path.join(dp, f), encoding='utf-8', errors='replace').read()
        m = re.search(r'BattleFieldTextId = "([A-Z0-9_]+)"', s)
        if m: battle_name[f[:-4]] = tx(m.group(1)) or m.group(1)

spawns = collections.defaultdict(list)   # unit master -> appearances in battles
scene_calls = collections.defaultdict(collections.Counter)  # unit master -> {context: count}
cd_re = re.compile(r'CreateUnitData\(\s*"([^"]*)",\s*"([^"]*)",\s*"([^"]*)",\s*([^,]+),\s*([^,]+),\s*([^,]+),\s*([^,]+),\s*([^,]+),\s*([^,)]+)(?:,\s*([^,)]+))?')
su_re = re.compile(r'SpawnUnit\(\s*"([^"]*)",\s*"(UNIT_MASTER[^"]*)",\s*"([^"]*)",\s*([^,]+),\s*([^,]+)')
call_re = re.compile(r'chara\.call\("(UNIT_MASTER_[A-Z0-9_]+)"')


def first_lap_levels(src):
    """Values assigned in the first `== 0 then` (first playthrough) branch, e.g. lv = 1."""
    m = re.search(r'GAME_RESULT_COUNT\)\s*==\s*0\s*then(.*?)(elseif|else|end)', src, re.S)
    vals = {}
    if m:
        for k, v in re.findall(r'(\w+)\s*=\s*(\d+)', m.group(1)): vals[k] = int(v)
    for k, v in re.findall(r'^local (\w+)\s*=\s*(\d+)\s*$', src, re.M): vals.setdefault(k, int(v))
    return vals


def eval_level(expr, vals):
    e = expr.strip()
    try:
        return int(eval(e, {'__builtins__': {}}, dict(vals)))
    except Exception:
        return e


for dp, _, fs in os.walk(LUA):
    for f in fs:
        if not f.endswith('.lua'): continue
        path = os.path.join(dp, f); rel = os.path.relpath(path, LUA).replace('\\', '/')
        if rel.startswith(('Develop/', 'Debug')) or 'Test' in rel or 'MapEditor' in rel: continue
        src = open(path, encoding='utf-8', errors='replace').read()
        m = chapter_re.search(rel)
        ctx = (m.group(1) or m.group(2) or m.group(3)) if m and m.group(0) not in ('Develop/', 'Debug') else rel.split('/')[0]
        vals = first_lap_levels(src)
        battle = re.sub(r'_common$', '', f[:-4])
        for g in cd_re.finditer(src):
            name, um, prm, x, y = g.group(1), g.group(2), g.group(3), g.group(4), g.group(5)
            spawns[um].append({'battle': battle, 'battle_name': battle_name.get(battle), 'context': ctx, 'unit_name': name,
                               'param': prm, 'pos': [eval_level(x, {}), eval_level(y, {})],
                               'level_first_playthrough': eval_level(g.group(9), vals), 'file': rel})
        for g in su_re.finditer(src):
            spawns[g.group(2)].append({'battle': f[:-4], 'battle_name': battle_name.get(f[:-4]), 'context': ctx,
                                       'unit_name': g.group(1), 'param': g.group(3), 'via': 'SpawnUnit', 'file': rel})
        for g in call_re.finditer(src):
            scene_calls[g.group(1)][ctx] += 1

# ---------------------------------------------------------------- characters
chars = collections.defaultdict(list)
for k, r in UM.items():
    chars[short(r.get('eCharacterId'))].append(k)


def unit_info(k):
    r = UM[k]
    gp = r.get('GrowthUnitBattleParamId')
    params = sorted({s['param'] for s in spawns.get(k, []) if s['param']} | ({gp} if gp not in (None, 'None') else set()))
    return {'id': k, 'name': tx(r.get('CharacterName')), 'full_name': tx(r.get('CharacterFullName')),
            'category': short(r.get('eUnitCategory')), 'face': r.get('FaceId'), 'voice': short(r.get('ActionVoiceType')),
            'sprite_type': short(r.get('SpriteType')), 'growth_unit': r.get('bGrowthUnit'),
            'growth_param': None if gp in (None, 'None') else gp, 'new_game_member': r.get('bNewGameMember'),
            'belief_lists': [r.get(f) for f in ('BeliefUpClassUpId', 'BeliefUpWeaponUpId', 'BeliefUpSubEventId', 'BeliefUpMoralUpId') if r.get(f) not in (None, 'None')],
            'attached_data_set': r.get('UnitAttachedDataSetId'),
            'battle_params_used': params,
            'battle_appearances': spawns.get(k, []),
            'scene_appearances': dict(scene_calls.get(k, {}))}


def named(cid, rows):
    if cid.startswith('CHAR_ID_N') or cid == 'CHAR_ID_M103':
        return True
    return False


out = {'characters': [], 'playable_variants': [], 'named_minor': []}
for cid, rows in sorted(chars.items()):
    if cid.startswith('CHAR_ID_P'):
        extra = [k for k in rows if not re.fullmatch(r'UNIT_MASTER_CH_P0\d\d', k)]
        # playables' non-playable forms: other unit-master rows, and params other than their own P row
        pk = [k for k in rows if re.fullmatch(r'UNIT_MASTER_CH_P0\d\d', k)]
        own = {f"BATTLE_UNITPARAM_CH_{k.split('_')[-1]}" for k in pk}
        alt_params = sorted({s['param'] for k in pk for s in spawns.get(k, [])
                             if s['param'] and s['param'] not in own and s['param'] in UP and 'Test' not in s['context']})
        if extra or alt_params:
            out['playable_variants'].append({'character_id': cid, 'name': tx(UM[pk[0]]['CharacterName']) if pk else None,
                                             'extra_unit_masters': [unit_info(k) for k in extra],
                                             'non_player_params': [param_info(p) for p in alt_params],
                                             'appearances_with_those_params': [s for k in pk for s in spawns.get(k, []) if s['param'] in alt_params]})
        continue
    if not named(cid, rows):
        continue
    units = [unit_info(k) for k in sorted(rows)]
    prof = {k: v for k, v in TXT.items() if re.match(rf'TEXT_CHARACTER_PROFILE_{cid[8:]}_\d+', k)}
    params = sorted({p for u in units for p in u['battle_params_used']})
    out['characters'].append({'character_id': cid, 'name': units[0]['name'] or next((u['name'] for u in units if u['name']), None),
                              'full_name': next((u['full_name'] for u in units if u['full_name']), None),
                              'profile': list(prof.values()),
                              'job_name_texts': {k: v for k, v in TXT.items() if re.match(rf'TEXT_JOB_NAME_{cid[8:]}', k)},
                              'unit_masters': units, 'battle_params': [param_info(p) for p in params]})

# named minor characters: unit masters whose name text is a possessive or unique (e.g. "Sycras's Wife")
name_count = collections.Counter(tx(r.get('CharacterName')) for r in UM.values())
for k, r in sorted(UM.items()):
    n = tx(r.get('CharacterName'))
    cid = short(r.get('eCharacterId'))
    TYPE = (r'(Soldier|Bowman|Blade|Shieldbearer|Pikeman|Battlemage|Healer|Rogue|Hawkbow|Rider|Lancer|Archer|Elite|Citizen|'
            r'Subject|Townsperson|Miner|Researcher|Official|Merchant|Child|Noble|Rosellan|Bandit|Brigand|Mercenary|Guard|'
            r'Captain|Soldiers|Assassin|Automaton|Cavalry|Knight|Priest|Monk|Saltmonger|Dealer|Elder|Allies|Spectators)')
    if n and name_count[n] == 1 and cid.startswith('CHAR_ID_M') and cid != 'CHAR_ID_M103' and \
            ("'s " in n or not re.search(TYPE, n)):
        out['named_minor'].append({'id': k, 'name': n, 'character_id': cid, 'scene_appearances': dict(scene_calls.get(k, {})),
                                   'battle_appearances': spawns.get(k, [])})

os.makedirs(os.path.join(ROOT, 'data'), exist_ok=True)
json.dump(out, open(os.path.join(ROOT, 'data', 'npc_reference.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
print('named characters:', len(out['characters']), '| playables with NPC forms:', len(out['playable_variants']), '| named minor:', len(out['named_minor']))
for c in out['characters']:
    print(f"{c['character_id']:14} {str(c['name']):18} units={len(c['unit_masters'])} params={len(c['battle_params'])} "
          f"battles={sum(len(u['battle_appearances']) for u in c['unit_masters'])} scenes={sum(sum(u['scene_appearances'].values()) for u in c['unit_masters'])}")
