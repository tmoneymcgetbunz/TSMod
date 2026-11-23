"""Unit (character) records in TRIANGLE STRATEGY saves: list, and inject a record from another save.

  python tsunits.py list   <file.sav>
  python tsunits.py inject <target.sav> <template.sav> <UNIT_MASTER_ID> <out.sav>
  python tsunits.py learned <file.sav> <UNIT_MASTER_ID>                      (print the learned-ability list)
  python tsunits.py show <file.sav> <UNIT_MASTER_ID|all-recruits> [<other.sav>]  (level, ids, learned; diff vs other)
  python tsunits.py addlearned <in.sav> <UNIT_MASTER_ID> <BATTLE_ABILITY_...> <passive 0|1> <out.sav>
  python tsunits.py removelearned <in.sav> <UNIT_MASTER_ID> <BATTLE_ABILITY_...> <out.sav>   (learned list + passive cache)
  python tsunits.py setlevel <in.sav> <UNIT_MASTER_ID> <level> <out.sav>   (level, EXP 0; the game rebuilds stats at battle entry)
  python tsunits.py addpassive <in.sav> <UNIT_MASTER_ID> <BATTLE_ABILITY_...> <BATTLE_CORRECTPARAM_...> <out.sav>

Layout (game-state section s1), from ShaneQi's s1parse.js: an int32 count, then that many unit records
back to back, sorted by unit-master id. Each record starts with the unit-master FString. The array is
followed by the world tail (leader-name FString, then gold). JoinParty can only flag an existing record,
and records are created only at New Game, so a unit added to an existing save needs its record injected.
`inject` never writes over its inputs; it writes a new file and re-verifies it.
"""
import os, re, struct, sys
import tssave


def _load(path):
    data = open(path, 'rb').read()
    hdr, props = tssave.parse(data)
    plain, ok = tssave.decrypt_blob(props[0]['data'])
    if not ok:
        raise SystemExit(f'{path}: SHA-1 mismatch, refusing to touch it')
    return data, props, plain


def unit_array(s1):
    """Return (count_offset, [(record_start, unit_id)], array_end) within s1."""
    starts = []
    for m in re.finditer(rb'(.)\x00\x00\x00(UNIT_MASTER_CH_[A-Z0-9_]+)\x00', s1, re.S):
        o = m.start()
        if m.group(1)[0] != len(m.group(2)) + 1 or o + 84 + 64 > len(s1):
            continue
        v = struct.unpack_from('<16i', s1, o + 84)
        if 1 <= v[0] <= 99 and 0 <= v[1] < 100 and 100 <= v[2] <= 1500 and 1 <= v[5] <= 9999:
            starts.append((o, m.group(2).decode()))
    if not starts:
        raise SystemExit('no unit records found')
    # keep the contiguous run that follows the count
    first = starts[0][0]
    count = struct.unpack_from('<i', s1, first - 4)[0]
    if count != len(starts):
        raise SystemExit(f'count {count} != records found {len(starts)}; layout not as expected')
    # array end = start of the world tail: FString (leader name) followed by gold. Last record is
    # bounded by the next negative-length (UTF-16) FString after it.
    last = starts[-1][0]
    m = re.compile(rb'[\xc0-\xff]\xff\xff\xff', re.S)
    end = None
    for k in m.finditer(s1, last + 100):
        n = struct.unpack_from('<i', s1, k.start())[0]
        if -32 <= n <= -2 and s1[k.start() + 4 - 2 * n - 2:k.start() + 4 - 2 * n] == b'\x00\x00':
            end = k.start(); break
    if end is None:
        raise SystemExit('could not find end of unit array')
    return first - 4, starts, end


def records(s1):
    co, starts, end = unit_array(s1)
    bounds = [s for s, _ in starts] + [end]
    return co, [(uid, bounds[i], bounds[i + 1]) for i, (_, uid) in enumerate(starts)], end


def gold(s1):
    _, _, end = unit_array(s1)
    n = struct.unpack_from('<i', s1, end)[0]
    return struct.unpack_from('<i', s1, end + 4 + (-2 * n if n < 0 else n))[0]


def splice_s1(plain, new_s1):
    secs, _ = tssave.sections(plain)
    a, n = secs[1]
    out = bytearray(plain[:a - 4]) + struct.pack('<i', len(new_s1)) + new_s1 + plain[a + n:]
    return bytes(out)


def inject(target, template, uid, out):
    tdata, tprops, tplain = _load(target)
    _, _, mplain = _load(template)
    ta, tn = tssave.sections(tplain)[0][1]; s1 = tplain[ta:ta + tn]
    ma, mn = tssave.sections(mplain)[0][1]; m1 = mplain[ma:ma + mn]
    co, recs, end = records(s1)
    if any(r[0] == uid for r in recs):
        raise SystemExit(f'{uid} already in target')
    src = [r for r in records(m1)[1] if r[0] == uid]
    if not src:
        raise SystemExit(f'{uid} not in template')
    rec = m1[src[0][1]:src[0][2]]
    # insert in sorted position
    pos = end
    for r in recs:
        if r[0] > uid:
            pos = r[1]; break
    new_s1 = bytearray(s1[:pos]) + rec + s1[pos:]
    struct.pack_into('<i', new_s1, co, len(recs) + 1)
    new_plain = splice_s1(tplain, bytes(new_s1))
    blob = tssave.encrypt_blob(new_plain)
    open(out, 'wb').write(tssave.replace_blob(tdata, tprops, blob))
    # verify
    _, _, vplain = _load(out)
    va, vn = tssave.sections(vplain)[0][1]; v1 = vplain[va:va + vn]
    vco, vrecs, _ = records(v1)
    assert [r[0] for r in vrecs] == sorted([r[0] for r in recs] + [uid]), 'record order mismatch'
    assert v1[vrecs[[r[0] for r in vrecs].index(uid)][1]:][:len(rec)] == rec, 'record bytes mismatch'
    assert gold(v1) == gold(s1), 'gold changed'
    assert vplain[0x40:ta - 4] == tplain[0x40:ta - 4], 's0 changed'
    assert vplain[:0x0c] == tplain[:0x0c] and vplain[0x20:0x40] == tplain[0x20:0x40], 'header changed'
    assert vplain[va + vn:-20] == tplain[ta + tn:-20], 's2 changed'
    print(f'injected {uid} ({len(rec)} bytes) at s1+{pos}; units {len(recs)} -> {len(vrecs)}; gold {gold(v1)}; wrote {out}')


def set_string(target, uid, old, new, out, replace_all=False, first=False):
    """Replace an FString value (exact match) inside a unit's record, e.g. its battle-param id.
    Exactly one occurrence unless replace_all; first=True replaces only the first one (the learned-ability list
    precedes the passive-effect cache, Test 14 layout notes in SAVE_FORMAT.md)."""
    data, props, plain = _load(target)
    a, n = tssave.sections(plain)[0][1]; s1 = plain[a:a + n]
    co, recs, end = records(s1)
    r = [x for x in recs if x[0] == uid]
    if not r: raise SystemExit(f'{uid} not in save')
    _, s, e = r[0]
    def fs(x): b = x.encode('latin1') + b'\0'; return struct.pack('<i', len(b)) + b
    rec = s1[s:e]
    k = rec.count(fs(old))
    if k == 0 or (k != 1 and not (replace_all or first)): raise SystemExit(f'{old} occurs {k} times in {uid} record')
    rec2 = rec.replace(fs(old), fs(new), 1 if first else -1)
    new_s1 = s1[:s] + rec2 + s1[e:]
    new_plain = splice_s1(plain, new_s1)
    open(out, 'wb').write(tssave.replace_blob(data, props, tssave.encrypt_blob(new_plain)))
    _, _, vplain = _load(out)
    va, vn = tssave.sections(vplain)[0][1]; v1 = vplain[va:va + vn]
    _, vrecs, _ = records(v1)
    assert [x[0] for x in vrecs] == [x[0] for x in recs]
    vr = [x for x in vrecs if x[0] == uid][0]
    assert v1[vr[1]:vr[2]] == rec2 and gold(v1) == gold(s1)
    assert tssave.units(vplain)[uid]['level'] == tssave.units(plain)[uid]['level']
    print(f'{uid}: {old} -> {new} ({len(rec)} -> {len(rec2)} bytes); wrote {out}')


def fstring(x):
    b = x.encode('latin1') + b'\0'; return struct.pack('<i', len(b)) + b


def patch_record(target, uid, find, repl, out):
    """Replace one exact byte sequence inside a unit's record (must occur exactly once)."""
    data, props, plain = _load(target)
    a, n = tssave.sections(plain)[0][1]; s1 = plain[a:a + n]
    co, recs, end = records(s1)
    _, s, e = [x for x in recs if x[0] == uid][0]
    rec = s1[s:e]
    if rec.count(find) != 1: raise SystemExit(f'pattern occurs {rec.count(find)} times in {uid}')
    rec2 = rec.replace(find, repl)
    new_plain = splice_s1(plain, s1[:s] + rec2 + s1[e:])
    open(out, 'wb').write(tssave.replace_blob(data, props, tssave.encrypt_blob(new_plain)))
    _, _, vplain = _load(out)
    va, vn = tssave.sections(vplain)[0][1]; v1 = vplain[va:va + vn]
    _, vrecs, _ = records(v1)
    assert [x[0] for x in vrecs] == [x[0] for x in recs] and gold(v1) == gold(s1)
    vr = [x for x in vrecs if x[0] == uid][0]; assert v1[vr[1]:vr[2]] == rec2
    print(f'{uid}: patched ({len(rec)} -> {len(rec2)} bytes); wrote {out}')


def add_weapon_skill(target, uid, skill, out):
    """Add the weapon-skill unlock entry the game writes when a weapon-skill node is bought:
    after the bought-node id list: count 1, {FString skill, i32 1, i32 0, FString skill, i32 0}
    (identical across all recruits checked). Requires the node in the bought list and an empty skill list."""
    tail = b'\x01\x00\x00\x00\x05\x00\x00\x00None\x00'
    find = fstring(skill) + struct.pack('<i', 0) + tail
    repl = fstring(skill) + struct.pack('<i', 1) + fstring(skill) + struct.pack('<ii', 1, 0) + fstring(skill) + struct.pack('<i', 0) + tail
    patch_record(target, uid, find, repl, out)


def learned_list(rec):
    """Find the learned-ability list in a unit record [read, Test 21e]: int32 count, then per entry
    [i32 flag][i32 0][u8 0][FString ability]; flag meaning unknown (1 on every Resist and most passives, 0 on most commands; Sycras's Detain has 1). Followed by the passive-effect
    cache, whose entries don't fit this shape. Returns (count_pos, end_pos, [(flag, name)]) for the last match."""
    best = None
    for cpos in range(0, len(rec) - 4):
        cnt = struct.unpack_from('<i', rec, cpos)[0]
        if not 1 <= cnt <= 64: continue
        p = cpos + 4; ents = []
        try:
            for _ in range(cnt):
                f1, f2 = struct.unpack_from('<ii', rec, p)
                L = struct.unpack_from('<i', rec, p + 9)[0]
                if f1 not in (0, 1) or f2 != 0 or rec[p + 8] != 0 or not 16 < L < 80: raise ValueError
                nm = rec[p + 13:p + 12 + L]
                if not nm.startswith(b'BATTLE_ABILITY_') or rec[p + 12 + L] != 0: raise ValueError
                ents.append((f1, nm.decode())); p += 13 + L
        except (ValueError, struct.error, IndexError):
            continue
        best = (cpos, p, ents)
    if not best: raise SystemExit('learned-ability list not found')
    return best


def add_learned(target, uid, ability, passive, out):
    """Append an ability to a unit's learned list (e.g. a learn-table entry below the unit's current level)."""
    _, _, plain = _load(target)
    a, n = tssave.sections(plain)[0][1]; s1 = plain[a:a + n]
    _, s, e = [x for x in records(s1)[1] if x[0] == uid][0]
    rec = s1[s:e]; cpos, end, ents = learned_list(rec)
    if ability in [x[1] for x in ents]: raise SystemExit(f'{uid} already has {ability}')
    repl = struct.pack('<i', len(ents) + 1) + rec[cpos + 4:end] + struct.pack('<iiB', int(passive), 0, 0) + fstring(ability)
    patch_record(target, uid, rec[cpos:end], repl, out)


def passive_cache(rec, end):
    """The passive cache right after the learned list [read, Test 28]: int32 count, then per entry
    [i32 0][FString ability][i32 0][FString CorrectParam] (e.g. INVALID_FLAME -> BATTLE_CORRECTPARAM_ABILITY_INVALID_FLAME
    on Svarog). Returns (end_pos, [(start, stop, ability, correctparam)])."""
    p = end; cnt = struct.unpack_from('<i', rec, p)[0]; p += 4; ents = []
    for _ in range(cnt):
        st = p
        assert struct.unpack_from('<i', rec, p)[0] == 0; p += 4
        L = struct.unpack_from('<i', rec, p)[0]; ab = rec[p + 4:p + 3 + L].decode(); p += 4 + L
        assert struct.unpack_from('<i', rec, p)[0] == 0; p += 4
        L = struct.unpack_from('<i', rec, p)[0]; cp = rec[p + 4:p + 3 + L].decode(); p += 4 + L
        ents.append((st, p, ab, cp))
    return p, ents


def _record(target, uid):
    _, _, plain = _load(target)
    a, n = tssave.sections(plain)[0][1]; s1 = plain[a:a + n]
    _, s, e = [x for x in records(s1)[1] if x[0] == uid][0]
    return s1[s:e]


def remove_learned(target, uid, ability, out):
    """Remove an ability from a unit's learned list and, if present, from its passive cache (kit change, Test 28)."""
    rec = _record(target, uid); cpos, end, ents = learned_list(rec)
    if ability not in [x[1] for x in ents]: raise SystemExit(f'{uid} has no {ability}')
    body = b''.join(struct.pack('<iiB', f, 0, 0) + fstring(nm) for f, nm in ents if nm != ability)
    cend, cents = passive_cache(rec, end)
    keep = [rec[s:e] for s, e, ab, _ in cents if ab != ability]
    repl = struct.pack('<i', len(ents) - 1) + body + struct.pack('<i', len(keep)) + b''.join(keep)
    assert len(rec[cpos:cend]) == len(struct.pack('<i', len(ents)) + b''.join(struct.pack('<iiB', f, 0, 0) + fstring(nm) for f, nm in ents)) + len(rec[end:cend])
    patch_record(target, uid, rec[cpos:cend], repl, out)


def add_passive(target, uid, ability, correctparam, out):
    """Append {ability, CorrectParam} to a unit's passive cache, as the game writes it when a passive is learned."""
    rec = _record(target, uid); _, end, _ = learned_list(rec)
    cend, cents = passive_cache(rec, end)
    if ability in [x[2] for x in cents]: raise SystemExit(f'{uid} cache already has {ability}')
    repl = struct.pack('<i', len(cents) + 1) + rec[end + 4:cend] + struct.pack('<i', 0) + fstring(ability) + struct.pack('<i', 0) + fstring(correctparam)
    patch_record(target, uid, rec[end:cend], repl, out)


def set_level(target, uid, level, out):
    """Set a unit's level (EXP to 0) in its stat block (SAVE_FORMAT.md: 16 int32 at record +84, level first).
    Stats are copies the game recomputes on level-up and battle entry. Cleanup test 17, 2026-11-20."""
    rec = _record(target, uid); blk = rec[84:84 + 64]
    lv, ex = struct.unpack_from('<ii', blk)
    if not (1 <= lv <= 99): raise SystemExit(f'unexpected stat block in {uid} (level {lv})')
    patch_record(target, uid, blk, struct.pack('<ii', int(level), 0) + blk[8:], out)


def summary(path, uid):
    """Level, the record's ids (param, class, weapons, abilities in order) and the learned list, for comparing saves."""
    _, _, plain = _load(path); a, n = tssave.sections(plain)[0][1]; s1 = plain[a:a + n]
    hit = [x for x in records(s1)[1] if x[0] == uid]
    if not hit: return None
    _, s, e = hit[0]; rec = s1[s:e]
    ids = [m.decode() for m in re.findall(rb'BATTLE_[A-Z0-9_]+', rec)]
    try: learned = learned_list(rec)[2]
    except SystemExit: learned = []
    return {'level': tssave.units(plain).get(uid, {}).get('level'), 'bytes': len(rec),
            'param': next((i for i in ids if i.startswith('BATTLE_UNITPARAM')), None),
            'class': next((i for i in reversed(ids) if i.startswith('BATTLE_JOB')), None),
            'weapons': [i for i in ids if i.startswith('BATTLE_WEAPON_')],
            'learned': sorted(nm for _, nm in learned)}


def unresolved_ids(path, build_out):
    """Ids anywhere in the save (unit records AND saved battle state) that match no row in the vanilla table dump
    (data/tables) or in a build's staged tables. Run before every install (Test 23 crash: a removed ability id in
    slot 2's saved battle state crashed the load). Vanilla saves also carry a few non-row ids; compare with slot 1."""
    import glob, json, dtparse
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    rows = set()
    for f in glob.glob(os.path.join(root, 'data', 'tables', '*.json')):
        try: rows |= set(json.load(open(f, encoding='utf-8')))
        except Exception: pass
    for ua in glob.glob(os.path.join(build_out, 'stage', '**', '*.uasset'), recursive=True):
        try: rows |= set(dtparse.parse(ua)[1])
        except Exception: pass
    _, _, plain = _load(path)
    pat = rb'(?<![A-Z0-9_])(?:BATTLE_(?:ABILITY|JOB|WEAPON|UNITPARAM|ACCESSARY|ARMOR|INFO|STATUSEFFECT)|ITEM|UNIT_MASTER|QUEST_INFO)_[A-Z0-9_]+'
    return sorted({m.decode() for m in re.findall(pat, plain)} - rows)


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'list':
        _, _, plain = _load(sys.argv[2])
        a, n = tssave.sections(plain)[0][1]; s1 = plain[a:a + n]
        co, recs, end = records(s1)
        print(f'count at s1+{co}: {len(recs)} units, array ends s1+{end}, gold {gold(s1)}')
        stats = tssave.units(plain)
        for uid, s, e in recs:
            st = stats.get(uid, {})
            print(f'  {uid:24} {e - s:5} bytes  Lv{st.get("level", "?")}')
    elif cmd == 'inject':
        inject(*sys.argv[2:6])
    elif cmd == 'setstr':      # tsunits.py setstr <in.sav> <UNIT_MASTER_ID> <old> <new> <out.sav> [--all | --first]
        set_string(*sys.argv[2:7], replace_all='--all' in sys.argv, first='--first' in sys.argv)
    elif cmd == 'learned':
        _, _, plain = _load(sys.argv[2]); a, n = tssave.sections(plain)[0][1]; s1 = plain[a:a + n]
        _, s, e = [x for x in records(s1)[1] if x[0] == sys.argv[3]][0]
        for f, nm in learned_list(s1[s:e])[2]: print(f'flag {f}  {nm}')
    elif cmd == 'ids':         # tsunits.py ids <sav> <build-out-dir>: ids in the save that no table row matches
        for i in unresolved_ids(sys.argv[2], sys.argv[3]): print(i)
    elif cmd == 'show':
        units = sys.argv[3]
        if units == 'all-recruits':
            units = [f'UNIT_MASTER_CH_{c}' for c in ('N106', 'N204', 'N005', 'N007', 'N009', 'N104', 'N105', 'N004', 'N006', 'N008', 'N102', 'N203')]
        else: units = [units]
        other = sys.argv[4] if len(sys.argv) > 4 else None
        for u in units:
            A = summary(sys.argv[2], u); print(f'== {u}:', 'no record' if A is None else f"Lv{A['level']} {A['class']} {A['weapons']} ({A['bytes']} bytes)")
            if A: print('   learned:', ', '.join(x[15:] for x in A['learned']))
            if other and A:
                B = summary(other, u)
                if B is None: print('   other save: no record'); continue
                for k in ('param', 'class', 'weapons', 'level'):
                    if A[k] != B[k]: print(f'   DIFF {k}: {A[k]} vs {B[k]}')
                only_a = set(A['learned']) - set(B['learned']); only_b = set(B['learned']) - set(A['learned'])
                if only_a: print('   learned only here:', sorted(x[15:] for x in only_a))
                if only_b: print('   learned only in other:', sorted(x[15:] for x in only_b))
    elif cmd == 'setlevel':
        set_level(*sys.argv[2:6])
    elif cmd == 'removelearned':
        remove_learned(*sys.argv[2:6])
    elif cmd == 'addpassive':
        add_passive(*sys.argv[2:7])
    elif cmd == 'addlearned':
        add_learned(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5] == '1', sys.argv[6])
    elif cmd == 'addwskill':   # tsunits.py addwskill <in.sav> <UNIT_MASTER_ID> <BATTLE_ABILITY_...> <out.sav>
        add_weapon_skill(*sys.argv[2:6])
