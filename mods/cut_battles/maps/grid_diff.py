"""Compare two baked battle grids (Map/WBAsset/*.uexp) record by record (partial decode, see SYSTEMS.md section 6).

Header (after the UE property block): version, then three uint16 (21, 21, 21) and uint32 cell count (441 = 21x21).
Each terrain layer record contains its panel-name FString (TEXT_COMMON_PANEL_NAME_*); we split on those, keep the bytes
between names (layer header + properties), and diff the sequences.
Run: python grid_diff.py <a.uexp> <b.uexp>
"""
import re, sys, struct, collections, difflib

def records(path):
    b = open(path, 'rb').read()
    i = b.find(b'\x15\x00\x15\x00\x15\x00')
    hdr = struct.unpack_from('<HHHI', b, i)
    pos = [m.start() - 4 for m in re.finditer(rb'TEXT_COMMON_PANEL_NAME_', b)]
    recs = []
    for n, p in enumerate(pos):
        ln = struct.unpack_from('<i', b, p)[0]
        name = b[p + 4:p + 3 + ln].decode()[len('TEXT_COMMON_PANEL_NAME_'):]
        end = pos[n + 1] if n + 1 < len(pos) else len(b)
        pre = b[p - 12:p]            # bytes just before the name: layer header (flags, height...)
        recs.append((name, pre.hex(), b[p + 4 + ln:end].hex()))
    return hdr, recs

(ha, a), (hb, b) = records(sys.argv[1]), records(sys.argv[2])
print('header A', ha, 'records', len(a)); print('header B', hb, 'records', len(b))
print('terrain A', dict(collections.Counter(r[0] for r in a)))
print('terrain B', dict(collections.Counter(r[0] for r in b)))
sm = difflib.SequenceMatcher(None, [r[0] for r in a], [r[0] for r in b], autojunk=False)
print('terrain sequence similarity', round(sm.ratio(), 3))
same_full = sum(1 for x, y in zip(a, b) if x == y)
print('records identical at same index (all bytes)', same_full)
for tag, i1, i2, j1, j2 in sm.get_opcodes():
    if tag != 'equal': print(' ', tag, f'A[{i1}:{i2}]', [r[0] for r in a[i1:i2]][:8], f'B[{j1}:{j2}]', [r[0] for r in b[j1:j2]][:8])
