"""Higher-level editor features built on model.Save and tables.Tables.

- learn_qualified / learn_all: learn-table moves a unit qualifies for but doesn't have (the game never grants moves
  from below the current level after the fact).
- promote_targets / demote_target: the next / previous class in the unit's chain.
- mod_summary: which TSMod content a save uses and whether the installed TSMod pak has every id it needs.
- shop: the shop and quartermaster stock table (layout from tools/tsshop.py).
- orders: Quietus orders.
- recruits: add the TSMod recruits a save lacks, from game-made Lv1 records (recruit_records.json).
- export_unit / import_unit: a unit record as a small JSON file.
- compare: every difference between two saves, by area.
"""
import json, os, re, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import tsshop                                        # noqa: E402
from . import model, checks
from .checks import SAFE, RISKY, DANGER

MOD_ID = re.compile(r'_[A-Z]\d{3}P(?:_|$)')


# ---------------------------------------------------------------------------------------------------- learning
def class_chain(T, job):
    """The class and every class before it (rank 1 first)."""
    out, j = [], job
    while j and j != 'None' and j not in out and T.row('GOP_Battle_Job', j):
        out.insert(0, j); j = T.row('GOP_Battle_Job', j).get('JobTypeBefore')
    return out


def is_passive(T, ability):
    r = T.row('GOP_Battle_Ability', ability) or {}
    return 1 if str(r.get('eAbilityCategory', '')).endswith('SUPPORT') else 0


def learn_qualified(save, T, uid):
    """[(level, ability, passive)] the unit's class chain grants at or below its level and it doesn't know."""
    info = save.unit_info(uid)
    lv = info['stats']['level']; have = {a for _, a in info['learned']}
    out = []
    for job in class_chain(T, info['jobs'][0] if info['jobs'] else None):
        r = T.row('GOP_Battle_Job', job)
        for k in range(1, 11):
            a = r.get(f'LearnableAbility{k}'); need = r.get(f'iLearnableLevel{k}', 0)
            if a and a != 'None' and need <= lv and a not in have and a not in [x[1] for x in out]:
                out.append((need, a, is_passive(T, a)))
    return out


def learn_all(save, T, uid, status):
    for _, a, p in learn_qualified(save, T, uid):
        save.add_learned(uid, a, p, status)


def promote_targets(T, job):
    r = T.row('GOP_Battle_Job', job) or {}
    return [r[f] for f in ('JobTypeAfter1', 'JobTypeAfter2', 'JobTypeAfter3') if r.get(f) and r[f] != 'None']


def demote_target(T, job):
    r = T.row('GOP_Battle_Job', job) or {}
    j = r.get('JobTypeBefore')
    return j if j and j != 'None' else None


# ---------------------------------------------------------------------------------------------------- TSMod content
def mod_summary(save, T):
    """{'recruits': [names], 'mod_ids': n, 'missing': [ids], 'paks': [names]}."""
    ids = {m.decode() for m in re.findall(checks.ID_PATTERN, save.plaintext())}
    mod_ids = {i for i in ids if MOD_ID.search(i)}
    recruits = [u for u in save.unit_ids() if re.match(r'UNIT_MASTER_CH_[NM]\d', u)]
    return {'recruits': recruits, 'mod_ids': len(mod_ids), 'missing': sorted(mod_ids - T.all_ids),
            'paks': [os.path.basename(p) for p in T.mod_paks]}


# ---------------------------------------------------------------------------------------------------- shop
def shop(save):
    """[(id, stock_at, stock, tail6)]: the longest run of stock entries {FString id, int32 stock, 6 bytes} around any
    occurrence of ITEM_CLASSMEDAL_MIDDLE (the id also appears in the inventory, so every occurrence is tried)."""
    b = bytes(save.s1); best = []
    for m in re.finditer(re.escape(b'ITEM_CLASSMEDAL_MIDDLE\x00'), b):
        anchor = m.start() - 4
        for start in range(max(0, anchor - 8000), anchor + 1):
            o, run = start, []
            while True:
                r = tsshop._entry(b, o)
                if not r: break
                run.append(r); o = r[4]
            if len(run) > len(best) and any(x[0] == 'ITEM_CLASSMEDAL_MIDDLE' for x in run): best = run
    return [(sid, e, stock, tail) for sid, e, stock, tail, _ in best]


def set_stock(save, stock_at, count, status):
    """Set one stock row (rows are addressed by position: an item can be both a shop and an exchange entry)."""
    rows = shop(save)
    instock = {}
    for sid, e, stock, tail in rows:
        if stock > 0 and not tail[0] & 0x02: instock.setdefault(tail[0] & ~0x02, tail[:2])
    for sid, e, stock, tail in rows:
        if e == stock_at:
            item = sid
            save.s1[e:e + 4] = struct.pack('<i', int(count))
            if count > 0 and tail[0] & 0x02:                  # sold out: copy the flags of an in-stock entry
                good = instock.get(tail[0] & ~0x02)
                if good: save.s1[e + 4:e + 6] = good
            save.reparse(); save.dirty = True; save.history.append((f'shop: {item} stock = {count}', status))
            return
    raise KeyError(stock_at)


# ---------------------------------------------------------------------------------------------------- orders
def set_order(save, order, value, flag, status):
    for k, vat, v, fat, f in save.parts['orders']:
        if k == order:
            save.s1[vat:vat + 4] = struct.pack('<i', int(value))
            save.s1[fat:fat + 4] = struct.pack('<i', 1 if flag else 0)
            save.reparse(); save.dirty = True; save.history.append((f'Quietus {order} = {value}/{int(bool(flag))}', status))
            return
    end, at = save.parts['orders_end'], save.parts['orders_count_at']
    n = len(save.parts['orders'])
    save.s1[end:end] = model.fstring(order) + struct.pack('<ii', int(value), 1 if flag else 0)
    struct.pack_into('<i', save.s1, at, n + 1)
    save.reparse(); save.dirty = True; save.history.append((f'Quietus: add {order}', status))


# ---------------------------------------------------------------------------------------------------- recruits
def recruit_templates():
    return json.load(open(os.path.join(HERE, 'recruit_records.json')))['records']


def recruit_plan(save, T):
    """[(uid, name, class, weapon, first_move, problems)] for each TSMod recruit the save lacks."""
    tmpl = recruit_templates(); out = []
    have = set(save.unit_ids())
    for uid in sorted(tmpl):
        if uid in have: continue
        cid = uid[15:]
        job, wpn, party = f'BATTLE_JOB_CH_{cid}P_1', f'BATTLE_WEAPON_{cid}P', f'BATTLE_UNITPARAM_CH_{cid}_PARTY'
        problems = [x for x in (job, wpn, party) if x not in T.all_ids]
        if problems: continue                       # not a recruit in the installed TSMod (e.g. the Hierophant)
        first = None
        r = T.row('GOP_Battle_Job', job) or {}
        moves = sorted((r.get(f'iLearnableLevel{k}', 99), k, r.get(f'LearnableAbility{k}')) for k in range(1, 11)
                       if r.get(f'LearnableAbility{k}') not in (None, 'None'))
        if moves: first = moves[0][2]                 # lowest level, then the class table's own order
        out.append((uid, T.name_of(uid), job, wpn, first, problems))
    return out


def add_recruit(save, T, uid, status):
    rec = bytes.fromhex(recruit_templates()[uid])
    cid = uid[15:]
    old = {m.decode() for m in re.findall(rb'BATTLE_(?:JOB|WEAPON|UNITPARAM|ABILITY)_[A-Z0-9_]+', rec)}
    repl = {}
    for o in old:
        if o.startswith('BATTLE_JOB_'): repl[o] = f'BATTLE_JOB_CH_{cid}P_1'
        elif o.startswith('BATTLE_WEAPON_'): repl[o] = f'BATTLE_WEAPON_{cid}P'
        elif o.startswith('BATTLE_UNITPARAM_'): repl[o] = f'BATTLE_UNITPARAM_CH_{cid}_PARTY'
    plan = {p[0]: p for p in recruit_plan(save, T)}
    first = plan[uid][4] if uid in plan else None
    for o in old:
        if o.startswith('BATTLE_ABILITY_') and first: repl[o] = first
    for o, n in repl.items():
        if o != n: rec = rec.replace(model.fstring(o), model.fstring(n))
    # Party state (record end -7: 0 never joined, 1 in party, 2 left; SAVE_FORMAT.md). Always add the recruit as never
    # joined, so join_release joins it and levels it like the others (Sycras's template had 1: user, 2026-11-23).
    rec = bytearray(rec); rec[-7] = 0; rec = bytes(rec)
    pos = save.units_end
    for u, s, e in save.unit_recs:
        if u > uid: pos = s; break
    cnt = struct.unpack_from('<i', save.s1, save.units_count_at)[0]
    save.s1[pos:pos] = rec
    struct.pack_into('<i', save.s1, save.units_count_at, cnt + 1)
    save.reparse(); save.dirty = True
    save.history.append((f'add TSMod recruit {T.name_of(uid)} ({uid})', status))


# ---------------------------------------------------------------------------------------------------- unit files
def export_unit(save, T, uid, path):
    s, e = save.unit_record(uid)
    json.dump({'format': 'tsmod-unit-1', 'unit': uid, 'name': T.name_of(uid) if T else uid,
               'save_version': save.version, 'record': bytes(save.s1[s:e]).hex()}, open(path, 'w'), indent=1)


def read_unit_file(path):
    d = json.load(open(path))
    if d.get('format') != 'tsmod-unit-1': raise ValueError('not a TSMod unit file')
    return d


def import_unit(save, d, status):
    uid, rec = d['unit'], bytes.fromhex(d['record'])
    if uid in save.unit_ids():
        s, e = save.unit_record(uid)
        save.s1[s:e] = rec
    else:
        pos = save.units_end
        for u, s, e in save.unit_recs:
            if u > uid: pos = s; break
        cnt = struct.unpack_from('<i', save.s1, save.units_count_at)[0]
        save.s1[pos:pos] = rec
        struct.pack_into('<i', save.s1, save.units_count_at, cnt + 1)
    save.reparse(); save.dirty = True; save.history.append((f'import unit {d.get("name", uid)}', status))


# ---------------------------------------------------------------------------------------------------- compare
def compare(a, b, T=None):
    """[(area, item, value in A, value in B)] for every located field that differs."""
    nm = (lambda x: T.name_of(x)) if T else (lambda x: x)
    out = []
    for k in ('leader', 'level', 'play_time', 'saved'):
        va, vb = a.preview.get(k), b.preview.get(k)
        if k == 'saved': va, vb = str(va)[:16], str(vb)[:16]
        if va != vb: out.append(('Overview', k.replace('_', ' '), va, vb))
    if a.gold != b.gold: out.append(('Overview', 'Gold', f'{a.gold:,}', f'{b.gold:,}'))
    for i, label in enumerate(['(unused)', 'Liberty', 'Utility', 'Morality']):
        va, vb = a.parts['convictions']['a'][i][1], b.parts['convictions']['a'][i][1]
        if va != vb: out.append(('Overview', label, va, vb))
    va = {e['name']: e['value'] for e in a.sysvars['entries']}; vb = {e['name']: e['value'] for e in b.sysvars['entries']}
    for k in sorted(set(va) | set(vb)):
        if va.get(k) != vb.get(k): out.append(('Script variables', k, va.get(k), vb.get(k)))
    fa = {n: v for n, _, v in a.flags['entries']}; fb = {n: v for n, _, v in b.flags['entries']}
    for k in sorted(set(fa) | set(fb)):
        if fa.get(k) != fb.get(k): out.append(('Story flags', k, fa.get(k), fb.get(k)))
    ua, ub = set(a.unit_ids()), set(b.unit_ids())
    for u in sorted(ua | ub):
        if u not in ua or u not in ub:
            out.append(('Units', nm(u), 'present' if u in ua else '—', 'present' if u in ub else '—')); continue
        ia, ib = a.unit_info(u), b.unit_info(u)
        for k, v in ia['stats'].items():
            if v != ib['stats'][k]: out.append(('Units', f'{nm(u)}: {k}', v, ib['stats'][k]))
        for k in ('params', 'jobs', 'weapons'):
            if ia[k] != ib[k]: out.append(('Units', f'{nm(u)}: {k}', ', '.join(map(nm, ia[k])), ', '.join(map(nm, ib[k]))))
        la, lb = {x for _, x in ia['learned']}, {x for _, x in ib['learned']}
        for x in sorted(la - lb): out.append(('Units', f'{nm(u)}: learned', nm(x), '—'))
        for x in sorted(lb - la): out.append(('Units', f'{nm(u)}: learned', '—', nm(x)))
        oa, ob = set(ia['other_abilities']), set(ib['other_abilities'])
        for x in sorted(oa - ob): out.append(('Units', f'{nm(u)}: record', nm(x), '—'))
        for x in sorted(ob - oa): out.append(('Units', f'{nm(u)}: record', '—', nm(x)))
        if ia['bytes'] != ib['bytes']: out.append(('Units', f'{nm(u)}: record size', ia['bytes'], ib['bytes']))
    for ma, mb in zip(a.parts['maps'], b.parts['maps']):
        da = {k: v for k, _, v in ma['entries']}; db = {k: v for k, _, v in mb['entries']}
        for k in sorted(set(da) | set(db)):
            if da.get(k) != db.get(k): out.append((f'Items: {ma["label"]}', nm(k), da.get(k, '—'), db.get(k, '—')))
    oa = {k: (v, f) for k, _, v, _, f in a.parts['orders']}; ob = {k: (v, f) for k, _, v, _, f in b.parts['orders']}
    for k in sorted(set(oa) | set(ob)):
        if oa.get(k) != ob.get(k): out.append(('Quietus', nm(k), oa.get(k, '—'), ob.get(k, '—')))
    sa = {r[0]: r[2] for r in shop(a)}; sb = {r[0]: r[2] for r in shop(b)}
    for k in sorted(set(sa) | set(sb)):
        if sa.get(k) != sb.get(k): out.append(('Shop', nm(k), sa.get(k, '—'), sb.get(k, '—')))
    if len(a.s1) != len(b.s1): out.append(('Raw', 'game-state size', f'{len(a.s1):,} bytes', f'{len(b.s1):,} bytes'))
    return out


# ---------------------------------------------------------------------------------------------------- weapon trees
# Layout [read, 2026-11-20, from real records]: after the unit's weapon FString comes int32 N, then N bought-node
# objects ({int32 0, FString node id, type-specific payload}), then the same ids again as TArray<FString>.
# Un-buying = removing one object and its echo entry. Buying would need each node type's payload: not offered.
def _name_at(rec, p):
    L = struct.unpack_from('<i', rec, p)[0]
    if not 3 <= L <= 100 or rec[p + 4 + L - 1] != 0: return None, p
    t = rec[p + 4:p + 3 + L]
    if not re.fullmatch(rb'[A-Z0-9_]+', t): return None, p
    return t.decode(), p + 4 + L


def weapon_nodes(save, uid):
    """{'weapon', 'count_at', 'objects': [(id, start, end)], 'echo_at', 'echo_end'} or None."""
    info = save.unit_info(uid)
    if not info['weapons']: return None
    s, e = save.unit_record(uid); rec = bytes(save.s1[s:e])
    w = model.fstring(info['weapons'][0]); i = rec.find(w)
    if i < 0: return None
    cnt_at = i + len(w); n = struct.unpack_from('<i', rec, cnt_at)[0]
    if not 0 <= n <= 64: return None
    if n == 0: return {'weapon': info['weapons'][0], 'count_at': s + cnt_at, 'objects': [], 'echo_at': None, 'echo_end': None}
    first, _ = _name_at(rec, cnt_at + 8)
    if not first: return None
    # the echo list: int32 n followed by n names, the first one = the first object's id
    pat = struct.pack('<i', n) + model.fstring(first)
    q = rec.find(pat, cnt_at + 8)
    while q >= 0:
        names, p = [], q + 4
        for _ in range(n):
            nm, p2 = _name_at(rec, p)
            if not nm: break
            names.append(nm); p = p2
        if len(names) == n: break
        q = rec.find(pat, q + 1)
    if q < 0: return None
    objs, cur = [], cnt_at + 4
    for k, nm in enumerate(names):
        hdr = b'\x00\x00\x00\x00' + model.fstring(nm)
        st = rec.find(hdr, cur)
        if st < 0 or st >= q: return None
        if objs: objs[-1] = (objs[-1][0], objs[-1][1], s + st)
        objs.append((nm, s + st, s + q)); cur = st + len(hdr)
    return {'weapon': info['weapons'][0], 'count_at': s + cnt_at, 'objects': objs, 'echo_at': s + q, 'echo_end': s + p}


def unbuy_node(save, uid, node, status):
    wn = weapon_nodes(save, uid)
    if not wn: raise ValueError('could not read this unit\'s weapon tree')
    ids = [o[0] for o in wn['objects']]
    if node not in ids: raise KeyError(node)
    k = ids.index(node); nm, st, en = wn['objects'][k]
    # echo entry k
    p = wn['echo_at'] + 4
    for j in range(k): _, p = _name_at(bytes(save.s1), p)
    _, p2 = _name_at(bytes(save.s1), p)
    n = len(ids)
    del save.s1[p:p2]                                        # echo entry (after the objects, delete first)
    struct.pack_into('<i', save.s1, wn['echo_at'], n - 1)
    del save.s1[st:en]                                       # the object
    struct.pack_into('<i', save.s1, wn['count_at'], n - 1)
    save.reparse(); save.dirty = True; save.history.append((f'{uid}: un-buy weapon-tree node {node}', status))


def accessories(save, uid):
    s, e = save.unit_record(uid); rec = bytes(save.s1[s:e])
    return sorted(set(m.decode() for m in re.findall(rb'(?<![A-Z_])BATTLE_ACCESSARY_[A-Z0-9_]+', rec)))


# ---------------------------------------------------------------------------------------------------- unlocks
def mock_battles(save, T):
    """[(quest id, title, chapter, normal flag, normal value, hard flag, hard value)]."""
    flags = {n: v for n, _, v in save.flags['entries']}
    out = []
    for qid, r in T.rows.get('GOP_Quest_Info', {}).items():
        fn, fh = r.get('ClearFlag_Normal'), r.get('ClearFlag_Hard')
        if fn in flags or fh in flags:
            out.append((qid, T.text.get(r.get('TitleTextId'), qid), r.get('ChapterNum'), fn, flags.get(fn), fh, flags.get(fh)))
    return sorted(out, key=lambda x: (x[2] or 0, x[0]))


def character_stories(save):
    """[(flag, story number, episode, extra, value)] from the WI_END_CSxx_Eyy flags."""
    out = []
    for n, _, v in save.flags['entries']:
        m = re.fullmatch(r'WI_END_CS(\d+)_E(\d+)(_EX)?', n)
        if m: out.append((n, int(m.group(1)), int(m.group(2)), bool(m.group(3)), v))
    return out
