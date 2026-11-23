"""Dump every top-level DataTable to data/tables/<name>.json and print a schema summary.

  python tools/dump_tables.py [filter]
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dtparse, tspak

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME_PAK = paths.game_pak()
PREFIX = 'TRIANGLE_STRATEGY/Content/Newera/Data/DataTables/'

flt = sys.argv[1] if len(sys.argv) > 1 else ''
pak = tspak.Pak(GAME_PAK)
lst = [l.strip() for l in open(os.path.join(ROOT, 'pak_filelist.txt'), encoding='utf-8')]
tables = sorted({l[len(PREFIX):-7] for l in lst if l.startswith(PREFIX) and l.endswith('.uasset') and '/' not in l[len(PREFIX):]})
out = os.path.join(ROOT, 'data', 'tables'); os.makedirs(out, exist_ok=True)
summary = {}
for t in tables:
    if flt not in t: continue
    try:
        ua = pak.read(PREFIX + t + '.uasset'); ue = pak.read(PREFIX + t + '.uexp')
        names, rows = dtparse.parse_bytes(ua, ue)
    except Exception as e:
        print(f'{t}: FAILED {e}'); continue
    clean = {k: {f: p['v'] for f, p in v.items()} for k, v in rows.items()}
    json.dump(clean, open(os.path.join(out, t + '.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=str)
    first = next(iter(rows.values()), {})
    schema = {f: p['t'].replace('Property', '') for f, p in first.items()}
    summary[t] = {'rows': len(rows), 'fields': schema}
    print(f'{t}: {len(rows)} rows, {len(schema)} fields: ' + ', '.join(f'{f}:{ty}' for f, ty in schema.items())[:600])
json.dump(summary, open(os.path.join(out, '_schema.json'), 'w', encoding='utf-8'), indent=1)
