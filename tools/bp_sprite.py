"""Edit a character blueprint's sprite variants: Character/<id>/BP_<id>, SpriteManagerComponent.FlipbookOverrideDatas.

[read + Test 12, 2026-11-16] FlipbookOverrideDatas = Map<ENeweraFlipbookOverrideType, {AdditionalUnitHeight,
SubTypeIdString (frame folder, e.g. "TypeHorse"), AnimationDatas}>. The actor only uses variants listed here; any
other requested variant (e.g. HORSE_RANK2 for a promoted cavalry unit) falls back to plain on-foot DEFAULT.
Hossabara (P017): HORSE->TypeHorse, HORSE_RANK2->TypeHorse, HORSE_RANK3->TypeHorse_Rank3. Exharme (N204): HORSE only.

mod.json key "bp_sprite": list of
  {"char": "N204", "copy_override": "HORSE", "to": ["HORSE_RANK2", "HORSE_RANK3"]}
      adds entries identical to the <copy_override> one under the new keys (same frame folder and data)

  python tools/bp_sprite.py show <CHAR>
"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import uasset_edit as U

CH = 'TRIANGLE_STRATEGY/Content/Newera/Character/'


class BP:
    def __init__(self, ua, ue):
        self.ua, self.ue = bytes(ua), bytearray(ue)
        self.f = U.read_summary(self.ua)
        self.nm = [n for n, _ in U.read_names(self.ua, self.f)[0]]
        self.idx = {n: i for i, n in enumerate(self.nm)}
        self.ex = U.read_exports(self.ua, self.f)

    def name(self, p, b=None):
        b = self.ue if b is None else b
        i, n = struct.unpack_from('<ii', b, p)
        return self.nm[i] + (f'_{n - 1}' if n else '')

    def find(self):
        """-> (export_index, map_tag_pos (absolute in uexp))"""
        pat = struct.pack('<ii', self.idx['FlipbookOverrideDatas'], 0)
        hits = []
        for k, e in enumerate(self.ex):
            o = e['SerialOffset'] - len(self.ua)
            j = self.ue.find(pat, o, o + e['SerialSize'])
            if j >= 0 and self.name(j + 8) == 'MapProperty': hits.append((k, j))
        assert len(hits) == 1, hits
        return hits[0]

    def entries(self):
        k, t = self.find()
        p = t + 16; size = struct.unpack_from('<i', self.ue, p)[0]; p += 8
        assert self.name(p) == 'EnumProperty' and self.name(p + 8) == 'StructProperty'
        p += 17; start = p
        cnt = struct.unpack_from('<i', self.ue, p + 4)[0]; p += 8; out = []
        for _ in range(cnt):
            s = p; key = self.name(p).split('::')[1]; p += 8
            sub = None
            while True:                                   # struct value: tagged properties until None
                n = self.name(p); p += 8
                if n == 'None': break
                typ = self.name(p); sz = struct.unpack_from('<i', self.ue, p + 8)[0]; p += 16
                if typ == 'MapProperty': p += 16
                elif typ == 'StructProperty': p += 16 + 8 + 1 - 1
                elif typ in ('EnumProperty', 'ByteProperty'): p += 8
                elif typ == 'ArrayProperty': p += 8
                elif typ == 'BoolProperty': pass
                p += 1
                if n == 'SubTypeIdString':
                    l = struct.unpack_from('<i', self.ue, p)[0]; sub = self.ue[p + 4:p + 4 + l - 1].decode('latin1')
                p += sz
            out.append({'key': key, 'start': s, 'end': p, 'sub': sub})
        assert p == start + size, (p, start, size)
        return k, t, out

    def apply(self, edits):
        for e in edits:
            need = [f'ENeweraFlipbookOverrideType::{t}' for t in e['to']]
            if any(n not in self.idx for n in need):
                ua, ue, _ = U.add_names(self.ua, bytes(self.ue), need)
                self.__init__(ua, ue)
            k, t, ents = self.entries()
            have = {x['key'] for x in ents}
            src = next(x for x in ents if x['key'] == e['copy_override'])
            blob = b''
            for to in e['to']:
                if to in have: continue
                raw = bytearray(self.ue[src['start']:src['end']])
                raw[0:8] = struct.pack('<ii', self.idx[f'ENeweraFlipbookOverrideType::{to}'], 0)
                blob += raw
            n = len(blob) // (src['end'] - src['start'])
            if not blob: continue
            at = ents[-1]['end']; d = len(blob)
            self.ue[at:at] = blob
            struct.pack_into('<i', self.ue, t + 16, struct.unpack_from('<i', self.ue, t + 16)[0] + d)   # map size
            cp = t + 24 + 17 + 4
            struct.pack_into('<i', self.ue, cp, struct.unpack_from('<i', self.ue, cp)[0] + n)          # count
            ua = bytearray(self.ua)
            for i, x in enumerate(self.ex):
                if i == k: struct.pack_into('<q', ua, x['pos'] + 28, x['SerialSize'] + d)
                elif x['SerialOffset'] > self.ex[k]['SerialOffset']:
                    struct.pack_into('<q', ua, x['pos'] + 36, x['SerialOffset'] + d)
            _, p, _ = self.f['BulkDataStartOffset']; struct.pack_into('<q', ua, p, self.f['BulkDataStartOffset'][0] + d)
            self.__init__(bytes(ua), bytes(self.ue))
            print(f"  bp_sprite {e['char']}: +{n} FlipbookOverrideDatas ({', '.join(e['to'])} = {e['copy_override']}, folder {src['sub']})")
        return self


def _pak():
    import tspak
    return tspak.Pak(paths.game_pak())


def apply_to_stage(edits, stage, pak=None):
    pak = pak or _pak()
    by = {}
    for e in edits: by.setdefault(e['char'], []).append(e)
    for c, es in by.items():
        path = f'{CH}{c}/BP_{c}'
        bp = BP(pak.read(path + '.uasset'), pak.read(path + '.uexp')).apply(es)
        # verify: re-parse, header/export consistency, hashes
        v = BP(bp.ua, bp.ue); _, _, ents = v.entries()
        assert not U.check_hashes(v.ua)[1]
        last = max(v.ex, key=lambda x: x['SerialOffset'])
        assert last['SerialOffset'] + last['SerialSize'] <= len(v.ua) + len(v.ue) - 4
        assert v.f['BulkDataStartOffset'][0] == len(v.ua) + len(v.ue) - 4
        out = os.path.join(stage, *path.split('/'))
        os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out + '.uasset', 'wb').write(v.ua); open(out + '.uexp', 'wb').write(bytes(v.ue))
        print(f"  bp_sprite {c}: variants now {[(x['key'], x['sub']) for x in ents]}")


if __name__ == '__main__':
    if sys.argv[1] == 'show':
        c = sys.argv[2]; pak = _pak(); path = f'{CH}{c}/BP_{c}'
        _, _, ents = BP(pak.read(path + '.uasset'), pak.read(path + '.uexp')).entries()
        for x in ents: print(f"  {x['key']:14} folder={x['sub']}  ({x['end'] - x['start']} bytes)")
