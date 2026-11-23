"""Edit the UnitActor data asset (Content/Newera/Data/DataAsset/UnitActor): unit id -> actor blueprint.

The asset is one tagged MapProperty `UnitActorClasses` <NameProperty, SoftObjectProperty>; each entry is
20 bytes: key FName (i32 index, i32 number), value FSoftObjectPath (asset FName 8 bytes + empty sub-path FString 4).

mod.json:  "unit_actor": [{"unit": "UNIT_MASTER_NEW_ID", "like": "UNIT_MASTER_EXISTING_ID"}]
  adds an entry for `unit` that uses the same actor blueprint as the existing entry `like`.

  python tools/unit_actor.py show [filter]     list entries (unit -> blueprint)
"""
import os, sys, struct, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import uasset_edit as U
import tspak

GAME_PAK = paths.game_pak()
PATH = 'TRIANGLE_STRATEGY/Content/Newera/Data/DataAsset/UnitActor'
ENTRY = 20


def parse(ua, ue):
    f = U.read_summary(ua)
    names = [n for n, _ in U.read_names(ua, f)[0]]
    nm = lambda i: names[i]
    assert nm(struct.unpack_from('<i', ue, 0)[0]) == 'UnitActorClasses' and nm(struct.unpack_from('<i', ue, 8)[0]) == 'MapProperty'
    size = struct.unpack_from('<i', ue, 16)[0]
    assert nm(struct.unpack_from('<i', ue, 24)[0]) == 'NameProperty' and nm(struct.unpack_from('<i', ue, 32)[0]) == 'SoftObjectProperty'
    data = 24 + 16 + 1                       # tag header, key/value types, HasPropertyGuid byte
    rem, num = struct.unpack_from('<ii', ue, data)
    assert rem == 0 and size == 8 + num * ENTRY, (rem, num, size)
    ents = []
    for i in range(num):
        p = data + 8 + i * ENTRY
        k, kn, v, vn, sub = struct.unpack_from('<iiiii', ue, p)
        assert vn == 0 and sub == 0, ('unexpected numbered value or sub-path', p)
        key = nm(k) if kn == 0 else f'{nm(k)}_{kn - 1}'     # FName number n stores suffix _(n-1)
        ents.append((key, nm(v), p))
    return f, names, data, num, size, ents


def add_entries(ua, ue, edits):
    f, names, data, num, size, ents = parse(ua, ue)
    have = {k: (v, p) for k, v, p in ents}
    new = [e for e in edits if e['unit'] not in have]
    for e in edits:
        assert e['like'] in have, f"unit_actor: {e['like']} has no UnitActor entry"
    if not new:
        return ua, ue
    for e in new:
        assert U.split_fname(e['unit'])[1] == 0, f"unit_actor: {e['unit']} ends in _<n>; numbered FNames not supported here"
    ua, ue, idx = U.add_names(ua, bytes(ue), [e['unit'] for e in new])
    names = [n for n, _ in U.read_names(ua, U.read_summary(ua))[0]]
    blob = b''
    for e in new:
        vname = have[e['like']][0]
        blob += struct.pack('<iiiii', names.index(e['unit']), 0, names.index(vname), 0, 0)
    end = data + 8 + num * ENTRY
    ue2 = bytearray(ue[:end]) + blob + ue[end:]
    d = len(blob)
    struct.pack_into('<i', ue2, 16, size + d)                 # tag size
    struct.pack_into('<i', ue2, data + 4, num + len(new))     # map count
    ua2 = bytearray(ua)
    f2 = U.read_summary(bytes(ua2)); ex = U.read_exports(bytes(ua2), f2)
    struct.pack_into('<q', ua2, ex[0]['pos'] + 28, ex[0]['SerialSize'] + d)
    _, p, _ = f2['BulkDataStartOffset']; struct.pack_into('<q', ua2, p, f2['BulkDataStartOffset'][0] + d)
    ua2, ue2 = bytes(ua2), bytes(ue2)
    # verify
    f3 = U.read_summary(ua2)
    assert f3['BulkDataStartOffset'][0] == len(ua2) + len(ue2) - 4
    assert U.read_exports(ua2, f3)[0]['SerialSize'] == len(ue2) - 4
    assert not U.check_hashes(ua2)[1]
    _, _, _, num3, _, ents3 = parse(ua2, ue2)
    got = {k: v for k, v, _ in ents3}
    assert num3 == num + len(new) and all(got[e['unit']] == have[e['like']][0] for e in new)
    assert all(got[k] == v for k, v, _ in ents)
    return ua2, ue2


def apply_to_stage(edits, stage, pak=None):
    pak = pak or tspak.Pak(GAME_PAK)
    ua, ue = add_entries(pak.read(PATH + '.uasset'), pak.read(PATH + '.uexp'), edits)
    out = os.path.join(stage, *PATH.split('/'))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out + '.uasset', 'wb').write(ua); open(out + '.uexp', 'wb').write(ue)
    for e in edits:
        print(f"  unit_actor: {e['unit']} -> same actor as {e['like']}")


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'show':
        pak = tspak.Pak(GAME_PAK)
        _, _, _, num, _, ents = parse(pak.read(PATH + '.uasset'), pak.read(PATH + '.uexp'))
        flt = sys.argv[2] if len(sys.argv) > 2 else ''
        for k, v, _ in ents:
            if re.search(flt, k + v, re.I): print(f'  {k:45} {v}')
        print(num, 'entries')
