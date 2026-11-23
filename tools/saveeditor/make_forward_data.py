"""Developer script: add the forward-jump data to story_data.json (section "forward"; the editor ships without the
game's scripts). Research 2026-11-22: mods/TESTING.md "Forward story jump".

Reads (game v1.1.0, decompiled Lua + data/tables):
  - Scenario/Story/<part>/**/*.lua: per chapter part (folder), the flags its scripts switch on
    (SetFlag(Flag.X, true|ON), SetFlagUp) and off (SetFlag(Flag.X, false|0)), and the party joins / departures
    (JoinParty / LeaveParty), in scene order (file names sorted by their scene number).
  - Scenario/CommonDef/ShopFlagList.lua: the cumulative shop unlocks per chapter (OpenShopFlag_MSxx, called by the game's
    own code at chapter start [read: no Lua caller]).
  - data/tables/GOP_World_Icon.json: each marker's "ever done" end flag (WorldIconEndFlagEx).
Writes story_data.json["forward"] = {"parts": {PART: {"on", "off", "party"}}, "shops": [[chapter, suffix, flags]],
"icon_end_ex": {icon: flag}}.
Run from the repository root:  python tools/saveeditor/make_forward_data.py
"""
import glob, json, os, re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
OUT = os.path.join(os.path.dirname(__file__), 'story_data.json')
DEC = os.path.join(ROOT, 'decompiled', 'Newera_Handling')
STORY = os.path.join(DEC, 'Scenario', 'Story')
SET = re.compile(r'SetFlag(Up)?\(Flag\.([A-Z0-9_]+)(?:,\s*([A-Za-z0-9]+))?\s*\)')
PARTY = re.compile(r'(?:\bSB_|\b)(JoinParty|LeaveParty)\("(UNIT_MASTER_CH_\w+)"')   # scenes use SB_JoinParty
# Never carried by a jump: battle-local scratch flags, tutorials (pop-ups only), talk flags (NPC lines only),
# the game's own transient state.
SKIP = re.compile(r'^(BATTLE_|TUTORIAL|EV_|IS_TO_BE_CONTINUED|CHANGE_BGM|LOAD_AFTER_EVENT|IN_STAND_BY_AREA|TEST)')


def scene_order(path):
    """Scripts in the order their scenes play: by the scene number in the file name (…_a0_0010, …_c0_1020), then name."""
    nums = re.findall(r'_(\d{3,4})(?=\D*$)', os.path.basename(path))
    return (int(nums[-1]) if nums else 0, os.path.basename(path))


# ---- scene blocks with conditions -------------------------------------------------------------------------------
# A marker's level runs its scene block Scenario/Story/<part>/sb_<level>.lua, which plays scenes with
# require(".../Scene/<scene>")() inside simple conditions on votes and flags. Each operation is kept with the
# conditions around it; the editor evaluates them in story order against the jump's simulated state [read 2026-11-22].
# Condition terms: ["var", NAME, N] (variable == N), ["nvar", NAME, N] (!=), ["flag", NAME, true|false]; None = a
# condition this parser can't read (the operation is then skipped, never guessed).
REQ_SCENE = re.compile(r'require\("Src/Newera_Handling/Scenario/(Story/[\w/]+)"\)\(\)')
OPEN = re.compile(r'^\s*(?:local\s+)?(?:function\b|if\b.*\bthen\s*$|for\b.*\bdo\s*$|while\b.*\bdo\s*$|do\s*$)')


def _term(t, alias):
    t = t.strip().strip('()').strip()
    m = re.fullmatch(r'(\w+)\s*(==|~=)\s*(\d+)', t)
    if m and m.group(1) in alias:
        return ['var' if m.group(2) == '==' else 'nvar', alias[m.group(1)], int(m.group(3))]
    m = re.fullmatch(r'GetSysGlobal\(SysGlobal\.(\w+)\)\s*(==|~=)\s*(\d+)', t)
    if m: return ['var' if m.group(2) == '==' else 'nvar', m.group(1), int(m.group(3))]
    m = re.fullmatch(r'(not\s+)?GetFlag\(Flag\.(\w+)\)(?:\s*==\s*(true|false))?', t)
    if m: return ['flag', m.group(2), (m.group(3) != 'false') != bool(m.group(1))]
    m = re.fullmatch(r'(not\s+)?(\w+)(?:\s*==\s*(true|false))?', t)
    if m and m.group(2) in alias and alias[m.group(2)].startswith('FLAG:'):
        return ['flag', alias[m.group(2)][5:], (m.group(3) != 'false') != bool(m.group(1))]
    return None


def _cond(expr, alias):
    if ' or ' in expr: return None
    terms = [_term(t, alias) for t in expr.split(' and ')]
    return None if any(t is None for t in terms) else terms


def ops_of(path, seen=()):
    """[(op, args, conditions)] of one script, scenes it requires expanded in place. op: on / off / join / leave / uad /
    var. conditions: list of terms, or None inside a block this parser can't read."""
    if path in seen or not os.path.exists(path): return []
    src = open(path, encoding='utf-8', errors='replace').read().split('\n')
    alias, stack, out = {}, [], []                    # stack: condition list per open block (None = unreadable, [] = none)
    def cur():
        c = []
        for s in stack:
            if s is None: return None
            c += s
        return c
    for line in src:
        ln = line.strip()
        if not ln or ln.startswith('--') or ln.startswith('print('): continue
        m = re.match(r'(?:local\s+)?(\w+)\s*=\s*GetSysGlobal\(SysGlobal\.(\w+)\)\s*$', ln)
        if m: alias[m.group(1)] = m.group(2); continue
        m = re.match(r'(?:local\s+)?(\w+)\s*=\s*GetFlag\(Flag\.(\w+)\)\s*$', ln)
        if m: alias[m.group(1)] = 'FLAG:' + m.group(2); continue
        m = re.match(r'if\s+(.+?)\s+then\s*$', ln)
        if m: stack.append(_cond(m.group(1), alias)); continue
        if re.match(r'(elseif\b.*then|else)\s*$', ln):
            if stack: stack[-1] = None                 # the other branches of an if aren't modelled
            continue
        if ln == 'end' or ln.startswith('end)') or ln == 'end,':
            if stack: stack.pop()
            continue
        if OPEN.match(line) and not ln.startswith('if'):
            stack.append([]);
            if re.search(r'\bend\s*$', ln) and ln.startswith('function'): stack.pop()
            continue
        c = cur()
        for up, nm, val in SET.findall(ln):
            if SKIP.match(nm): continue
            if up or val in ('true', 'ON', '1'): out.append(['on', nm, c])
            elif val in ('false', 'OFF', '0'): out.append(['off', nm, c])
        for nm in re.findall(r'SetExclusiveFlag\(Flag\.(\w+)\)', ln): out.append(['on', nm, c])
        for op, uid in PARTY.findall(ln): out.append(['join' if op == 'JoinParty' else 'leave', uid, c])
        for k, n in re.findall(r'SetUAD\("(\w+)",\s*(\d+)\)', ln): out.append(['uad', [k, int(n)], c])
        for k, n in re.findall(r'SetSysGlobal\(SysGlobal\.(\w+),\s*(\d+)\)', ln): out.append(['var', [k, int(n)], c])
        for sc in REQ_SCENE.findall(ln):
            for op, a, cc in ops_of(os.path.join(DEC, 'Scenario', *sc.split('/')) + '.lua', seen + (path,)):
                out.append([op, a, None if c is None or cc is None else c + cc])
    return out


def blocks():
    """{level name: ops} for every scene block sb_<level>.lua (what a marker plays)."""
    out = {}
    for f in glob.glob(os.path.join(STORY, '*', 'sb_*.lua')):
        if re.search(r'(_Test|_test|_old|_OLD|Debug)', os.path.basename(f)): continue
        ops = ops_of(f)
        if ops: out[os.path.basename(f)[3:-4]] = ops
    return out


def map_events():
    """{map event name: ops} for the scenes the world map plays at a story point (MapEventList_*.lua: path_<x> -> Scene
    file; the variable path_<x> is defined in MapEventData / MapEventList as a Scene path)."""
    out = {}
    base = os.path.join(DEC, 'Progress', 'ScenarioProgressData', 'MapEvent')
    paths = {}
    for f in glob.glob(os.path.join(base, '*.lua')):
        t = open(f, encoding='utf-8', errors='replace').read()
        for m in re.finditer(r'(path_\w+)\s*=\s*"([^"]+)"', t): paths[m.group(1)] = m.group(2)
        for m in re.finditer(r'(ev_\w+) = mapEventData\.new\((\w+)', t):
            p = paths.get(m.group(2))
            if not p: continue
            sc = os.path.join(STORY, *p.replace('Story/', '').split('/')) + '.lua' if not p.startswith('Src') else \
                os.path.join(DEC, *p.split('/')[2:]) + '.lua'
            ops = ops_of(sc)
            if ops: out[m.group(1)] = ops
    return out


def parts():
    """Battle and exploration scripts (everything but the scene blocks and their scenes): their flags, switched on and
    then off within the same part (battle scratch state cancels out; route state such as a destroyed bridge stays)."""
    out = {}
    for d in sorted(os.listdir(STORY)):
        if not re.match(r'(ms\d\d[a-z]?_[a-z]+\d+|upd\d+_[a-z]+\d+)$', d): continue
        on, off, party = [], [], []
        for f in sorted(glob.glob(os.path.join(STORY, d, '*.lua')), key=scene_order):
            if re.search(r'(_Test|_test|_old|_OLD|Debug)', os.path.basename(f)) or os.path.basename(f).startswith('sb_'): continue
            t = open(f, encoding='utf-8', errors='replace').read()
            for up, nm, val in SET.findall(t):
                if SKIP.match(nm): continue
                if up or (val in ('true', 'ON', '1')):
                    if nm not in on: on.append(nm)
                elif val in ('false', 'OFF', '0'):
                    if nm not in off: off.append(nm)
        if on or off or party:
            out[d.upper()] = {'on': on, 'off': off, 'party': party}
    return out


def triggers():
    """Progress/TriggerAnchorEvent/Trigger*.lua: what the game runs when the story reaches a point: chapter-start flags
    (SetExclusiveFlag), other flags, per-character attached data (SetUAD: outfit/portrait set per chapter), the chapter's
    shop step (OpenShopFlag), feature unlocks (EnableReleaseFunction; recorded, not applied: their save storage isn't
    mapped) and party changes."""
    out = {}
    for f in sorted(glob.glob(os.path.join(DEC, 'Progress', 'TriggerAnchorEvent', 'Trigger*.lua'))):
        t = open(f, encoding='utf-8', errors='replace').read()
        fns = {m.group(1): m.group(2) for m in re.finditer(r'function (\w+)\(\)(.*?)\nend', t, re.S)}
        for m in re.finditer(r'triggerAnchorEvent\.new\(EScenarioAnchor(SA_\w+),\s*(\w+)\)', t):
            body = fns.get(m.group(2), '')
            on = re.findall(r'SetExclusiveFlag\(Flag\.(\w+)\)', body)
            on += [x[1] for x in SET.findall(body) if (x[0] or x[2] in ('true', 'ON')) and not SKIP.match(x[1])]
            e = {'on': on,
                 'uad': [[a, int(b)] for a, b in re.findall(r'SetUAD\("(\w+)",\s*(\d+)\)', body)],
                 'shop': 'OpenShopFlag()' in body,
                 'release': re.findall(r'EnableReleaseFunction\(EFunctionFlag(\w+)\)', body),
                 'party': [[op, uid] for op, uid in PARTY.findall(body)]}
            if any(e.values()): out[m.group(1)] = e
    return out


def shops():
    src = open(os.path.join(DEC, 'Scenario', 'CommonDef', 'ShopFlagList.lua'), encoding='utf-8', errors='replace').read()
    funcs = {}
    for m in re.finditer(r'function (OpenShopFlag_MS(\w+))\(\)(.*?)\nend', src, re.S):
        body = m.group(3)
        flags = [x[1] for x in SET.findall(body) if (x[0] or x[2] in ('true', 'ON')) and not SKIP.match(x[1])]
        calls = re.findall(r'(OpenShopFlag_MS\w+)\(\)', body)
        funcs[m.group(1)] = (m.group(2), flags, calls)
    def expand(fn, seen=()):
        sfx, flags, calls = funcs[fn]
        out = list(flags)
        for c in calls:
            if c in funcs and c not in seen: out += [f for f in expand(c, seen + (fn,)) if f not in out]
        return out
    res = []
    for fn, (sfx, _, _) in funcs.items():
        ch = int(re.match(r'(\d+)', sfx).group(1))
        res.append([ch, sfx, expand(fn)])
    return sorted(res)


def main():
    data = json.load(open(OUT, encoding='utf-8'))
    icon_rows = json.load(open(os.path.join(ROOT, 'data/tables/GOP_World_Icon.json'), encoding='utf-8'))
    icon_rows = icon_rows.get('rows', icon_rows)
    ex = {ic: (r.get('WorldIconEndFlagEx') or '').replace('Flag.', '') for ic, r in icon_rows.items()
          if r.get('WorldIconEndFlagEx')}
    P = parts()
    TR = triggers()
    B, M = blocks(), map_events()
    level_icon = {(r.get('LevelName') or '').lower(): ic for ic, r in icon_rows.items() if r.get('LevelName')}
    # The map events each story point plays (first definition in the game's load order, as GetScenarioProgressData).
    import make_story_data as msd
    anchor_mev = {}
    for f in msd.loaded_files():
        t = open(f, encoding='utf-8', errors='replace').read()
        for m in re.finditer(r'local mapEvent = \{([^}]*)\}.*?(SA_\w+) = progressData\.new', t, re.S):
            anchor_mev.setdefault(m.group(2), re.findall(r'ev_\w+', m.group(1)))
    data['forward'] = {'parts': P, 'triggers': TR, 'shops': shops(), 'icon_end_ex': ex, 'blocks': B, 'map_events': M,
                       'icon_level': {ic: lv for lv, ic in level_icon.items() if lv in B},
                       'anchor_map_events': {a: [e for e in evs if e in M] for a, evs in anchor_mev.items()
                                             if any(e in M for e in evs)},
                       # Recommended level of each chapter part's main battle (first playthrough), for "raise the party".
                       'rec_level': {re.sub(r'^WORLD_ICON_', '', ic).rsplit('_PART_BATTLE', 1)[0]: r.get('RecLevel')
                                     for ic, r in icon_rows.items() if '_PART_BATTLE_01' in ic and r.get('RecLevel')}}
    n_ops = sum(len(v) for v in B.values()) + sum(len(v) for v in M.values())
    n_unk = sum(1 for v in list(B.values()) + list(M.values()) for o in v if o[2] is None)
    print(len(B), 'scene blocks,', len(M), 'map events,', n_ops, 'operations,', n_unk, 'with unreadable conditions')
    json.dump(data, open(OUT, 'w', encoding='utf-8', newline='\n'), ensure_ascii=False, indent=0)
    print(len(P), 'parts;', sum(len(p['on']) for p in P.values()), 'flags on,', sum(len(p['off']) for p in P.values()),
          'off,', sum(len(p['party']) for p in P.values()), 'party changes;', len(data['forward']['shops']), 'shop steps;',
          len(ex), 'ever-done flags;', len(TR), 'anchor triggers,', sum(len(e['uad']) for e in TR.values()),
          'attached-data sets,', sum(len(e['party']) for e in TR.values()), 'trigger party changes')


if __name__ == '__main__':
    main()
