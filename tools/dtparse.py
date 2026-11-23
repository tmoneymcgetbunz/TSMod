"""Minimal UE4.27 cooked DataTable reader (tagged properties) for Triangle Strategy.

  python dtparse.py <Table.uasset> [rowfilter]   -> prints rows as JSON-ish text

Also exposes parse(path) -> (names, rows) where each value records its file offset in the
.uexp so values can be patched in place (same-size edits only).
"""
import struct, sys, json


class R:
    def __init__(s, b, p=0): s.b = b; s.p = p
    def i32(s): v = struct.unpack_from('<i', s.b, s.p)[0]; s.p += 4; return v
    def u32(s): v = struct.unpack_from('<I', s.b, s.p)[0]; s.p += 4; return v
    def i64(s): v = struct.unpack_from('<q', s.b, s.p)[0]; s.p += 8; return v
    def f32(s): v = struct.unpack_from('<f', s.b, s.p)[0]; s.p += 4; return v
    def u8(s): v = s.b[s.p]; s.p += 1; return v
    def raw(s, n): v = s.b[s.p:s.p + n]; s.p += n; return v
    def fstr(s):
        n = s.i32()
        if n == 0: return ''
        if n < 0: return s.raw(-n * 2).decode('utf-16le')[:-1]
        return s.raw(n)[:-1].decode('utf-8', 'replace')


def read_summary(ua):
    r = R(ua)
    assert r.u32() == 0x9E2A83C1
    legacy = r.i32(); r.i32(); r.i32(); r.i32()  # legacy ue3, ue4 ver, licensee
    for _ in range(r.i32()): r.raw(20)
    total_header = r.i32(); r.fstr(); r.u32()
    name_count = r.i32(); name_off = r.i32()
    r2 = R(ua, name_off); names = []
    for _ in range(name_count):
        names.append(r2.fstr()); r2.raw(4)
    return names, total_header


class Parser:
    def __init__(s, names, data):
        s.N = names; s.r = R(data)

    def name(s):
        i = s.r.i32(); n = s.r.i32()
        v = s.N[i]
        return v if n == 0 else f'{v}_{n-1}'

    def props(s):
        out = {}
        while True:
            pn = s.name()
            if pn == 'None': return out
            pt = s.name(); size = s.r.i32(); idx = s.r.i32()
            extra = {}
            if pt == 'StructProperty': extra['struct'] = s.name(); s.r.raw(16)
            elif pt == 'BoolProperty': extra['boolpos'] = s.r.p; extra['bool'] = s.r.u8()
            elif pt in ('ByteProperty', 'EnumProperty'): extra['enum'] = s.name()
            elif pt in ('ArrayProperty', 'SetProperty'): extra['inner'] = s.name()
            elif pt == 'MapProperty': extra['k'] = s.name(); extra['v'] = s.name()
            if s.r.u8(): s.r.raw(16)
            start = s.r.p
            val = s.value(pt, size, extra)
            s.r.p = start + size
            key = pn if idx == 0 else f'{pn}[{idx}]'
            out[key] = {'t': pt, 'v': val, 'off': extra.get('boolpos', start), 'size': size}

    def value(s, pt, size, extra):
        r = s.r
        if pt == 'BoolProperty': return bool(extra['bool'])
        if pt == 'IntProperty': return r.i32()
        if pt == 'FloatProperty': return r.f32()
        if pt in ('NameProperty', 'EnumProperty'): return s.name()
        if pt == 'ByteProperty': return s.name() if size == 8 else r.u8()
        if pt == 'StrProperty': return r.fstr()
        if pt == 'StructProperty':
            st = extra['struct']
            if st in ('IntVector',): return [r.i32(), r.i32(), r.i32()]
            if st in ('Vector', 'Rotator'): return [r.f32(), r.f32(), r.f32()]
            if st == 'IntPoint': return [r.i32(), r.i32()]
            if st == 'LinearColor': return [r.f32() for _ in range(4)]
            try: return {k: v['v'] for k, v in s.props().items()}
            except Exception: return f'<{st} {size}b>'
        if pt == 'ArrayProperty':
            n = r.i32(); inner = extra['inner']
            if inner == 'NameProperty': return [s.name() for _ in range(n)]
            if inner == 'IntProperty': return [r.i32() for _ in range(n)]
            if inner == 'StructProperty':
                s.name(); s.name(); r.i32(); r.i32(); s.name(); r.raw(16); r.u8()
                return [{k: v['v'] for k, v in s.props().items()} for _ in range(n)]
            return f'<array {inner} x{n}>'
        return f'<{pt} {size}b>'


def parse(uasset_path):
    ua = open(uasset_path, 'rb').read()
    ue = open(uasset_path[:-7] + '.uexp', 'rb').read()
    return parse_bytes(ua, ue)


def parse_bytes(ua, ue):
    names, _ = read_summary(ua)
    p = Parser(names, ue)
    p.props()          # UDataTable object properties (RowStruct etc.)
    p.r.i32()          # object guid flag / padding (0)
    rows = {}
    for _ in range(p.r.i32()):
        rn = p.name()
        rows[rn] = p.props()
    return names, rows


if __name__ == '__main__':
    names, rows = parse(sys.argv[1])
    flt = sys.argv[2] if len(sys.argv) > 2 else ''
    for k, v in rows.items():
        if flt in k:
            print(k, json.dumps({a: b['v'] for a, b in v.items()}, ensure_ascii=False, default=str))


def read_exports(ua):
    """Return (names, imports, exports, total_header) for a cooked UE4.27 package."""
    r = R(ua)
    r.u32(); r.i32(); r.i32(); r.i32(); r.i32()
    for _ in range(r.i32()): r.raw(20)
    total_header = r.i32(); r.fstr(); r.u32()
    name_count = r.i32(); name_off = r.i32()
    r.i32(); r.i32()  # gatherable text
    exp_count = r.i32(); exp_off = r.i32()
    imp_count = r.i32(); imp_off = r.i32()
    names, _ = read_summary(ua)
    def fn(rr):
        i = rr.i32(); n = rr.i32(); return names[i] if n == 0 else f'{names[i]}_{n-1}'
    ri = R(ua, imp_off); imports = []
    for _ in range(imp_count):
        cp = fn(ri); cn = fn(ri); outer = ri.i32(); on = fn(ri)
        imports.append((cp, cn, outer, on))
    re_ = R(ua, exp_off); exports = []
    for _ in range(exp_count):
        cls = re_.i32(); sup = re_.i32(); tmpl = re_.i32(); outer = re_.i32(); on = fn(re_)
        flags = re_.u32(); size = re_.i64(); off = re_.i64()
        re_.raw(4 * 3 + 16 + 4 + 4 + 4 + 4 * 5)
        exports.append(dict(cls=cls, outer=outer, name=on, size=size, off=off))
    return names, imports, exports, total_header
