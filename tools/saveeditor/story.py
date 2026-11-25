"""Story position for the save editor.

The save keeps the story position in the script variable SCENARIO_ANCHOR: an index into the game's
EScenarioAnchor enum (486 story points, SA_<chapter part>_<point>). Loading a save never runs the game's
story-progress code: the game resumes the saved level, and the world map shows the marker lists **stored in the save**.
So changing the anchor alone does nothing [tested 2026-11-21, Tests 43-43c].

The warp below (rebuilt 2026-11-22) is the recipe that worked in game (Test 43c, slot 3 v4: right before the Ch.17
regiment split):
  1. SCENARIO_ANCHOR = the target story point;
  2. both stored world-map marker lists: the story markers replaced by the target's markers (+ its follow-event
     markers), character-story markers kept;
  3. resume on the world map: level/time records cleared, the location block set to the game's world-map form;
  4. story flags: the end flags of the target's markers and of markers that only come later, plus every flag of chapter
     parts that only come later (route-aware, from the story graph), set to 0. Earlier flags stay, so the run's history
     (choices, votes, routes) is kept. The game's protected list (chapter start/end, _EX "ever done") is kept, as the
     game's own warp keeps it;
  5. the load-screen title (cosmetic; the game rewrites it on its next save).
Only story points with their own world-map marker can be targets: points that play on their own (auto events,
narration, no-world) give an empty map (Test 43c soft lock). Data: story_data.json (make_story_data.py).
The party, items and unit availability are not changed: going back keeps everyone who has joined; going forward skips
the story's joins, events and flags (Dangerous).
"""
import json, os, re, struct
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
_DATA = None


def _data():
    global _DATA
    if _DATA is None: _DATA = json.load(open(os.path.join(HERE, 'story_data.json'), encoding='utf-8'))
    return _DATA


def anchors():
    return _data()['anchors']


def protected_flags():
    return set(_data()['exclusive_flags'])


def part_key(anchor):
    """SA_MS17_H01_HD010 -> MS17_H01 ; SA_UPD01_H01_HD010 -> UPD01_H01 ; SA_GAME_END -> GAME_END."""
    m = re.match(r'SA_([A-Z]+\d+[A-Z]?_[A-Z]+\d+)', anchor)
    return m.group(1) if m else anchor[3:] if anchor.startswith('SA_') else anchor


def chapter_no(anchor):
    m = re.match(r'SA_MS(\d+)', anchor)
    return int(m.group(1)) if m else None


def chapters(T):
    """[(chapter number or label, [(part key, title, [ (index, anchor) ])])] in story order."""
    titles = {}
    for rid, r in T.rows.get('GOP_StoryChartTable', {}).items():
        m = re.match(r'CHAPTER_START_(.+)', r.get('StartFlagName') or '')
        if not m: continue
        t = T.text.get(r.get('TitleTextId'), ''); sub = T.text.get(r.get('SubTitleTextId'), '')
        titles[m.group(1)] = (t + (' – ' + sub if sub else '')).strip(' –')
    groups = {}
    for i, a in enumerate(anchors()):
        if a == 'NONE': continue
        groups.setdefault(part_key(a), []).append((i, a))
    out = {}
    for key, items in groups.items():
        n = roman_chapter(titles.get(key, '')) or chapter_no(items[0][1])
        label = f'Chapter {n}' if n else ('Extra story' if key.startswith('UPD') else 'Other')
        out.setdefault(label, []).append((key, titles.get(key, ''), items))
    def order(label):
        m = re.match(r'Chapter (\d+)', label)
        return (0, int(m.group(1))) if m else (1, label)
    return [(lb, sorted(out[lb], key=lambda g: g[2][0][0])) for lb in sorted(out, key=order)]


ROMAN = {'I': 1, 'V': 5, 'X': 10, 'L': 50}


def roman_chapter(title):
    """'Chapter XVIII, Part I – …' -> 18 (the game's own chapter numbering, which differs from the MS number on
    some routes, e.g. MS17S_X38 is Chapter XVIII)."""
    m = re.match(r'Chapter ([IVXL]+)', title or '')
    if not m: return None
    v = [ROMAN[c] for c in m.group(1)]
    return sum(-a if i + 1 < len(v) and a < v[i + 1] else a for i, a in enumerate(v))


def describe(index, T=None):
    """Readable story position: 'Chapter XIX – The Fortress That Is Faith  (MS20S_X47, point RS010)'."""
    a = anchors()
    if not 0 <= index < len(a): return f'{index} (not a story point)'
    key = part_key(a[index]); point = a[index][3 + len(key) + 1:] if a[index].startswith('SA_' + key) else ''
    if T is not None:
        for lb, groups in chapters(T):
            for k, title, items in groups:
                if k == key:
                    head = title or lb
                    return f'{head}  ({key}' + (f', point {point})' if point else ')')
    n = chapter_no(a[index])
    return (f'Chapter {n}  ' if n else '') + f'({a[index][3:]})'


# ------------------------------------------------------------------------------------------------ story warp
RESUME_VARS = ('TRANSITION_LEVEL_RECORD', 'TRANSITION_LEVEL_MAP_TIME', 'MAIN_LEVEL_RECORD_BEFORE_QUEST',
               'MAIN_LEVEL_MAP_TIME_BEFORE_QUEST')


def points():
    return _data().get('points', {})


def is_target(index):
    """A story point the warp can go to: it has its own world-map marker(s) (type MARKER)."""
    a = anchors()
    if not 0 < index < len(a): return False
    p = points().get(a[index])
    return bool(p and p['type'] == 'MARKER' and p['icons'])


def point_kind(index):
    p = points().get(anchors()[index]) if 0 <= index < len(anchors()) else None
    if p is None: return 'no story data'
    return {'MARKER': 'map marker' if p['icons'] else 'no marker', 'ANCHOR_AUTO_EVENT': 'plays on its own',
            'ANCHOR_NARRATION': 'narration', 'ANCHOR_NO_WORLD': 'no world map'}.get(p['type'], p['type'])


def _graph():
    nxt = {a: p['next'] for a, p in points().items()}
    prev = {}
    for a, ns in nxt.items():
        for n in ns: prev.setdefault(n, []).append(a)
    return nxt, prev


def _reach(start, edges):
    seen, q = {start}, deque([start])
    while q:
        for n in edges.get(q.popleft(), []):
            if n not in seen: seen.add(n); q.append(n)
    return seen


def _part_re(key):
    """Flags name a chapter part with or without its route letter: MS17S_X38 or MS17_X38 (part numbers X## are
    unique across routes) [read: MS17_X38_BURNED_EVEN_ONE_GIMMICK]."""
    alts = {re.escape(key), re.escape(re.sub(r'^(MS\d\d)[A-Z]_', r'\1_', key))}
    return re.compile(r'(^|_)(' + '|'.join(sorted(alts)) + r')(_|$)')


def icon_lists(s1):
    """The stored world-map marker lists: int32 count + that many 'WORLD_ICON_*' FStrings, back to back (two in a
    v1.1.0 save) [read 2026-11-22]. Returns [(count_at, end, names)]."""
    b = bytes(s1); runs = []
    for m in re.finditer(rb'WORLD_ICON_[A-Z0-9_]+\x00', b):
        st = m.start() - 4
        if st < 4 or struct.unpack_from('<i', b, st)[0] != m.end() - m.start(): continue
        if runs and runs[-1][1] == st: runs[-1][1] = m.end(); runs[-1][2].append(b[st + 4:m.end() - 1].decode())
        else: runs.append([st - 4, m.end(), [b[st + 4:m.end() - 1].decode()]])
    return [(c, e, n) for c, e, n in runs if struct.unpack_from('<i', b, c)[0] == len(n)]


def warp_plan(save, index, T=None):
    """What the warp would change, without changing anything. Raises ValueError if the target can't be used."""
    A = anchors()
    if not is_target(index):
        raise ValueError(f'{A[index] if 0 <= index < len(A) else index}: this story point has no world-map marker of '
                         f'its own ({point_kind(index) if 0 <= index < len(A) else "unknown"}). Pick a point marked "map marker".')
    target = A[index]
    cur_i = save.sysvar('SCENARIO_ANCHOR')['value']
    cur = A[cur_i] if 0 <= cur_i < len(A) else None
    nxt, prev = _graph()
    after = _reach(target, nxt)                  # the target and everything that can follow it
    before = _reach(target, prev) - after        # everything that can lead to it
    if cur == target: direction = 'same point'
    elif cur in after: direction = 'back'
    elif cur in before: direction = 'forward'
    else: direction = 'other route'
    if direction == 'back' and part_key(target) != part_key(cur or ''):
        # Routes split and rejoin (Ch.10 A/B, Ch.17 B/R/F/S), so "the current point can follow the target" doesn't mean
        # this run went through it. A part this run played has marker-done flags on (WI_END_<part>_…, not the _EX
        # "ever done" copies that NG+ keeps) [read 2026-11-22: Golden save MS10A 4 on, MS10B 0].
        pr = _part_re(part_key(target))
        if not any(v and nm.startswith('WI_END_') and not nm.endswith('_EX') and pr.search(nm)
                   for nm, at, v in save.flags['entries']):
            direction = "a branch this run didn't take"

    follow = [f['icon'] for f in _data().get('follow_markers', []) if f['lo'] <= index <= f['hi']]
    new_story = list(points()[target]['icons']) + follow
    lists = icon_lists(save.s1)
    if not lists: raise ValueError("the save's world-map marker lists weren't found")

    ends = _data().get('icon_end_flags', {})
    before_icons = {i for a in before for i in points().get(a, {}).get('icons', [])}
    off = {ends[i] for i in new_story if i in ends}
    off |= {ends[i] for a in after for i in points().get(a, {}).get('icons', []) if i in ends and i not in before_icons}
    later_parts = {part_key(a) for a in after} - {part_key(a) for a in before}
    pats = [_part_re(k) for k in later_parts]
    keep = protected_flags()
    flags_off = []
    for nm, at, v in save.flags['entries']:
        if not v or nm in keep or nm.endswith('_EX'): continue
        if nm in off or any(p.search(nm) for p in pats): flags_off.append(nm)

    title = None
    if T is not None:
        for r in T.rows.get('GOP_StoryChartTable', {}).values():
            if r.get('StartFlagName') == 'CHAPTER_START_' + part_key(target):
                title = (r.get('TitleTextId'), r.get('SubTitleTextId')); break
    from .checks import RISKY, DANGER
    status = RISKY if direction in ('back', 'same point') else DANGER
    return {'index': index, 'target': target, 'current': cur, 'direction': direction, 'status': status,
            'markers': new_story, 'lists': len(lists), 'flags_off': sorted(flags_off), 'title': title}


def set_preview_title(save, title_id, subtitle_id):
    """The load screen shows the chapter from two text ids near the end of the preview section s0:
    TEXT_COMMON_STORY_TITLE_<ch>_<n> ("Chapter XVII") and TEXT_COMMON_STORY_SUBTITLE_<part>_<n> (the part's name),
    which the game writes together from one GOP_StoryChartTable row; only 5 fixed bytes follow them [read 2026-11-22,
    game-made saves]. Both are replaced (the subtitle can change length, so s0's size field is updated). Cosmetic:
    the game rewrites them on its next save. Returns True if both were found and set."""
    import tssave
    if not (title_id and subtitle_id and title_id != 'None' and subtitle_id != 'None'): return False
    plain = save.plaintext(); (a0, n0) = tssave.sections(plain)[0][0]
    h = bytes(save.head)
    if a0 + n0 != len(h): return False
    s0 = h[a0:a0 + n0]; out = s0
    for kind, new in (('TITLE', title_id), ('SUBTITLE', subtitle_id)):
        found = [m for m in re.finditer(rb'TEXT_COMMON_STORY_' + kind.encode() + rb'_[A-Z0-9_]+\x00', out)
                 if struct.unpack_from('<i', out, m.start() - 4)[0] == m.end() - m.start()]
        if len(found) != 1: return False
        m = found[0]; b = new.encode() + b'\x00'
        out = out[:m.start() - 4] + struct.pack('<i', len(b)) + b + out[m.end():]
    save.head = h[:a0 - 4] + struct.pack('<i', len(out)) + out
    return True


def set_position(save, index, status, T=None):
    """Story warp to a marker point (module docstring). Applies warp_plan()."""
    from . import model
    plan = warp_plan(save, index, T)
    save.set_sysvar('SCENARIO_ANCHOR', index, status)
    for nm in plan['flags_off']:
        at, _ = save.flag(nm); save.s1[at:at + 4] = b'\x00\x00\x00\x00'
    story_icons = {i for p in points().values() for i in p['icons']} | {f['icon'] for f in _data().get('follow_markers', [])}
    for k in range(plan['lists']):
        c, e, names = icon_lists(save.s1)[k]
        new = plan['markers'] + [n for n in names if n not in story_icons]
        save.s1[c:e] = struct.pack('<i', len(new)) + b''.join(model.fstring(n) for n in new)
    save.reparse()
    for k in RESUME_VARS:
        try:
            if save.sysvar(k)['is_str']: save.set_sysvar(k, '', status)
        except KeyError:
            pass
    L = save.parts['location']
    save.splice(L['at'], L['end'], bytes.fromhex(_data()['worldmap_location_hex']), 'resume on the world map', status)
    if plan['title']:
        set_preview_title(save, *plan['title'])
    save.history.append((f"story warp to {plan['target']} ({plan['direction']}): markers {', '.join(plan['markers'])}; "
                         f"{len(plan['flags_off'])} later story flags cleared", status))
    return plan


# ------------------------------------------------------------------------------------------------ forward jump
# Research 2026-11-22 (mods/TESTING.md "Forward story jump"). Going forward, the plain warp above skips everything the
# story does in between. forward_plan() replays what can be read from the game's scripts along the chosen path:
#   - branch points: a story point whose next list starts with a script variable (the 12 votes, and the exploration
#     outcomes MS10B_H01_RESERCH_01_SUCCESS / MS11_X21_RESEARCH_01_SUCCESS / ...) continues with next[value]
#     (ProgressData.get_next_scenario_anchor) [read];
#   - every marker passed: its end flag and its "ever done" (_EX) flag (the game sets both when a marker is done);
#   - each chapter part passed: CHAPTER_END_<part>; its scripts' flags switched on, then the ones the same part switches
#     off (drops battle-scratch state, keeps world-map changes such as a destroyed bridge); its party joins and
#     departures in scene order (unit record byte -7: 1 in the party, 2 left; EPartyMember) [read];
#   - each anchor trigger reached (Progress/TriggerAnchorEvent): its flags (CHAPTER_START_<part>), attached data
#     (map "unit data A": outfit/portrait sets per chapter) and the chapter's shop step (ShopFlagList, cumulative);
#   - the chosen branch values are written to their variables.
# Not replayed: talk flags, tutorials, conviction, items, gold, levels, feature unlocks (EnableReleaseFunction: their save
# storage isn't mapped; all happen by Chapter 3), in-scene dialogue choices.
PARTY_STATE_AT = -7          # byte offset from a unit record's end: 0 never joined, 1 in the party, 2 left [read]


def _fwd():
    return _data().get('forward', {})


def branch_points():
    """{anchor: variable} for every story point whose next point depends on a script variable."""
    return {a: p['vote'] for a, p in points().items() if p.get('vote')}


def forward_path(start, target, choices):
    """Story points from start to target, following choices {variable: value}. Returns (path, pending) where pending lists
    [(anchor, variable, [(value, next anchor, reaches target)])] for branch points not settled by choices: a branch with
    exactly one option that leads to the target is settled automatically."""
    nxt, _ = _graph()
    path, cur, pending, seen = [start], start, [], {start}
    while cur != target:
        p = points().get(cur)
        if not p or not p['next']: return path, pending
        if p.get('vote') and len(p['next']) > 1:
            opts = [(i, n, target in _reach(n, nxt)) for i, n in enumerate(p['next'])]
            var = p['vote']
            if var in choices and 0 <= choices[var] < len(p['next']):
                cur = p['next'][choices[var]]
            else:
                good = [o for o in opts if o[2]]
                if len(good) == 1:
                    choices[var] = good[0][0]; cur = good[0][1]
                else:
                    pending.append((cur, var, opts)); return path, pending
        else:
            cur = p['next'][0]
        if cur in seen: return path, pending
        seen.add(cur); path.append(cur)
    return path, pending


def branch_decisions(save, index, choices=None):
    """Resolve the path to a target with defaults and return (path, decisions, choices): decisions = [(anchor, variable,
    [(value, next anchor, reaches target)], chosen value)] for every branch point on the path. Default per branch: the
    given choice, else the save's current value if that option leads to the target, else the first option that does."""
    A = anchors(); nxt, _ = _graph()
    start, target = A[save.sysvar('SCENARIO_ANCHOR')['value']], A[index]
    choices = dict(choices or {})
    cur_vals = {e['name']: e['value'] for e in save.sysvars['entries'] if not e['is_str']}
    decisions, cur, path, seen = [], start, [start], {start}
    while cur != target:
        p = points().get(cur)
        if not p or not p['next']: break
        if p.get('vote') and len(p['next']) > 1:
            var = p['vote']
            opts = [(i, n, target in _reach(n, nxt)) for i, n in enumerate(p['next'])]
            if var in choices and 0 <= choices[var] < len(opts): v = choices[var]
            elif cur_vals.get(var) is not None and 0 <= cur_vals[var] < len(opts) and opts[cur_vals[var]][2]: v = cur_vals[var]
            else: v = next((o[0] for o in opts if o[2]), 0)
            choices[var] = v; decisions.append((cur, var, opts, v)); cur = p['next'][v]
        else:
            cur = p['next'][0]
        if cur in seen: break
        seen.add(cur); path.append(cur)
    return path, decisions, choices


def _shop_flags(target):
    """The cumulative shop unlocks for the target's chapter (ShopFlagList: the highest step at or below it; the
    _S step only on the Golden route)."""
    ch = chapter_no(target) or 0
    best = []
    for c, sfx, flags in _fwd().get('shops', []):
        if c > ch: continue
        if sfx.endswith('_S') and not re.match(r'SA_MS\d\dS_', target): continue
        best = flags
    return best


def forward_plan(save, index, choices=None):
    """What a forward jump would change (nothing is changed). choices: {variable: value} for branch points. Raises
    ValueError when the target can't be reached from the save's position or a branch still needs a choice (the message
    lists it); the plan's 'pending' is then also on the exception (.pending)."""
    A = anchors()
    if not is_target(index):
        raise ValueError(f'{A[index]}: not a story point with its own world-map marker ({point_kind(index)}).')
    cur_i = save.sysvar('SCENARIO_ANCHOR')['value']
    if not 0 <= cur_i < len(A) or A[cur_i] not in points():
        raise ValueError('the save is not at a known story point')
    start, target = A[cur_i], A[index]
    choices = dict(choices or {})
    path, pending = forward_path(start, target, choices)
    if pending:
        e = ValueError('choose how the story goes at: ' + '; '.join(f'{a} ({v})' for a, v, _ in pending))
        e.pending = pending; e.choices = choices; raise e
    if path[-1] != target:
        raise ValueError(f'{target} can\'t be reached forward from {start} (it is behind, or on another route).')
    sim = _simulate(save, path, choices)
    cur_flags = {n: v for n, _, v in save.flags['entries']}
    on = sorted(n for n, v in sim['flags'].items() if v and not cur_flags.get(n))
    off = sorted(n for n, v in sim['flags'].items() if not v and cur_flags.get(n))
    recs = dict((u, (s, e)) for u, s, e in save.unit_recs)
    party_changes = []
    for uid, st in sim['party'].items():
        if uid not in recs: continue
        old = save.s1[recs[uid][1] + PARTY_STATE_AT]
        if old != st: party_changes.append((uid, old, st))
    var_changes = []
    for var, val in sim['vars'].items():
        try:
            if save.sysvar(var)['value'] != val: var_changes.append((var, save.sysvar(var)['value'], val))
        except KeyError:
            pass
    uad_map = {k: v for k, _, v in save.map_by_label('unit data A')['entries']}
    uad_changes = [(k, uad_map.get(k), v) for k, v in sim['uad'].items() if uad_map.get(k) != v]
    return {'index': index, 'start': start, 'target': target, 'path': path, 'choices': choices,
            'flags_on': on, 'flags_off': off, 'party': party_changes, 'vars': var_changes,
            'uad': uad_changes, 'parts': sim['parts'], 'shops': _shop_flags(target), 'skipped': sim['skipped']}


def _main_cast_outfits(path):
    """Outfit / portrait sets (attached data) of the main cast P001-P008 for the target's chapter, by the game's own
    rule for story-battle replays (UnitAttachedDataCommon.AllUpdateStoryBattleReplayUAD: chapter = MS number, box = the
    part's X number) [read]. Matches the natural Golden Ch.19 save for these eight; not used for the others, where the
    replay rule differs from what the story sets (P013: rule 3, story 2)."""
    m = None
    for a in reversed(path):
        m = re.match(r'SA_MS(\d\d)[A-Z]?_X(\d+)', a)
        if m: break
    if not m: return {}
    ch, box = int(re.match(r'SA_MS(\d\d)', path[-1]).group(1)) if re.match(r'SA_MS(\d\d)', path[-1]) else int(m.group(1)), int(m.group(2))
    g = (box in (39, 43))
    p1 = 0 if box < 2 else 1 if ch < 12 else 4 if g else 2
    p2 = 0 if ch < 9 else 1 if ch < 15 else 6 if box in (40, 44) else 2
    p4 = 0 if ch < 2 else 2 if ch < 12 else 4 if g else 1
    p5 = 0 if ch < 2 else 5 if g else 2
    v = {'P001': p1, 'P002': p2, 'P003': 3 if g else 0, 'P004': p4, 'P005': p5, 'P006': 1 if g else 0,
         'P007': 2 if g else 0, 'P008': 2 if g else 0}
    return {f'UNIT_ATTACHED_DATA_SET_{k}': n for k, n in v.items()}


def _simulate(save, path, choices):
    """Replay the path in story order on a copy of the save's state (flags, variables, party, attached data): at each
    point its trigger, its map-event scenes, then (points passed, not the target) each marker's scene block and the
    marker's end flags; when a chapter part is left, CHAPTER_END_<part> and the part's battle-script flags. Operations
    are evaluated against this simulated state; ones under conditions the generator couldn't read are skipped (counted)."""
    F = _fwd(); ex = F.get('icon_end_ex', {}); ends = _data().get('icon_end_flags', {})
    names = {n for n, _, _ in save.flags['entries']}
    flags = {n: bool(v) for n, _, v in save.flags['entries']}
    changed_flags, vars_ = {}, {e['name']: e['value'] for e in save.sysvars['entries'] if not e['is_str']}
    vars_.update(choices)
    changed_vars = dict(choices)
    party, uad, skipped, done_parts = {}, {}, 0, []

    def setf(nm, v):
        if nm in names: flags[nm] = v; changed_flags[nm] = v

    def ok(cond):
        for kind, nm, val in cond:
            if kind == 'var' and vars_.get(nm) != val: return False
            if kind == 'nvar' and vars_.get(nm) == val: return False
            if kind == 'flag' and bool(flags.get(nm)) != bool(val): return False
        return True

    def run(ops):
        nonlocal skipped
        for op, arg, cond in ops:
            if cond is None: skipped += 1; continue
            if not ok(cond): continue
            if op == 'on': setf(arg, True)
            elif op == 'off': setf(arg, False)
            elif op == 'join': party[arg] = 1
            elif op == 'leave': party[arg] = 2
            elif op == 'uad': uad[arg[0]] = arg[1]
            elif op == 'var': vars_[arg[0]] = arg[1]; changed_vars[arg[0]] = arg[1]

    def finish_part(k):
        setf('CHAPTER_END_' + k, True)
        pp = F.get('parts', {}).get(k) or F.get('parts', {}).get(re.sub(r'^(MS\d\d)[A-Z]_', r'\1_', k))
        if pp:
            for fl in pp['on']: setf(fl, True)
            for fl in pp['off']: setf(fl, False)
        done_parts.append(k)

    trig, blocks, mevs = F.get('triggers', {}), F.get('blocks', {}), F.get('map_events', {})
    icon_level, a_mev = F.get('icon_level', {}), F.get('anchor_map_events', {})
    target = path[-1]
    for i, a in enumerate(path):
        t = trig.get(a)
        if t:
            run([['on', fl, []] for fl in t['on']] + [['uad', u, []] for u in t['uad']] +
                [['join' if op == 'JoinParty' else 'leave', uid, []] for op, uid in t['party']])
        if a == target: break
        for ev in a_mev.get(a, []): run(mevs.get(ev, []))
        for ic in points().get(a, {}).get('icons', []):
            lv = icon_level.get(ic)
            if lv: run(blocks.get(lv, []))
            for fl in (ends.get(ic), ex.get(ic)):
                if fl: setf(fl, True)
        nxt = path[i + 1]
        if part_key(nxt) != part_key(a) and part_key(a) not in done_parts: finish_part(part_key(a))
    for fl in _shop_flags(target): setf(fl, True)
    uad.update(_main_cast_outfits(path))
    return {'flags': changed_flags, 'vars': {k: v for k, v in changed_vars.items()}, 'party': party, 'uad': uad,
            'parts': done_parts, 'skipped': skipped}


def recommended_level(target):
    """The first-playthrough recommended level of the target's chapter part battle (GOP_World_Icon RecLevel), or of the
    nearest earlier part that has one."""
    rl = _fwd().get('rec_level', {})
    key = part_key(target)
    if rl.get(key): return rl[key]
    best = None
    for a in anchors():
        k = part_key(a)
        if rl.get(k): best = rl[k]
        if a == target: break
    return best


def recruit_candidates(save):
    """Playable units (UNIT_MASTER_CH_P0xx) with a record who have never joined (party state 0)."""
    out = []
    for uid, s, e in save.unit_recs:
        if re.match(r'UNIT_MASTER_CH_P0\d\d$', uid) and save.s1[e + PARTY_STATE_AT] == 0: out.append(uid)
    return out


# The game's own join (Scenario/CommonDef/ScenarioBlockJoinParty.lua) [read]: a unit already in the party is skipped;
# the late recruits are raised to the last main battle's recommended level (Avlora +2, capped at 50) and promoted to
# their second-rank class; Rudolph, Corentin and Milo only join (they were levelled as guests in their battle); the
# Chapter 1-2 cast gets level 1 or 2 on a first playthrough.
JOIN_PROMOTES = {f'UNIT_MASTER_CH_P{i:03d}' for i in [11] + list(range(13, 31))}
JOIN_LEVEL_BONUS = {'UNIT_MASTER_CH_P016': 2}


def recruit_now(save, T, uids, level, status):
    """Put never-joined base-game units in the party where the save is now, as the game's own join would: party state 1,
    then (with level) each one below the level is raised to it (EXP 0) and the late recruits get their second-rank
    class, and they learn their class moves up to that level. Returns [(uid, old level, new level, new class or None)].
    Story safety: an NG+ save starts with every unit in the party, so every story script runs with them present, and
    the story's later join of an added unit does nothing (ScenarioBlockJoinParty returns if IsPartyIn)."""
    from . import features
    done = []
    for uid in uids:
        s, e = save.unit_record(uid)
        if save.s1[e + PARTY_STATE_AT] != 0: continue          # only never-joined units; "left" (2) is the story's call
        save.s1[e + PARTY_STATE_AT] = 1
        done.append(uid)
    out = []
    for uid in done:
        info = save.unit_info(uid)
        old = new = info['stats']['level']; cls = None
        if level:
            target = min(50, int(level) + JOIN_LEVEL_BONUS.get(uid, 0))
            if old < target:
                save.set_unit_stat(uid, 'level', target, status); save.set_unit_stat(uid, 'exp', 0, status); new = target
            job = info['jobs'][0] if info['jobs'] else None
            if T is not None and uid in JOIN_PROMOTES and job and features.demote_target(T, job) is None:
                nxt = features.promote_targets(T, job)
                if nxt:
                    save.replace_in_unit(uid, job, nxt[0], status); cls = nxt[0]
            if T is not None: features.learn_all(save, T, uid, status)
        out.append((uid, old, new, cls))
    save.reparse()
    save.history.append((f"recruited {len(out)} base-game unit(s) now: " + ', '.join(u[15:] for u, *_ in out)
                         + (f", level {level}" if level else ''), status))
    return out


def forward_jump(save, index, choices, status, T=None, recruits=(), level=None, keep_party=False):
    """Apply forward_plan(), then the story warp (position, markers, resume, title). Options: recruits = unit ids to put
    in the party (side characters the story would have offered); level = raise every party member below it to it
    (EXP 0; stats are rebuilt from the tables at battle start) and teach the class moves up to that level; keep_party =
    skip the story's departures for units in the party now (e.g. Roland, who leaves after the Chapter 1 battle and
    rejoins in Chapter 2's second exploration; an NG+ save starts with everyone in the party)."""
    plan = forward_plan(save, index, choices)
    if keep_party:
        plan['party'] = [p for p in plan['party'] if not (p[1] == 1 and p[2] == 2)]
    for var, _, val in plan['vars']:
        save.set_sysvar(var, val, status)
    for nm in plan['flags_on']:
        at, _ = save.flag(nm); save.s1[at:at + 4] = struct.pack('<i', 1)
    for nm in plan['flags_off']:
        at, _ = save.flag(nm); save.s1[at:at + 4] = b'\x00\x00\x00\x00'
    recs = dict((u, (s, e)) for u, s, e in save.unit_recs)
    for uid, _, st in plan['party']:
        s, e = recs[uid]; save.s1[e + PARTY_STATE_AT] = st
    for k, _, v in plan['uad']:
        save.set_map_value('unit data A', k, v, status)
    save.reparse()
    recs = dict((u, (s, e)) for u, s, e in save.unit_recs)
    for uid in recruits:
        if uid in recs: save.s1[recs[uid][1] + PARTY_STATE_AT] = 1
    plan['recruited'] = [u for u in recruits if u in recs]
    plan['levelled'] = []
    if level:
        from . import features
        save.reparse()
        for uid in [u for u, _, _ in save.unit_recs]:
            s, e = save.unit_record(uid)                # fresh: teaching moves grows records and shifts the later ones
            if save.s1[e + PARTY_STATE_AT] != 1: continue
            if save.unit_info(uid)['stats']['level'] < level:
                save.set_unit_stat(uid, 'level', int(level), status); save.set_unit_stat(uid, 'exp', 0, status)
                if T is not None: features.learn_all(save, T, uid, status)
                plan['levelled'].append(uid)
    save.reparse()
    save.history.append((f"forward jump {plan['start']} -> {plan['target']}: {len(plan['path']) - 1} story points, "
                         f"{len(plan['flags_on'])} flags on, {len(plan['flags_off'])} off, {len(plan['party'])} party "
                         f"changes, {len(plan['uad'])} attached-data sets, branch values {plan['choices']}", status))
    set_position(save, index, status, T)
    return plan
