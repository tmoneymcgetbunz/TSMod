"""Edit Data/DataAsset/FlipbookStatic: the sprite lookup table the game uses for every unit sprite.

Structure [read 2026-11-16]: AnimationDatasEx = Map<ECharacterId, {Objects: Map<
  {AnimationType, NeweraFlipbookOverrideType, WeaponRank}, SoftObjectPath -> AnimationData>}>.
The game asks for (character, override, animation, rank). Class rank picks the override suffix: MIDDLE -> *_RANK2,
HIGH -> *_RANK3 (a cavalry unit asks for HORSE_RANK2/3). Missing entries fall back to the plain DEFAULT set.
The main export is the last one in the package, so a size change only touches its SerialSize and BulkDataStartOffset.

mod.json key "flipbook_static": list of edits
  {"char": "N204", "copy_override": "HORSE", "to": ["HORSE_RANK2", "HORSE_RANK3"], "rename_paths": true}
        adds every <to> key, using the same AnimationData as the <copy_override> key, or with rename_paths the
        cloned asset of the same name with <to> (made by sprite_clone.py; names are added to the package)
  {"char": "N204", "anim": "UIC_BattleIdle", "remap": {"DEFAULT": "HORSE"}}
        repoints existing keys of one animation from one override's data to another's
Every name involved must already be in the package's name map (nothing is added).

  python tools/flipbook_static.py show <CHAR>        summary of a character's entries in the vanilla asset
"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import uasset_edit as U

ASSET = 'TRIANGLE_STRATEGY/Content/Newera/Data/DataAsset/FlipbookStatic'


class FS:
    def __init__(self, ua, ue):
        self.ua, self.ue = bytes(ua), bytearray(ue)
        self.f = U.read_summary(self.ua)
        self.nm = [n for n, _ in U.read_names(self.ua, self.f)[0]]
        self.idx = {n: i for i, n in enumerate(self.nm)}
        ex = U.read_exports(self.ua, self.f)
        self.main = max(ex, key=lambda e: e['SerialOffset'])
        assert self.main['SerialOffset'] + self.main['SerialSize'] == len(self.ua) + len(self.ue) - 4, 'main export not last'
        self.base = self.main['SerialOffset'] - len(self.ua)

    def name(self, p):
        i, n = struct.unpack_from('<ii', self.ue, p)
        return self.nm[i] + (f'_{n - 1}' if n else '')

    def outer(self):
        """-> (size_field_pos, count_pos, {char: (entry_start, objects_tag_pos)})"""
        b = self.ue; p = self.base
        assert self.name(p) == 'AnimationDatasEx' and self.name(p + 8) == 'MapProperty'
        size_pos = p + 16; p += 24
        p += 16 + 1                      # key type, value type, guid flag
        cnt_pos = p + 4; cnt = struct.unpack_from('<i', b, cnt_pos)[0]; p += 8
        chars = {}
        for _ in range(cnt):
            ch = self.name(p).split('CHAR_ID_')[-1]; p += 8
            obj = p
            assert self.name(p) == 'Objects' and self.name(p + 8) == 'MapProperty'
            size = struct.unpack_from('<i', b, p + 16)[0]
            p += 24 + 17 + size
            assert self.name(p) == 'None'; p += 8
            chars[ch] = obj
        return size_pos, cnt_pos, chars

    def entries(self, obj):
        """entries of one Objects map -> list of dicts with raw bytes and parsed key."""
        b = self.ue; p = obj + 24 + 17
        cnt = struct.unpack_from('<i', b, p + 4)[0]; p += 8; out = []
        for _ in range(cnt):
            s = p; key = {}
            while True:
                n = self.name(p); p += 8
                if n == 'None': break
                assert self.name(p) == 'EnumProperty'; p += 8
                sz = struct.unpack_from('<i', b, p)[0]; p += 8 + 8 + 1
                key[n] = (self.name(p).split('::')[1], p); p += sz
            val_pos = p; p += 8; l = struct.unpack_from('<i', b, p)[0]; p += 4 + l
            out.append({'start': s, 'end': p, 'key': key, 'val_pos': val_pos,
                        'k': (key['AnimationType'][0], key['NeweraFlipbookOverrideType'][0], key['WeaponRank'][0])})
        return out

    def ref(self, s):
        assert s in self.idx, f'name not in package: {s}'
        return struct.pack('<ii', self.idx[s], 0)

    def _ensure_names(self, edits):
        need = []
        for e in edits:
            if 'copy_override' in e and e.get('rename_paths'):
                _, _, chars = self.outer()
                for x in self.entries(chars[e['char']]):
                    if x['k'][1] == e['copy_override']:
                        v = self.name(x['val_pos'])
                        need += [v.replace(f"_{e['copy_override']}_", f'_{t}_') for t in e['to']]
        need = [n for n in dict.fromkeys(need) if n not in self.idx]
        if need:
            ua, ue, _ = U.add_names(self.ua, bytes(self.ue), need)
            self.__init__(ua, ue)
            print(f'  FlipbookStatic: +{len(need)} names')

    def apply(self, edits):
        self._ensure_names(edits)
        for e in edits:
            _, _, chars = self.outer()
            obj = chars[e['char']]; ents = self.entries(obj); by = {x['k']: x for x in ents}
            if 'remap' in e:
                for x in ents:
                    a, o, r = x['k']
                    if a == e['anim'] and o in e['remap']:
                        src = by[(a, e['remap'][o], r)]
                        self.ue[x['val_pos']:x['val_pos'] + 8] = self.ue[src['val_pos']:src['val_pos'] + 8]
                        print(f"  FlipbookStatic {e['char']}: {a}/{o}/{r} -> data of {e['remap'][o]}")
            if 'copy_override' in e:
                new = bytearray(); added = 0
                for to in e['to']:
                    enum = self.ref('ENeweraFlipbookOverrideType::' + to)
                    for x in ents:
                        a, o, r = x['k']
                        if o != e['copy_override']: continue
                        if (a, to, r) in by:                      # already there: repoint
                            t = by[(a, to, r)]
                            self.ue[t['val_pos']:t['val_pos'] + 8] = self.ue[x['val_pos']:x['val_pos'] + 8]
                            continue
                        raw = bytearray(self.ue[x['start']:x['end']])
                        k = x['key']['NeweraFlipbookOverrideType'][1] - x['start']
                        raw[k:k + 8] = enum
                        if e.get('rename_paths'):                  # point at the cloned asset (sprite_clone.py)
                            v = self.name(x['val_pos']).replace(f"_{e['copy_override']}_", f'_{to}_')
                            vp = x['val_pos'] - x['start']; raw[vp:vp + 8] = self.ref(v)
                        new += raw; added += 1
                self._insert(obj, ents[-1]['end'], bytes(new), added)
                print(f"  FlipbookStatic {e['char']}: +{added} entries ({', '.join(e['to'])} = {e['copy_override']})")
        return self

    def _insert(self, obj, at, data, n):
        d = len(data)
        if not d: return
        size_pos, _, _ = self.outer()
        self.ue[at:at] = data
        for pos in (obj + 16, size_pos):                          # Objects size, AnimationDatasEx size
            struct.pack_into('<i', self.ue, pos, struct.unpack_from('<i', self.ue, pos)[0] + d)
        cp = obj + 24 + 17 + 4
        struct.pack_into('<i', self.ue, cp, struct.unpack_from('<i', self.ue, cp)[0] + n)
        ua = bytearray(self.ua)
        struct.pack_into('<q', ua, self.main['pos'] + 28, self.main['SerialSize'] + d)
        _, p, _ = self.f['BulkDataStartOffset']; struct.pack_into('<q', ua, p, self.f['BulkDataStartOffset'][0] + d)
        self.ua = bytes(ua); self.f = U.read_summary(self.ua)
        self.main = max(U.read_exports(self.ua, self.f), key=lambda e: e['SerialOffset'])
        assert self.main['SerialOffset'] + self.main['SerialSize'] == len(self.ua) + len(self.ue) - 4

    def summary(self, ch):
        _, _, chars = self.outer(); ents = self.entries(chars[ch])
        from collections import Counter
        return Counter(x['k'][1] for x in ents), {x['k']: self.name(x['val_pos']).rsplit('/', 1)[-1] for x in ents if 'UIC' in x['k'][0]}


def load_vanilla():
    import tspak
    pak = tspak.Pak(paths.game_pak())
    return pak.read(ASSET + '.uasset'), pak.read(ASSET + '.uexp')


def apply_to_stage(edits, stage):
    fs = FS(*load_vanilla()).apply(edits)
    # verify: re-parse everything from scratch
    fs2 = FS(fs.ua, fs.ue); _, _, chars = fs2.outer()
    for ch, obj in chars.items(): fs2.entries(obj)
    out = os.path.join(stage, *ASSET.split('/'))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out + '.uasset', 'wb').write(fs.ua); open(out + '.uexp', 'wb').write(bytes(fs.ue))
    return fs2


if __name__ == '__main__':
    if sys.argv[1] == 'show':
        c, uic = FS(*load_vanilla()).summary(sys.argv[2])
        print(dict(c))
        for k, v in sorted(uic.items()): print('  ', k, '->', v)
