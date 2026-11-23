"""Shop / quartermaster stock in TRIANGLE STRATEGY saves (game-state section s1).

  python tsshop.py list <file.sav>
  python tsshop.py refill <in.sav> <out.sav> <pattern>=<count> [<pattern>=<count> ...]

Stock table = consecutive entries {FString item id, int32 remaining stock, 6 bytes:
  b0 status flags (0x02 seems to mean "sold out": 07 = shop item at 0, 05 = shop item with stock; 0c/0d = exchange),
  b1 bitmask of restock flags already applied, 2 bytes 0, 2 small bytes}.
`refill` sets stock for items whose id matches a regex. For shop items marked sold out (b0 & 0x02) it also copies
b0/b1 from an in-stock entry of the same kind, so the item becomes purchasable again. Writes a new file and re-verifies.
"""
import re, struct, sys
import tssave, tsunits


def _s1(path):
    data = open(path, 'rb').read(); hdr, props = tssave.parse(data)
    plain, ok = tssave.decrypt_blob(props[0]['data']); assert ok
    a, n = tssave.sections(plain)[0][1]
    return data, props, plain, a, n


def _entry(s, o):
    ln = struct.unpack_from('<i', s, o)[0]
    if not 5 <= ln <= 80: return None
    sid = s[o + 4:o + 4 + ln - 1]
    if s[o + 4 + ln - 1] != 0 or not re.fullmatch(rb'[A-Z][A-Z0-9_]+', sid): return None
    e = o + 4 + ln
    return sid.decode(), e, struct.unpack_from('<i', s, e)[0], bytes(s[e + 4:e + 10]), e + 10


def table(s):
    """Find the stock table: the longest run of entries that contains ITEM_CLASSMEDAL_MIDDLE."""
    anchor = s.find(b'ITEM_CLASSMEDAL_MIDDLE\x00') - 4
    assert anchor > 0, 'stock table not found'
    best = None
    for start in range(max(0, anchor - 6000), anchor + 1):
        o, run = start, []
        while True:
            r = _entry(s, o)
            if not r: break
            run.append(r); o = r[4]
        if any(r[0] == 'ITEM_CLASSMEDAL_MIDDLE' for r in run) and (best is None or len(run) > len(best)):
            best = run
    return best


def refill(src, dst, rules):
    data, props, plain, a, n = _s1(src)
    s = bytearray(plain[a:a + n])
    entries = table(bytes(s))
    instock = {}
    for sid, e, stock, tail, _ in entries:
        if stock > 0 and not tail[0] & 0x02: instock.setdefault(tail[0] & ~0x02, tail[:2])
    changed = []
    for sid, e, stock, tail, _ in entries:
        for pat, cnt in rules:
            if re.fullmatch(pat, sid):
                struct.pack_into('<i', s, e, cnt)
                if tail[0] & 0x02:
                    good = instock.get(tail[0] & ~0x02)
                    if good: s[e + 4:e + 6] = good
                changed.append((sid, stock, cnt, tail.hex(' '), bytes(s[e + 4:e + 10]).hex(' ')))
                break
    new_plain = plain[:a] + bytes(s) + plain[a + n:]
    open(dst, 'wb').write(tssave.replace_blob(data, props, tssave.encrypt_blob(new_plain)))
    # verify: everything outside the changed bytes identical; table re-reads
    _, _, vplain, va, vn = _s1(dst)
    assert vplain[va:va + vn] == bytes(s) and len(vplain) == len(plain)
    after = {r[0]: r[2] for r in table(vplain[va:va + vn])}
    for sid, old, cnt, *_ in changed: assert after[sid] == cnt
    return changed


if __name__ == '__main__':
    if sys.argv[1] == 'list':
        _, _, plain, a, n = _s1(sys.argv[2])
        for sid, e, stock, tail, _ in table(plain[a:a + n]): print(f'{sid:45} stock={stock:3} tail={tail.hex(" ")}')
    elif sys.argv[1] == 'refill':
        rules = [(r.split('=')[0], int(r.split('=')[1])) for r in sys.argv[4:]]
        for c in refill(sys.argv[2], sys.argv[3], rules): print(f'  {c[0]:45} {c[1]:3} -> {c[2]:3}   {c[3]} -> {c[4]}')
