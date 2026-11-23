"""Compare every DataTable staged in a mod build against vanilla.

  python tools/verify_stage.py <mod_dir>

Checks per table: header/bulk/serial sizes consistent, FName hashes valid, every vanilla row still present,
lists rows that changed and rows that were added (with their SelfId)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dtparse, tspak, uasset_edit as U

GAME_PAK = paths.game_pak()
mod = sys.argv[1]
stage = os.path.join(mod, 'stage') if os.path.isdir(os.path.join(mod, 'stage')) else os.path.join(mod, 'build', 'stage')
pak = tspak.Pak(GAME_PAK)
ok_all = True
for root, _, files in os.walk(stage):
    for fn in files:
        if not fn.endswith('.uasset'): continue
        p = os.path.join(root, fn)
        rel = os.path.relpath(p, stage).replace('\\', '/')[:-7]
        # DataTables only; sprite/blueprint assets (sprite_clones, bp_sprite, flipbook_static) self-verify when built
        if '/Data/DataTables/' not in rel: continue
        ua = open(p, 'rb').read(); ue = open(p[:-7] + '.uexp', 'rb').read()
        vua = pak.read(rel + '.uasset'); vue = pak.read(rel + '.uexp')
        f = U.read_summary(ua)
        _, bad = U.check_hashes(ua); _, vbad = U.check_hashes(vua)
        _, rows = dtparse.parse_bytes(ua, ue); _, vrows = dtparse.parse_bytes(vua, vue)
        val = lambda r: {a: b['v'] for a, b in r.items()}
        missing = [k for k in vrows if k not in rows]
        changed = [k for k in vrows if k in rows and val(vrows[k]) != val(rows[k])]
        added = [k for k in rows if k not in vrows]
        sizes = (f['TotalHeaderSize'][0] == len(ua), f['BulkDataStartOffset'][0] == len(ua) + len(ue) - 4,
                 U.read_exports(ua, f)[0]['SerialSize'] == len(ue) - 4)
        # names the engine would split at runtime ('X_45') must never be stored whole in a name map
        names_now = [s for s, _ in U.read_names(ua, f)[0]]
        vnames = set(s for s, _ in U.read_names(vua, U.read_summary(vua))[0])
        unsplit = [n for n in names_now if n not in vnames and U.split_fname(n)[1] != 0]
        dupes = len(names_now) - len(set(names_now))
        good = all(sizes) and not missing and set(bad) <= set(vbad) and not unsplit and not dupes
        if unsplit or dupes: print(f'    !! {rel.split("/")[-1]}: unsplit numbered names {unsplit[:5]} dupes={dupes}')
        ok_all &= good
        print(f"{'OK ' if good else 'BAD'} {rel.split('/')[-1]}: rows {len(vrows)}->{len(rows)} changed={changed} added={[(k, rows[k].get('SelfId', {}).get('v')) for k in added]} sizes={sizes} newbadhash={sorted(set(bad) - set(vbad))}")
print('ALL OK' if ok_all else 'PROBLEMS FOUND')
