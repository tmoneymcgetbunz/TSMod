"""Structural edits to cooked UE4.27 DataTable packages (.uasset + .uexp) for Triangle Strategy.

- add_names(): append entries to the name map (with correct FName hashes) and shift every
  header offset that lies after it.
- add_row(): append a copy of an existing DataTable row under a new row name, and fix the
  export SerialSize and BulkDataStartOffset.

Everything is verified by re-reading (summary, name map, exports, rows) before returning.
"""
import struct

# ---------------------------------------------------------------- FName hashes (UE4.27)
def _crc_table_lsb():
    t = []
    for i in range(256):
        c = i
        for _ in range(8):
            c = (c >> 1) ^ 0xEDB88320 if c & 1 else c >> 1
        t.append(c)
    return t


def _crc_table_msb():
    t = []
    for i in range(256):
        c = i << 24
        for _ in range(8):
            c = ((c << 1) ^ 0x04C11DB7) & 0xFFFFFFFF if c & 0x80000000 else (c << 1) & 0xFFFFFFFF
        t.append(c)
    return t


_LSB, _MSB = _crc_table_lsb(), _crc_table_msb()


def strihash_deprecated(s):          # NonCasePreservingHash
    h = 0
    for ch in s.upper():
        h = ((h >> 8) & 0x00FFFFFF) ^ _MSB[(h ^ ord(ch)) & 0xFF]
    return h & 0xFFFFFFFF


def strcrc32(s):                     # CasePreservingHash (TCHAR = 2 bytes, both bytes fed)
    crc = 0xFFFFFFFF
    for ch in s:
        c = ord(ch)
        for _ in range(4):
            crc = (crc >> 8) ^ _LSB[(crc ^ c) & 0xFF]
            c >>= 8
    return ~crc & 0xFFFFFFFF


def name_hashes(s):
    return struct.pack('<HH', strihash_deprecated(s) & 0xFFFF, strcrc32(s) & 0xFFFF)


# ---------------------------------------------------------------- summary
class _R:
    def __init__(s, b, p=0): s.b = b; s.p = p
    def i32(s):
        v = struct.unpack_from('<i', s.b, s.p)[0]; s.p += 4; return v
    def u32(s):
        v = struct.unpack_from('<I', s.b, s.p)[0]; s.p += 4; return v
    def i64(s):
        v = struct.unpack_from('<q', s.b, s.p)[0]; s.p += 8; return v
    def u16(s):
        v = struct.unpack_from('<H', s.b, s.p)[0]; s.p += 2; return v
    def fstr(s):
        n = s.i32()
        if n == 0: return ''
        if n < 0:
            v = s.b[s.p:s.p - 2 * n].decode('utf-16le')[:-1]; s.p += -2 * n; return v
        v = s.b[s.p:s.p + n - 1].decode('latin1'); s.p += n; return v


OFFSET_FIELDS = ('TotalHeaderSize', 'GatherableTextDataOffset', 'ExportOffset', 'ImportOffset',
                 'DependsOffset', 'SoftPackageReferencesOffset', 'SearchableNamesOffset',
                 'ThumbnailTableOffset', 'AssetRegistryDataOffset', 'WorldTileInfoDataOffset',
                 'PreloadDependencyOffset')


def read_summary(ua):
    """Return dict field -> (value, position, kind)."""
    r = _R(ua); f = {}
    def put(k, kind='i32'):
        p = r.p; v = getattr(r, kind)(); f[k] = (v, p, kind); return v
    assert r.u32() == 0x9E2A83C1
    legacy = r.i32()
    if legacy != -4: r.i32()
    put('FileVersionUE4'); r.i32()
    n = r.i32(); r.p += n * 20
    put('TotalHeaderSize'); r.fstr(); flags = put('PackageFlags', 'u32')
    put('NameCount'); put('NameOffset')
    if f['FileVersionUE4'][0] >= 516 and not (flags & 0x80000000): r.fstr()
    put('GatherableTextDataCount'); put('GatherableTextDataOffset')
    put('ExportCount'); put('ExportOffset'); put('ImportCount'); put('ImportOffset'); put('DependsOffset')
    put('SoftPackageReferencesCount'); put('SoftPackageReferencesOffset')
    put('SearchableNamesOffset'); put('ThumbnailTableOffset')
    r.p += 16                                     # package guid
    gens = r.i32(); f['Generations'] = []
    for _ in range(gens):
        p = r.p; ec = r.i32(); nc = r.i32(); f['Generations'].append((ec, nc, p))
    for _ in range(2):                            # saved-by / compatible-with engine version
        r.u16(); r.u16(); r.u16(); r.u32(); r.fstr()
    put('CompressionFlags', 'u32')
    assert r.i32() == 0, 'compressed chunks not supported'
    put('PackageSource', 'u32')
    for _ in range(r.i32()): r.fstr()             # additional packages to cook
    if legacy > -7: r.i32()
    put('AssetRegistryDataOffset'); put('BulkDataStartOffset', 'i64'); put('WorldTileInfoDataOffset')
    for _ in range(r.i32()): r.i32()              # chunk ids
    put('PreloadDependencyCount'); put('PreloadDependencyOffset')
    f['_end'] = r.p
    return f


def read_names(ua, f):
    r = _R(ua, f['NameOffset'][0]); out = []
    for _ in range(f['NameCount'][0]):
        s = r.fstr(); h = ua[r.p:r.p + 4]; r.p += 4; out.append((s, h))
    return out, r.p


EXPORT_SIZE = 104


def read_exports(ua, f):
    out = []
    for i in range(f['ExportCount'][0]):
        p = f['ExportOffset'][0] + i * EXPORT_SIZE
        size, off = struct.unpack_from('<qq', ua, p + 28)
        out.append({'pos': p, 'SerialSize': size, 'SerialOffset': off})
    return out


def check_hashes(ua):
    f = read_summary(ua)
    names, _ = read_names(ua, f)
    bad = [s for s, h in names if h != name_hashes(s)]
    return len(names), bad


# ---------------------------------------------------------------- edits
import re as _re
_SPLIT = _re.compile(r'^(.+)_(0|[1-9][0-9]{0,8})$')


def split_fname(s):
    """UE4 FName rule: a trailing _<number> (no leading zero, except '0') is stored as base + (number+1).
    'X_45' -> ('X', 46); 'X_05' -> ('X_05', 0); 'X_RANK1' -> ('X_RANK1', 0).
    The engine applies this when it builds FNames from strings at runtime, so name maps must hold the base."""
    m = _SPLIT.match(s)
    return (m.group(1), int(m.group(2)) + 1) if m else (s, 0)


def ref(idx, s):
    """(name-map index, number) for string s, given {base_name: index}."""
    base, num = split_fname(s)
    return idx[base], num


def add_names(ua, uexp, new_names):
    """Ensure the name map can express every string in new_names (adds split *bases*).
    Returns (ua2, uexp, {base_name: index}); use ref(idx, s) for the (index, number) pair."""
    f = read_summary(ua)
    names, names_end = read_names(ua, f)
    existing = [s for s, _ in names]
    new_names = list(dict.fromkeys(split_fname(n)[0] for n in new_names))
    add = [n for n in new_names if n not in existing]
    idx = {n: existing.index(n) for n in new_names if n in existing}
    if not add: return ua, uexp, idx
    blob = b''
    for n in add:
        e = n.encode('latin1') + b'\0'
        blob += struct.pack('<i', len(e)) + e + name_hashes(n)
        idx[n] = len(existing); existing.append(n)
    d = len(blob)
    out = bytearray(ua[:names_end]) + blob + ua[names_end:]
    def setf(k, v):
        _, p, kind = f[k]; struct.pack_into({'i32': '<i', 'u32': '<I', 'i64': '<q'}[kind], out, p, v)
    setf('NameCount', f['NameCount'][0] + len(add))
    for k in OFFSET_FIELDS:
        v = f[k][0]
        if v and v >= names_end: setf(k, v + d)
    setf('BulkDataStartOffset', f['BulkDataStartOffset'][0] + d)
    for ec, nc, p in f['Generations']:
        struct.pack_into('<ii', out, p, ec, nc + len(add))
    f2 = read_summary(bytes(out))
    for e in read_exports(bytes(out), f2):        # export data sits after the header
        struct.pack_into('<q', out, e['pos'] + 36, e['SerialOffset'] + d)
    out = bytes(out)
    # verify
    f3 = read_summary(out); n3, _ = read_names(out, f3)
    assert [s for s, _ in n3] == existing and f3['TotalHeaderSize'][0] == len(out)
    return out, uexp, idx


def dt_rows(names, uexp):
    """Locate rows in a DataTable .uexp. Returns (numrows_pos, [(rowname, start, end)], rows_end)."""
    import dtparse
    p = dtparse.Parser(names, uexp)
    p.props(); p.r.i32()
    np_ = p.r.p; n = p.r.i32(); rows = []
    for _ in range(n):
        s = p.r.p; rn = p.name(); p.props(); rows.append((rn, s, p.r.p))
    return np_, rows, p.r.p


def _fstring(s):
    try:
        b = s.encode('ascii') + b'\0'; return struct.pack('<i', len(b)) + b
    except UnicodeEncodeError:
        b = s.encode('utf-16le') + b'\0\0'; return struct.pack('<i', -(len(b) // 2)) + b


def set_str(ua, uexp, row, field, value):
    """Set a StrProperty (size may change). Returns (ua2, uexp2)."""
    import dtparse
    f = read_summary(ua)
    _, rows = dtparse.parse_bytes(ua, uexp)
    prop = rows[row][field]
    assert prop['t'] == 'StrProperty', f'{row}.{field} is {prop["t"]}'
    off, size = prop['off'], prop['size']
    new = _fstring(value)
    out = bytearray(uexp[:off]) + new + uexp[off + size:]
    assert struct.unpack_from('<i', out, off - 9)[0] == size, 'tag layout not as expected'
    struct.pack_into('<i', out, off - 9, len(new))
    d = len(new) - size
    ua2 = bytearray(ua)
    ex = read_exports(ua, f)
    assert len(ex) == 1
    struct.pack_into('<q', ua2, ex[0]['pos'] + 28, ex[0]['SerialSize'] + d)
    _, p, _ = f['BulkDataStartOffset']; struct.pack_into('<q', ua2, p, f['BulkDataStartOffset'][0] + d)
    ua2, out = bytes(ua2), bytes(out)
    _, rows2 = dtparse.parse_bytes(ua2, out)
    assert rows2[row][field]['v'] == value and len(rows2) == len(rows)
    return ua2, out


def add_rows(ua, uexp, specs, self_field='SelfId'):
    """Bulk-append rows. specs = [(src_row, new_row, {field: value})]; values for Float/Int/Bool/Name/Enum
    properties are patched inside the copied bytes (same size). Returns (ua2, uexp2)."""
    import dtparse
    need = [n for _, n, _ in specs] + [v for _, _, s in specs for v in s.values() if isinstance(v, str)]
    ua, uexp, _ = add_names(ua, uexp, list(dict.fromkeys(need)))
    f = read_summary(ua)
    names = [s for s, _ in read_names(ua, f)[0]]
    idx = {n: i for i, n in enumerate(names)}
    def fref(v):
        return ref(idx, v)
    np_, rows, rows_end = dt_rows(names, uexp)
    bounds = {r[0]: (r[1], r[2]) for r in rows}
    _, parsed = dtparse.parse_bytes(ua, uexp)
    blob = bytearray()
    for src, new, sets in specs:
        assert new not in bounds, f'{new} already exists'
        s, e = bounds[src]
        rec = bytearray(uexp[s:e])
        old_ref = uexp[s:s + 8]
        struct.pack_into('<ii', rec, 0, *ref(idx, new))
        if self_field:                            # parsed offset, not a byte search (see add_row)
            k = parsed[src][self_field]['off'] - s; assert rec[k:k + 8] == old_ref
            struct.pack_into('<ii', rec, k, *ref(idx, new))
        for field, val in sets.items():
            p = parsed[src][field]; rel = p['off'] - s; t = p['t']
            if t == 'FloatProperty': struct.pack_into('<f', rec, rel, float(val))
            elif t == 'IntProperty': struct.pack_into('<i', rec, rel, int(val))
            elif t == 'BoolProperty': rec[rel] = 1 if val else 0
            elif t in ('NameProperty', 'EnumProperty') or (t == 'ByteProperty' and p['size'] == 8):
                struct.pack_into('<ii', rec, rel, *fref(val))
            else: raise ValueError(f'unsupported {t} for {field}')
        blob += rec
        bounds[new] = None
    out = bytearray(uexp[:rows_end]) + blob + uexp[rows_end:]
    struct.pack_into('<i', out, np_, len(rows) + len(specs))
    d = len(blob)
    ua2 = bytearray(ua)
    ex = read_exports(ua, f); assert len(ex) == 1
    struct.pack_into('<q', ua2, ex[0]['pos'] + 28, ex[0]['SerialSize'] + d)
    _, p, _ = f['BulkDataStartOffset']; struct.pack_into('<q', ua2, p, f['BulkDataStartOffset'][0] + d)
    ua2, out = bytes(ua2), bytes(out)
    _, rows2 = dtparse.parse_bytes(ua2, out)
    assert len(rows2) == len(rows) + len(specs)
    for src, new, sets in specs:
        for field, val in sets.items():
            got = rows2[new][field]['v']
            assert (abs(got - float(val)) < 1e-3) if isinstance(got, float) else str(got) == str(val), (new, field, got, val)
    return ua2, out


def add_row(ua, uexp, src_row, new_row, self_field='SelfId'):
    """Append a copy of src_row named new_row (also sets its SelfId). Returns (ua2, uexp2)."""
    ua, uexp, idx = add_names(ua, uexp, [new_row])
    f = read_summary(ua)
    names = [s for s, _ in read_names(ua, f)[0]]
    np_, rows, rows_end = dt_rows(names, uexp)
    assert new_row not in [r[0] for r in rows], f'{new_row} already exists'
    src = [r for r in rows if r[0] == src_row]
    assert src, f'{src_row} not found'
    _, s, e = src[0]
    rec = bytearray(uexp[s:e])
    struct.pack_into('<ii', rec, 0, *ref(idx, new_row))
    old_ref = uexp[s:s + 8]
    if self_field:                                # SelfId value: use the parsed offset. A byte search for the row-name
        import dtparse                            # ref can hit the tag's size field when the name index is 8 (BOOK_RANK2)
        k = dtparse.parse_bytes(ua, uexp)[1][src_row][self_field]['off'] - s
        assert rec[k:k + 8] == old_ref, 'SelfId value is not the row name'
        struct.pack_into('<ii', rec, k, *ref(idx, new_row))
    out = bytearray(uexp[:rows_end]) + rec + uexp[rows_end:]
    struct.pack_into('<i', out, np_, len(rows) + 1)
    d = len(rec)
    ua2 = bytearray(ua)
    ex = read_exports(ua, f)
    assert len(ex) == 1, 'single-export DataTables only'
    struct.pack_into('<q', ua2, ex[0]['pos'] + 28, ex[0]['SerialSize'] + d)
    _, p, _ = f['BulkDataStartOffset']; struct.pack_into('<q', ua2, p, f['BulkDataStartOffset'][0] + d)
    ua2, out = bytes(ua2), bytes(out)
    # verify
    f2 = read_summary(ua2)
    assert f2['BulkDataStartOffset'][0] == len(ua2) + len(out) - 4
    assert read_exports(ua2, f2)[0]['SerialSize'] == len(out) - 4
    _, rows2, _ = dt_rows(names, out)
    assert [r[0] for r in rows2] == [r[0] for r in rows] + [new_row]
    return ua2, out


def rename_names(ua, mapping):
    """Replace name-map strings (exact matches, or substring replacement when mapping values are
    (old_sub, new_sub) pairs under key None). Indices are kept, so all references stay valid; header
    offsets after the name map shift by the size change. Returns the new .uasset bytes."""
    f = read_summary(ua)
    names, names_end = read_names(ua, f)
    subs = mapping.get(None, [])
    blob = b''
    for s, h in names:
        n = mapping.get(s, s)
        for a, b in subs: n = n.replace(a, b)
        if n == s: blob += struct.pack('<i', len(s) + 1) + s.encode('latin1') + b'\0' + h
        else:
            e = n.encode('latin1') + b'\0'
            blob += struct.pack('<i', len(e)) + e + name_hashes(n)
    start = f['NameOffset'][0]
    d = len(blob) - (names_end - start)
    out = bytearray(ua[:start]) + blob + ua[names_end:]
    def setf(k, v):
        _, p, kind = f[k]; struct.pack_into({'i32': '<i', 'u32': '<I', 'i64': '<q'}[kind], out, p, v)
    for k in OFFSET_FIELDS:
        v = f[k][0]
        if v and v >= names_end: setf(k, v + d)
    setf('BulkDataStartOffset', f['BulkDataStartOffset'][0] + d)
    f2 = read_summary(bytes(out))
    for e in read_exports(bytes(out), f2):
        struct.pack_into('<q', out, e['pos'] + 36, e['SerialOffset'] + d)
    out = bytes(out)
    f3 = read_summary(out); n3, _ = read_names(out, f3)
    assert f3['TotalHeaderSize'][0] == len(out) and len(n3) == len(names)
    assert not check_hashes(out)[1]
    return out
