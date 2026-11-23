"""TRIANGLE STRATEGY (PC) save files: GVAS wrapper with a single `bulkData` byte array.

  python tssave.py info <file.sav>
"""
import struct, sys


class R:
    def __init__(s, b, p=0): s.b = b; s.p = p
    def i32(s): v = struct.unpack_from('<i', s.b, s.p)[0]; s.p += 4; return v
    def u32(s): v = struct.unpack_from('<I', s.b, s.p)[0]; s.p += 4; return v
    def u16(s): v = struct.unpack_from('<H', s.b, s.p)[0]; s.p += 2; return v
    def i64(s): v = struct.unpack_from('<q', s.b, s.p)[0]; s.p += 8; return v
    def u8(s): v = s.b[s.p]; s.p += 1; return v
    def raw(s, n): v = s.b[s.p:s.p + n]; s.p += n; return v
    def fstr(s):
        n = s.i32()
        if n == 0: return ''
        if n < 0: return s.raw(-n * 2).decode('utf-16le')[:-1]
        return s.raw(n)[:-1].decode('utf-8', 'replace')


def parse(data):
    r = R(data)
    assert r.raw(4) == b'GVAS'
    hdr = {'save_ver': r.i32(), 'pkg_ver': r.i32(),
           'engine': (r.u16(), r.u16(), r.u16(), r.u32()), 'branch': r.fstr(), 'cv_format': r.i32()}
    n = r.i32(); r.raw(20 * n); hdr['custom_versions'] = n
    hdr['class'] = r.fstr()
    props = []
    while True:
        name = r.fstr()
        if name in ('None', ''): break
        ptype = r.fstr(); size = r.i64()
        if ptype == 'ArrayProperty':
            inner = r.fstr(); r.u8()
            start = r.p
            count = r.i32()
            props.append({'name': name, 'type': ptype, 'inner': inner, 'size': size,
                          'count': count, 'data_off': r.p, 'data': data[r.p:r.p + count]})
            r.p = start + size
        else:
            r.u8(); start = r.p
            props.append({'name': name, 'type': ptype, 'size': size, 'off': start})
            r.p = start + size
    hdr['end'] = r.p
    hdr['trailer'] = data[r.p:]
    return hdr, props


# ---------------------------------------------------------------- NWER blob cipher
# Format and algorithm as documented in ShaneQi/triangle-strategy-save-editor (core.js header),
# reimplemented here:
#   0x00 'NWER' | 0x04 u16 version | 0x06 u16 1 | 0x08 u8 kind (0 system, 1 game) | 0x09..0x0b flags
#   0x0c 20B SHA-1 of plaintext[0x40:-20] (= key) | 0x20 32B zero | 0x40.. ciphertext; plaintext ends with SHA-1
import hashlib


def _tables(K):
    n = len(K); T = list(range(256))
    for r in range(128):
        for j in range(n):
            a = (K[(j + 1) % n] + r) & 255; b = (K[j] + r) & 255
            T[a], T[b] = T[b], T[a]
    INV = [0] * 256
    for i, v in enumerate(T): INV[v] = i
    return bytes(T), bytes(INV)


def decrypt_blob(blob):
    K = blob[12:32]; _, INV = _tables(K)
    n = len(K)
    body = bytes(INV[c ^ K[i % n]] for i, c in enumerate(blob[0x40:]))
    plain = blob[:0x40] + body
    ok = hashlib.sha1(plain[0x40:-20]).digest() == K and plain[-20:] == K
    return plain, ok


def encrypt_blob(plain):
    p = bytearray(plain)
    K = hashlib.sha1(bytes(p[0x40:-20])).digest()
    p[12:32] = K; p[-20:] = K
    T, _ = _tables(K)
    body = bytes(T[b] ^ K[i % 20] for i, b in enumerate(p[0x40:]))
    return bytes(p[:0x40]) + body


def replace_blob(data, props, new_blob):
    """Rebuild the .sav with a new bulkData blob (fixes array count and property size)."""
    p = props[0]; off = p['data_off']; old = p['count']
    out = bytearray(data[:off]) + new_blob + data[off + old:]
    struct.pack_into('<i', out, off - 4, len(new_blob))
    # property size (int64) sits just before the inner-type FString: find by value
    size_pos = data.rfind(struct.pack('<q', old + 4), 0, off)
    struct.pack_into('<q', out, size_pos, len(new_blob) + 4)
    return bytes(out)


def sections(plain):
    """Game data plaintext: header(0x40) + 3 x (int32 len + bytes) + SHA-1."""
    out = []; o = 0x40
    for _ in range(3):
        n = struct.unpack_from('<i', plain, o)[0]; out.append((o + 4, n)); o += 4 + n
    return out, o


def preview(plain):
    import datetime
    secs, _ = sections(plain); o = secs[0][0]
    ticks, played = struct.unpack_from('<QQ', plain, o); o += 16
    lvl = struct.unpack_from('<H', plain, o)[0]; o += 3
    r = R(plain, o)
    return {'saved': str(datetime.datetime(1, 1, 1) + datetime.timedelta(microseconds=ticks // 10)),
            'play_time': str(datetime.timedelta(seconds=played)), 'level': lvl, 'leader': r.fstr(), 'location': r.fstr()}


STAT_NAMES = ['level', 'exp', 'move_x100', 'jump_up', 'jump_down', 'hp', 'tp', 'speed_f', 'tp_turn_f',
              'str', 'int', 'dex', 'agi', 'luk', 'def', 'mdf']


def units(plain):
    """Unit records in the game-state section: FString unit-master id, stat block (16 int32) at +83
    from the string's length field + 3 (verified on 31 units). Returns {unit_master: stats}."""
    import re
    secs, _ = sections(plain); a, n = secs[1]; s1 = plain[a:a + n]
    out = {}
    for m in re.finditer(rb'\x00\x00\x00(UNIT_MASTER_CH_[A-Z0-9_]+)\x00', s1):
        if m.start() + 83 + 64 > len(s1): continue
        v = struct.unpack_from('<16i', s1, m.start() + 83)
        if 1 <= v[0] <= 99 and 0 <= v[1] < 100 and 100 <= v[2] <= 1500 and 1 <= v[5] <= 9999:
            st = dict(zip(STAT_NAMES, v)); st['offset_in_s1'] = m.start() + 83
            out[m.group(1).decode()] = st
    return out


if __name__ == '__main__':
    cmd = sys.argv[1]; d = open(sys.argv[2], 'rb').read()
    if cmd == 'summary':          # tssave.py summary in.sav
        h, props = parse(d); plain, ok = decrypt_blob(props[0]['data'])
        print('sha1', 'ok' if ok else 'MISMATCH', '| kind', plain[8], '| version', struct.unpack_from('<H', plain, 4)[0])
        if plain[8] == 1:
            print(preview(plain))
            for k, s in units(plain).items():
                print(f"  {k:24} Lv{s['level']:2} EXP{s['exp']:3} HP{s['hp']:4} STR{s['str']:3} INT{s['int']:3} DEF{s['def']:3} MDF{s['mdf']:3} move{s['move_x100'] / 100:g}")
        sys.exit()
    h, props = parse(d)
    if cmd == 'info':
        print({k: v for k, v in h.items() if k != 'trailer'}, 'trailer', h['trailer'].hex())
        for p in props: print({k: v for k, v in p.items() if k != 'data'})
    elif cmd == 'decrypt':       # tssave.py decrypt in.sav out.bin
        plain, ok = decrypt_blob(props[0]['data'])
        open(sys.argv[3], 'wb').write(plain); print('sha1 ok' if ok else 'SHA1 MISMATCH', len(plain))
    elif cmd == 'encrypt':       # tssave.py encrypt template.sav plain.bin out.sav
        plain = open(sys.argv[3], 'rb').read()
        open(sys.argv[4], 'wb').write(replace_blob(d, props, encrypt_blob(plain)))
