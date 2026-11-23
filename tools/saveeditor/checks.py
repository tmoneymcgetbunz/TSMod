"""Legality checks: every value gets Safe / Risky / Dangerous, derived from the game's own tables
(vanilla + the installed TSMod pak), never from hand-written id lists.

  SAFE       consistent with the game's rules
  RISKY      legal but unusual: the game may recompute it, the story may not expect it, or it's untested
  DANGER     likely to crash the load or corrupt the save (e.g. an id no table has: Test 23)
"""
import re

SAFE, RISKY, DANGER = 'safe', 'risky', 'danger'
ORDER = {DANGER: 0, RISKY: 1, SAFE: 2}
LEVEL_CAP = 50                       # party level cap in the shipped game
SHOWN_LEARNED = 7                    # the unit screens list at most 7 learned class moves (Test 38)
ID_PATTERN = (rb'(?<![A-Z0-9_])(?:BATTLE_(?:ABILITY|JOB|WEAPON|UNITPARAM|ACCESSARY|ARMOR|INFO|STATUSEFFECT|ATTACKPARAM|'
              rb'CORRECTPARAM|ORDER)|ITEM|UNIT_MASTER|QUEST_INFO)_[A-Z0-9_]+')
# Ids that vanilla saves carry without a table row (seen in the untouched 100% save, 2026-11-20).
VANILLA_ORPHANS = {'BATTLE_ABILITY_AUTO_HEAL_TOUGHNESS'}


class Finding:
    def __init__(self, status, area, item, message, fix=None, fix_label=None):
        self.status, self.area, self.item, self.message = status, area, item, message
        self.fix, self.fix_label = fix, fix_label

    def __repr__(self):
        return f'{self.status.upper()} [{self.area}] {self.item}: {self.message}'


def worst(statuses):
    statuses = list(statuses)
    return min(statuses, key=lambda s: ORDER[s]) if statuses else SAFE


# ---------------------------------------------------------------------------------------------------- single values
def level_status(v):
    if not 1 <= v <= 99: return DANGER, 'outside 1-99: the record check fails'
    if v > LEVEL_CAP: return RISKY, f'above the level cap ({LEVEL_CAP})'
    return SAFE, ''


def exp_status(v):
    if not 0 <= v <= 99: return DANGER, 'outside 0-99: EXP runs 0-99 per level, and the unit-record check fails'
    return SAFE, ''


# Values the unit-record check needs (tools/tsunits.py unit_array): outside them the editor can't find the unit list.
RECORD_LIMITS = {'move_x100': (100, 1500), 'hp': (1, 9999)}


def stat_status(stat, v=None):
    if stat in ('level',): return SAFE, ''
    lim = RECORD_LIMITS.get(stat)
    if lim and v is not None and not lim[0] <= v <= lim[1]:
        return DANGER, f'outside {lim[0]}-{lim[1]}: the unit-record check fails'
    return RISKY, 'the game recomputes stats from the growth table on level-up and battle entry'


def gold_status(v):
    if v < 0: return DANGER, 'negative gold'
    if v > 9999999: return RISKY, 'above 9,999,999 (more than the game shows)'
    return SAFE, ''


def count_status(v):
    if v < 0: return DANGER, 'negative count'
    if v > 99: return RISKY, 'above 99 (the usual stack limit)'
    return SAFE, ''


def id_status(T, rid, kind=''):
    if rid in T.all_ids: return SAFE, ''
    if rid in VANILLA_ORPHANS: return RISKY, 'unknown id, but unmodified saves contain it too (harmless)'
    return DANGER, f'unknown {kind or "game"} id: the game can crash while loading this save'


def unknown_ids(T, blob):
    """Ids in some save bytes (e.g. a unit record being imported) that no table of the game or the installed TSMod pak
    has, without drop/money ids and the known harmless orphans."""
    seen = {x.decode() for x in re.findall(ID_PATTERN, blob)}
    return sorted(x for x in seen - T.all_ids - VANILLA_ORPHANS if not x.startswith(('ITEM_DROP', 'ITEM_MONEY')))


def record_status(T, uid, blob):
    """Rating for adding/replacing a whole unit record: Dangerous if it carries any id the installed game and mod lack
    (the Test 23 crash), else Risky (it keeps the source save's class, weapon and moves)."""
    bad = unknown_ids(T, blob)
    if uid not in T.all_ids and uid not in bad: bad = [uid] + bad
    if bad:
        return DANGER, (f'the record uses {len(bad)} id(s) the installed game/TSMod pak lacks ({", ".join(bad[:4])}'
                        f'{" …" if len(bad) > 4 else ""}): the game can crash while loading this save')
    return RISKY, "the record keeps the source save's class, weapon and moves"


def new_findings(before, after):
    """Findings in `after` that `before` doesn't have (same status, area, item and message)."""
    key = lambda f: (f.status, f.area, f.item, f.message)
    old = {key(f) for f in before}
    return [f for f in after if key(f) not in old]


def class_status(T, uid, job):
    s, m = id_status(T, job, 'class')
    if s != SAFE: return s, m
    if job not in T.unit_classes(uid): return RISKY, "not one of this unit's own classes"
    return SAFE, ''


def ability_status(T, uid, ability, info):
    s, m = id_status(T, ability, 'ability')
    if s != SAFE: return s, m
    kit = T.class_learnables(T.unit_classes(uid) | set(info['jobs']))
    for w in info['weapons']: kit |= T.weapon_line(w)[1]
    if ability not in kit: return RISKY, "not in this unit's class learn tables or weapon trees"
    return SAFE, ''


def flag_status(v):
    if v not in (0, 1): return DANGER, 'story flags are 0 or 1'
    return RISKY, 'story flags drive events: changing one can break the story order'


# ---------------------------------------------------------------------------------------------------- whole save
def report(save, T):
    """All findings for a loaded save, worst first."""
    out = []
    # units
    for uid in save.unit_ids():
        info = save.unit_info(uid)
        st = info['stats']
        s, m = id_status(T, uid, 'unit')
        if s != SAFE: out.append(Finding(s, 'Units', uid, m))
        s, m = level_status(st['level'])
        if s != SAFE:
            fix = (lambda u=uid: save.set_unit_stat(u, 'level', LEVEL_CAP, SAFE)) if st['level'] > LEVEL_CAP else None
            out.append(Finding(s, 'Units', T.name_of(uid), f"level {st['level']}: {m}", fix, f'Set level {LEVEL_CAP}'))
        for p in info['params']:
            s, m = id_status(T, p, 'unit param')
            if s != SAFE: out.append(Finding(s, 'Units', T.name_of(uid), f'param {p}: {m}'))
        for j in info['jobs']:
            s, m = class_status(T, uid, j)
            if s != SAFE: out.append(Finding(s, 'Units', T.name_of(uid), f'class {j}: {m}'))
        for w in info['weapons']:
            s, m = id_status(T, w, 'weapon')
            if s != SAFE: out.append(Finding(s, 'Units', T.name_of(uid), f'weapon {w}: {m}'))
        for flag, ab in info['learned']:
            s, m = ability_status(T, uid, ab, info)
            if s != SAFE:
                fix = (lambda u=uid, a=ab: save.remove_learned(u, a, SAFE)) if s == DANGER else None
                out.append(Finding(s, 'Units', T.name_of(uid), f'learned move {T.name_of(ab)}: {m}', fix, 'Unlearn'))
        if len(info['learned']) > SHOWN_LEARNED:
            out.append(Finding(RISKY, 'Units', T.name_of(uid),
                               f"{len(info['learned'])} learned moves: the game shows only the first {SHOWN_LEARNED}"))
    # gold and inventory
    s, m = gold_status(save.gold)
    if s != SAFE: out.append(Finding(s, 'Overview', 'Gold', f'{save.gold:,}: {m}'))
    for mp in save.parts['maps']:
        if mp['label'] not in ('items', 'materials', 'medals', 'accessories', 'notes'): continue
        for k, at, v in mp['entries']:
            s, m = id_status(T, k)
            if s == DANGER and not k.startswith('NOTE_'): out.append(Finding(s, 'Items', k, m))
            s, m = count_status(v)
            if s != SAFE: out.append(Finding(s, 'Items', T.name_of(k), f'{v}: {m}'))
    # story
    for nm, at, v in save.flags['entries']:
        if v not in (0, 1): out.append(Finding(DANGER, 'Story', nm, f'value {v}: story flags are 0 or 1'))
    try:
        a = save.sysvar('SCENARIO_ANCHOR')['value']
        from . import story
        if not 0 <= a < len(story.anchors()):
            out.append(Finding(DANGER, 'Story', 'SCENARIO_ANCHOR', f'{a} is not a story point'))
    except KeyError:
        out.append(Finding(DANGER, 'Story', 'SCENARIO_ANCHOR', 'missing'))
    # every id anywhere in the save (unit records and saved battle state), Test 23
    seen = {x.decode() for x in re.findall(ID_PATTERN, save.plaintext())}
    for rid in sorted(seen - T.all_ids):
        if rid.startswith('ITEM_DROP') or rid.startswith('ITEM_MONEY'): continue
        s = RISKY if rid in VANILLA_ORPHANS else DANGER
        msg = 'unknown id, but unmodified saves contain it too (harmless)' if s == RISKY else \
            'unknown id: the game can crash while loading this save. Is the matching TSMod version installed?'
        out.append(Finding(s, 'Save data', rid, msg))
    # mod dependence
    mod_ids = {x for x in seen if re.search(r'_[A-Z]\d{3}P(?:_|$)', x)}
    if mod_ids and not T.mod_paks:
        out.append(Finding(DANGER, 'Mod', 'TSMod', f'the save uses {len(mod_ids)} TSMod ids but no TSMod pak is installed'))
    out.sort(key=lambda f: ORDER[f.status])
    return out
