"""Developer script: add the story-warp data to story_data.json (the editor ships without the game's scripts).

Reads (game v1.1.0):
  - decompiled/Newera_Handling/Progress/ScenarioProgressData/*.lua: for every story point (anchor) its world-map
    markers (iconList), its type (default = player picks a marker; ANCHOR_AUTO_EVENT / ANCHOR_NARRATION /
    ANCHOR_NO_WORLD play on their own) and the points that can follow it (nextScenarioIDList; a leading
    SysGlobal.VOTE_* entry means "chosen by that vote").
  - data/tables/GOP_World_Icon.json: each marker's end flag (WorldIconEndFlag), set when the marker is done.
Adds to story_data.json (keeps 'anchors' and 'exclusive_flags'):
  - points: {anchor: {"type", "icons", "next"}}
  - follow_markers: [{"icon", "lo", "hi"}] (FollowEvent/*.lua: extra markers shown while the position is in a range)
  - icon_end_flags: {icon: flag}
  - worldmap_location_hex: the save's location block as the game writes it on the world map (no field actor,
    zero position; taken from a game-made world-map save) [tested 2026-11-22 as part of the slot 3 v4 recipe].
Run from the repository root:  python tools/saveeditor/make_story_data.py
"""
import glob, json, os, re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
OUT = os.path.join(os.path.dirname(__file__), 'story_data.json')
WORLDMAP_LOCATION_HEX = ('050000004e6f6e65000000000000000000000000000000803f0000000000000000000000000000803f0000803f'
                         '0000803f00000000000000000000000000050000004e6f6e6500050000004e6f6e6500ffffffff000000000000000000')

ASSIGN = re.compile(r'^\s*(?:local )?(iconList|mapEvent|releaseFlagList|nextScenarioIDList) = (\{.*?\})', re.S | re.M)
NEW = re.compile(r'(SA_\w+) = progressData\.new\(EScenarioAnchor(SA_\w+), iconList, mapEvent, releaseFlagList, '
                 r'nextScenarioIDList(?:, (\w+))?\)')
CONDITIONAL_ICONS = []


def parse_file(src):
    """Each progressData.new uses the values assigned since the previous one. Some blocks assign the next-point list
    again inside `if` (edition checks: the trial ends the game, the full game goes on), so the next points are the union
    of every assignment in the block [read: ScenarioProgressData_MS03_X04 BT920]."""
    out, start = {}, 0
    for m in re.finditer(r'(\w+) = progressData\.new\(EScenarioAnchor(\w+), iconList, mapEvent, releaseFlagList, '
                         r'nextScenarioIDList(?:, (\w+))?\)', src):
        seg = src[start:m.start()]; start = m.end()
        if not m.group(2).startswith('SA_'): continue          # trial-edition points (TRIAL_01_SA_…) end a block too
        got = {}
        for a in ASSIGN.finditer(seg): got.setdefault(a.group(1), []).append(a.group(2))
        icon_vals = got.get('iconList', ['{}'])
        if len(icon_vals) > 1: CONDITIONAL_ICONS.append(m.group(2))
        icons = re.findall(r'"(WORLD_ICON_\w+)"', icon_vals[0])
        nxt = []
        for v in got.get('nextScenarioIDList', []):
            for n in re.findall(r'EScenarioAnchor(SA_\w+)', v):
                if n not in nxt: nxt.append(n)
        vote = re.search(r'SysGlobal\.(\w+)', ' '.join(got.get('nextScenarioIDList', [])))
        out[m.group(2)] = {'type': m.group(3) or 'MARKER', 'icons': icons, 'next': nxt}
        if vote: out[m.group(2)]['vote'] = vote.group(1)
    return out


PROGRESS = os.path.join(ROOT, 'decompiled/Newera_Handling/Progress')
REQ = re.compile(r'require\("Src/Newera_Handling/Progress/(ScenarioProgressData/[\w/]+)"\)')


def loaded_files():
    """The progress files the game actually loads, in load order: Progress.lua's require chain (depth first, in
    source order). The folder also holds files nothing loads (_OLD, _TEST, _TO_4, MS06_X07, MS11_F01/F02, MS12_H01;
    the game takes Chapter 6 from ..._MS06_X07_Trial_01) [read 2026-11-22]."""
    order, seen = [], set()

    def visit(path):
        for m in REQ.finditer(open(path, encoding='utf-8', errors='replace').read()):
            q = os.path.join(PROGRESS, m.group(1) + '.lua')
            if q in seen or not os.path.exists(q): continue
            seen.add(q); order.append(q); visit(q)
    visit(os.path.join(PROGRESS, 'Progress.lua'))
    return [p for p in order if '/FollowEvent/' not in p.replace('\\', '/')]


def follow_markers(anchors):
    """Follow-event markers (FollowEvent/FollowEventList.lua): extra markers the world map shows while the story
    position is inside a range, e.g. `targetAnchor >= SA_X and targetAnchor <= SA_Y` (or `< SA_Y`). Returns
    [{"icon", "lo", "hi"}] with inclusive anchor indices [read]."""
    d = os.path.join(PROGRESS, 'ScenarioProgressData/FollowEvent')
    files = re.findall(r'FollowEvent/(FollowEventData_\w+)"', open(os.path.join(d, 'FollowEventList.lua'), encoding='utf-8').read())
    out = []
    for f in files:
        src = open(os.path.join(d, f + '.lua'), encoding='utf-8', errors='replace').read()
        for block in re.split(r'(?=function condition)', src):
            m = re.search(r'followEventData\.new\("(\w+)", condition\)', block)
            if not m: continue
            lo = re.search(r'targetAnchor >= EScenarioAnchor(SA_\w+)', block)
            hi = re.search(r'targetAnchor (<=?) EScenarioAnchor(SA_\w+)', block)
            assert lo and hi, (f, m.group(1))
            out.append({'icon': m.group(1), 'lo': anchors.index(lo.group(1)),
                        'hi': anchors.index(hi.group(2)) - (1 if hi.group(1) == '<' else 0)})
    return out


def main():
    data = json.load(open(OUT, encoding='utf-8'))
    points = {}
    for f in loaded_files():
        for a, p in parse_file(open(f, encoding='utf-8', errors='replace').read()).items():
            points.setdefault(a, p)          # GetScenarioProgressData returns the first match in load order
    anchors = set(data['anchors'])
    missing = [a for a in points if a not in anchors]
    assert not missing, missing[:5]
    for a, p in points.items():
        bad = [n for n in p['next'] if n not in anchors]
        assert not bad, (a, bad)
    icon_rows = json.load(open(os.path.join(ROOT, 'data/tables/GOP_World_Icon.json'), encoding='utf-8'))
    icon_rows = icon_rows.get('rows', icon_rows)
    follow = follow_markers(data['anchors'])
    end_flags, no_row = {}, set()
    for ic in [i for p in points.values() for i in p['icons']] + [f['icon'] for f in follow]:
        if True:
            r = icon_rows.get(ic)
            if r is None: no_row.add(ic); continue      # named by a script but has no icon row: kept as the game does
            fl = (r.get('WorldIconEndFlag') or '').replace('Flag.', '')
            if fl: end_flags[ic] = fl
    print('markers named by scripts without an icon row:', len(no_row), sorted(no_row)[:6])
    print('points whose marker list is assigned more than once (first kept):', CONDITIONAL_ICONS)
    nxt = {a: p['next'] for a, p in points.items()}
    seen, todo = {'SA_MS01_X01_HD010'}, ['SA_MS01_X01_HD010']
    while todo:
        for n in nxt.get(todo.pop(), []):
            if n not in seen: seen.add(n); todo.append(n)
    print('story points reachable from the start of Chapter 1:', len(seen & set(points)), 'of', len(points),
          '| not reachable:', sorted(set(points) - seen)[:12])
    data['points'] = points
    data['follow_markers'] = follow
    data['icon_end_flags'] = end_flags
    data['worldmap_location_hex'] = WORLDMAP_LOCATION_HEX
    data['source'] = (data['source'].split('; generated')[0] + '; story points from Progress/ScenarioProgressData/*.lua and '
                      'GOP_World_Icon; generated 2026-11-22')
    json.dump(data, open(OUT, 'w', encoding='utf-8', newline='\n'), ensure_ascii=False, indent=0)
    types = {}
    for p in points.values(): types[p['type']] = types.get(p['type'], 0) + 1
    print(len(points), 'story points', types, '| with markers:', sum(1 for p in points.values() if p['type'] == 'MARKER' and p['icons']),
          '| icon end flags:', len(end_flags))


if __name__ == '__main__':
    main()
