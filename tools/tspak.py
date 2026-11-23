"""Minimal reader for TRIANGLE STRATEGY's UE4.27 pak (version 11, encrypted index, zlib).

Usage:
  python tspak.py list  <pak> [substring]        -> prints paths (optionally filtered)
  python tspak.py extract <pak> <outdir> <substring...>  -> extracts matching files

Uses pycryptodome if installed, else tools/aes_py.py (pure Python, slower). Key below is the publicly posted PC key (verified against v1.1.0).
"""
import struct, sys, os, zlib, io

KEY = bytes.fromhex('75D4C74524DE13DD968F3DE80349A6C984912E76A67E6851280EF1F01BFE4946')
try:                                    # pycryptodome when installed (fast) ...
    from Crypto.Cipher import AES
    AESB = AES.new(KEY, AES.MODE_ECB)
except ImportError:                     # ... else the pure-Python decryptor (Steam Deck without extra packages)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from aes_py import AES256Decryptor
    AESB = AES256Decryptor(KEY)


def dec(b):
    return AESB.decrypt(b)


def align16(n):
    return (n + 15) & ~15


class R:
    def __init__(s, b): s.b = b; s.p = 0
    def u32(s): v = struct.unpack_from('<I', s.b, s.p)[0]; s.p += 4; return v
    def i32(s): v = struct.unpack_from('<i', s.b, s.p)[0]; s.p += 4; return v
    def u64(s): v = struct.unpack_from('<Q', s.b, s.p)[0]; s.p += 8; return v
    def raw(s, n): v = s.b[s.p:s.p + n]; s.p += n; return v
    def fstr(s):
        n = s.i32()
        if n == 0: return ''
        if n < 0:
            v = s.raw(-n * 2).decode('utf-16le'); return v[:-1]
        return s.raw(n)[:-1].decode('utf-8', 'replace')


class Pak:
    def __init__(s, path):
        s.f = open(path, 'rb')
        s.f.seek(0, 2); size = s.f.tell()
        # footer: guid16, encidx1, magic4, ver4, off8, size8, hash20, 5*32 comp names
        s.f.seek(size - (16 + 1 + 4 + 4 + 8 + 8 + 20 + 5 * 32))
        ft = s.f.read(16 + 1 + 4 + 4 + 8 + 8 + 20 + 5 * 32)
        enc_idx = ft[16]
        magic, ver, ioff, isz = struct.unpack_from('<IIQQ', ft, 17)
        assert magic == 0x5A6F12E1 and ver == 11, (hex(magic), ver)
        s.comp = [ft[61 + 32 * i:93 + 32 * i].rstrip(b'\0').decode() for i in range(5)]
        s.comp = ['None'] + [c for c in s.comp]
        idx = s.read_enc(ioff, isz) if enc_idx else s.read_plain(ioff, isz)
        r = R(idx)
        s.mount = r.fstr()
        s.count = r.i32()
        r.u64()  # path hash seed
        if r.u32(): r.raw(8 + 8 + 20)  # path hash index (skip)
        has_fdi = r.u32()
        fdi_off = r.u64(); fdi_sz = r.u64(); r.raw(20)
        enc_sz = r.i32(); s.encoded = r.raw(enc_sz)
        nfiles = r.i32()
        s.nonenc = []  # rarely used; parse lazily if needed
        s.nonenc_raw = idx[r.p:]
        fdi = R(s.read_enc(fdi_off, fdi_sz) if enc_idx else s.read_plain(fdi_off, fdi_sz))   # mod paks: plain index
        s.files = {}
        for _ in range(fdi.i32()):
            d = fdi.fstr()
            for _ in range(fdi.i32()):
                fn = fdi.fstr(); loc = fdi.i32()
                s.files[(d + fn).lstrip('/')] = loc

    def read_plain(s, off, n):
        s.f.seek(off); return s.f.read(n)

    def read_enc(s, off, n):
        s.f.seek(off); return dec(s.f.read(align16(n)))[:n]

    def entry(s, loc):
        if loc < 0:
            raise NotImplementedError('non-encoded entry')
        r = R(s.encoded); r.p = loc
        bits = r.u32()
        cmi = (bits >> 23) & 0x3f
        encrypted = (bits >> 22) & 1
        nblocks = (bits >> 6) & 0xffff
        bsize = bits & 0x3f
        bsize = r.u32() if bsize == 0x3f else bsize << 11
        off = r.u32() if bits & (1 << 31) else r.u64()
        usize = r.u32() if bits & (1 << 30) else r.u64()
        size = usize
        if cmi:
            size = r.u32() if bits & (1 << 29) else r.u64()
        hdr = 8 + 8 + 8 + 4 + 20 + 1 + 4
        if cmi: hdr += 4 + 16 * nblocks
        blocks = []
        if cmi and nblocks:
            if nblocks == 1 and not encrypted:
                blocks = [(hdr, hdr + size)]
            else:
                cur = hdr
                for _ in range(nblocks):
                    bs = r.u32(); blocks.append((cur, cur + bs))
                    cur += align16(bs) if encrypted else bs
        return dict(off=off, usize=usize, size=size, cm=s.comp[cmi], enc=encrypted, blocks=blocks, hdr=hdr)

    def read(s, path):
        e = s.entry(s.files[path])
        if e['cm'] == 'None':
            s.f.seek(e['off'] + e['hdr'])
            n = align16(e['size']) if e['enc'] else e['size']
            data = s.f.read(n)
            return (dec(data) if e['enc'] else data)[:e['size']]
        out = io.BytesIO()
        for a, b in e['blocks']:
            s.f.seek(e['off'] + a)
            n = b - a
            chunk = s.f.read(align16(n) if e['enc'] else n)
            if e['enc']: chunk = dec(chunk)
            out.write(zlib.decompress(chunk[:n]))
        return out.getvalue()[:e['usize']]


if __name__ == '__main__':
    cmd, pakpath = sys.argv[1], sys.argv[2]
    p = Pak(pakpath)
    if cmd == 'list':
        flt = sys.argv[3] if len(sys.argv) > 3 else ''
        for k in sorted(p.files):
            if flt.lower() in k.lower(): print(k)
    elif cmd == 'extract':
        outdir = sys.argv[3]; pats = [x.lower() for x in sys.argv[4:]]
        n = 0
        for k in sorted(p.files):
            if any(x in k.lower() for x in pats):
                dst = os.path.join(outdir, k)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                open(dst, 'wb').write(p.read(k)); n += 1
        print('extracted', n)
