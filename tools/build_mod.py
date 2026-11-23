"""Build a Triangle Strategy Lua mod into a patch pak.

  python tools/build_mod.py <mod_dir> [<mod_dir> ...] [--name NAME] [--out DIR]

<mod_dir>/mod.json:
  {"name": "...",
   "lua":        {"src/file.lua": "Newera_Handling/Scenario/.../file"},   full replacement
   "lua_append": {"src/snip.lua": "Newera_Handling/Scenario/.../file"},   appended to base
   "dt_edits":   [...],
   "flipbook_static": [...], "sprite_clones": [...], "bp_sprite": [...],   sprite edits, see tools/*.py
   "unit_actor": [{"unit": NEW_ID, "like": EXISTING_ID}],                  unit -> actor blueprint, see tools/unit_actor.py
   "raw_files": {"src/file.umap": "Newera/Map/Story/x/file.umap"}}         whole asset files, copied under Content/
  (lua target = path under Content/LuaScriptBin/Src, without extension)
  Several mods combine into one pak (see collect()).

Steps: luac5.1 compile -> XOR-encrypt with the ORIGINAL file's key offset -> stage under
TRIANGLE_STRATEGY/Content/LuaScriptBin/Src/... -> repak pack (V11, mount ../../../)
Output: <mod_dir>/build/<name>_P.pak
"""
import json, os, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import lubcrypt

LUAC = os.path.join(ROOT, 'tools', 'lua51', 'luac5.1.exe')
REPAK = os.path.join(ROOT, 'tools', 'repak', 'repak.exe')
ORIG = os.path.join(ROOT, 'extracted_lub', 'TRIANGLE_STRATEGY', 'Content', 'LuaScriptBin', 'Src')


GAME_PAK = paths.game_pak()


def fname_ref(names, value, table):
    """FName -> (name-map index, number). UE stores 'FOO_1' as base 'FOO' with number 2 (see
    uasset_edit.split_fname); the engine splits strings the same way at runtime, so always use the split form."""
    import uasset_edit
    base, num = uasset_edit.split_fname(value)
    if base in names: return names.index(base), num
    raise SystemExit(f"{value} not in {table} name map")


def apply_dt_edits(edits, stage):
    """Same-size in-place DataTable edits.
    edit = {"table": "Newera/Data/DataTables/GOP_X", "row": ..., "field": ..., "value": ...}
    Supports Name/Enum (value must already be in the table's name map), Int, Float.
    Original asset is read straight from the game pak, so edits always start from vanilla."""
    import struct
    import dtparse, tspak
    if not edits: return
    pak = tspak.Pak(GAME_PAK)
    by_table = {}
    for e in edits: by_table.setdefault(e['table'], []).append(e)
    import uasset_edit
    for table, tedits in by_table.items():
        base = os.path.join(stage, 'TRIANGLE_STRATEGY', 'Content', *table.split('/'))
        os.makedirs(os.path.dirname(base), exist_ok=True)
        ua = pak.read('TRIANGLE_STRATEGY/Content/' + table + '.uasset')
        ue = pak.read('TRIANGLE_STRATEGY/Content/' + table + '.uexp')
        # structural pass: new rows ({"add_row": NEW, "copy_from": SRC}), then names that Name
        # edits need but the table doesn't have yet (name-map growth)
        vanilla_rows = len(dtparse.parse_bytes(ua, ue)[1])
        added = []
        for e in tedits:
            if 'add_row' in e:
                ua, ue = uasset_edit.add_row(ua, ue, e['copy_from'], e['add_row'])
                added.append(e['add_row'])
                print(f"  {table.split('/')[-1]}: + row {e['add_row']} (copy of {e['copy_from']})")
            elif 'add_rows' in e:      # bulk: [{"row": NEW, "copy_from": SRC, "set": {field: value}}]
                specs = [(r['copy_from'], r['row'], r.get('set', {})) for r in e['add_rows']]
                ua, ue = uasset_edit.add_rows(ua, ue, specs)
                added += [r['row'] for r in e['add_rows']]
                print(f"  {table.split('/')[-1]}: + {len(specs)} rows (bulk)")
        names0 = dtparse.parse_bytes(ua, ue)[0]
        _, rows0 = dtparse.parse_bytes(ua, ue)
        need = []
        for e in tedits:
            if 'field' not in e: continue
            prop = rows0[e['row']][e['field']]
            if prop['t'] == 'NameProperty' and isinstance(e['value'], str):
                try: fname_ref(names0, e['value'], table)
                except SystemExit: need.append(e['value'])
        if need:
            ua, ue, _ = uasset_edit.add_names(ua, ue, need)
            print(f"  {table.split('/')[-1]}: + names {need}")
        # string fields (size-changing) are applied structurally too
        _, rows0 = dtparse.parse_bytes(ua, ue)
        str_edits = [e for e in tedits if 'field' in e and rows0[e['row']][e['field']]['t'] == 'StrProperty']
        for e in str_edits:
            old = rows0[e['row']][e['field']]['v']
            ua, ue = uasset_edit.set_str(ua, ue, e['row'], e['field'], e['value'])
            print(f"  {table.split('/')[-1]}[{e['row']}].{e['field']}: {old!r} -> {e['value']!r}")
        open(base + '.uasset', 'wb').write(ua); open(base + '.uexp', 'wb').write(ue)
        tedits = [e for e in tedits if 'add_row' not in e and 'add_rows' not in e and e not in str_edits]
        names, rows = dtparse.parse(base + '.uasset')
        uexp = bytearray(open(base + '.uexp', 'rb').read())
        # expand {"row": dst, "copy_from": src, "except": [...]} into per-field edits
        SIMPLE = ('NameProperty', 'EnumProperty', 'BoolProperty', 'IntProperty', 'FloatProperty')
        expanded = []
        for e in tedits:
            if 'copy_from' not in e: expanded.append(e); continue
            src, dst = rows[e['copy_from']], rows[e['row']]
            skip = set(e.get('except', [])) | {'SelfId'}
            for f, p in src.items():
                if f in skip or f not in dst or dst[f]['t'] != p['t'] or p['t'] not in SIMPLE: continue
                if dst[f]['v'] != p['v']:
                    expanded.append({'table': table, 'row': e['row'], 'field': f, 'value': p['v']})
            missing = [f for f in src if f not in skip and (f not in dst or src[f]['t'] not in SIMPLE)]
            if missing: print(f"  NOTE copy {e['copy_from']}->{e['row']}: not copied {missing}")
        tedits = expanded
        for e in tedits:
            prop = rows[e['row']][e['field']]
            t, off, old = prop['t'], prop['off'], prop['v']
            if t in ('NameProperty', 'EnumProperty') or (t == 'ByteProperty' and prop['size'] == 8):
                struct.pack_into('<ii', uexp, off, *fname_ref(names, e['value'], table))
            elif t == 'BoolProperty':
                if not isinstance(e['value'], bool): raise SystemExit('bool edit needs true/false')
                uexp[off] = 1 if e['value'] else 0
            elif t == 'IntProperty': struct.pack_into('<i', uexp, off, int(e['value']))
            elif t == 'FloatProperty': struct.pack_into('<f', uexp, off, float(e['value']))
            else: raise SystemExit(f'unsupported property type {t}')
            print(f"  {table.split('/')[-1]}[{e['row']}].{e['field']}: {old} -> {e['value']}")
        open(base + '.uexp', 'wb').write(uexp)
        # re-parse to confirm the table is still well-formed and the edit landed
        _, rows2 = dtparse.parse(base + '.uasset')
        final = {(e['row'], e['field']): e for e in tedits}   # last edit wins
        for e in final.values():
            got = rows2[e['row']][e['field']]['v']
            assert (abs(got - float(e['value'])) < 1e-6 if isinstance(got, float) else got == e['value']) if not isinstance(got, str) else got == str(e['value']), (e, got)
        assert len(rows2) == len(rows) == vanilla_rows + len(added)


DECOMPILED = os.path.join(ROOT, 'decompiled')


def collect(mod_dirs):
    """Merge several mods. Per Lua target: at most one mod may supply a full replacement
    ("lua"); any number may add "lua_append" snippets (appended in mod order, so they can
    redefine functions). Base = replacement or the vanilla decompiled source."""
    global UNIT_ACTOR, RAW_FILES
    full, appends, dt, fbs, clones, bps = {}, {}, [], [], [], []
    UNIT_ACTOR = []; RAW_FILES = []
    for d in mod_dirs:
        cfg = json.load(open(os.path.join(d, 'mod.json')))
        for src, target in cfg.get('lua', {}).items():
            if target in full:
                raise SystemExit(f'conflict: {target} fully replaced by both {full[target]} and {d}')
            full[target] = os.path.join(d, src)
        for src, target in cfg.get('lua_append', {}).items():
            appends.setdefault(target, []).append(os.path.join(d, src))
        dt += cfg.get('dt_edits', [])
        fbs += cfg.get('flipbook_static', [])
        clones += cfg.get('sprite_clones', [])
        bps += cfg.get('bp_sprite', [])
        UNIT_ACTOR.extend(cfg.get('unit_actor', []))
        RAW_FILES.extend((os.path.join(d, src), tgt) for src, tgt in cfg.get('raw_files', {}).items())
    return full, appends, dt, fbs, clones, bps


def build_lua(target, base_path, append_paths, build, stage):
    src = open(base_path, encoding='utf-8').read()
    for a in append_paths:
        src += f'\n-- ===== appended from {os.path.relpath(a, ROOT)} =====\n' + open(a, encoding='utf-8').read() + '\n'
    merged = os.path.join(build, 'src', target + '.lua')
    os.makedirs(os.path.dirname(merged), exist_ok=True)
    open(merged, 'w', encoding='utf-8').write(src)
    luac_out = merged + 'c'
    subprocess.run([LUAC, '-o', luac_out, merged], check=True)
    orig = open(os.path.join(ORIG, target + '.lub'), 'rb').read()
    off = lubcrypt.find_offset(orig)
    data = lubcrypt.xor(open(luac_out, 'rb').read(), off)
    assert lubcrypt.xor(data[:12], off) == lubcrypt.HDR
    dst = os.path.join(stage, 'TRIANGLE_STRATEGY', 'Content', 'LuaScriptBin', 'Src', target + '.lub')
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    open(dst, 'wb').write(data)
    how = ('replaced' if base_path.startswith(os.path.join(ROOT, 'mods')) else 'vanilla') + (f' +{len(append_paths)} append' if append_paths else '')
    print(f'  {target}.lub  [{how}]  offset={off}  {len(orig)} -> {len(data)} bytes')


def main(mod_dirs, name=None, out_dir=None):
    mod_dirs = [os.path.abspath(d) for d in mod_dirs]
    if name is None:
        name = json.load(open(os.path.join(mod_dirs[0], 'mod.json')))['name']
    build = out_dir or os.path.join(mod_dirs[0], 'build')
    stage = os.path.join(build, 'stage')
    shutil.rmtree(build, ignore_errors=True); os.makedirs(stage)
    full, appends, dt, fbs, clones, bps = collect(mod_dirs)
    for target in sorted(set(full) | set(appends)):
        base = full.get(target) or os.path.join(DECOMPILED, *target.split('/')) + '.lua'
        build_lua(target, base, appends.get(target, []), build, stage)
    apply_dt_edits(dt, stage)
    if clones:                                # renamed sprite asset copies (tools/sprite_clone.py)
        import sprite_clone
        sprite_clone.apply_to_stage(clones, stage)
    if bps:                                   # character blueprint sprite variants (tools/bp_sprite.py)
        import bp_sprite
        bp_sprite.apply_to_stage(bps, stage)
    if fbs:                                   # sprite lookup table edits (tools/flipbook_static.py)
        import flipbook_static
        flipbook_static.apply_to_stage(fbs, stage)
    if UNIT_ACTOR:                            # unit -> actor blueprint entries (tools/unit_actor.py)
        import unit_actor
        unit_actor.apply_to_stage(UNIT_ACTOR, stage)
    for src, tgt in RAW_FILES:                # whole asset files (e.g. a cloned map), copied under Content/
        dst = os.path.join(stage, 'TRIANGLE_STRATEGY', 'Content', *tgt.split('/'))
        if os.path.exists(dst): raise SystemExit(f'raw_files conflict: {tgt}')
        os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copyfile(src, dst)
        print(f'  raw file {tgt} ({os.path.getsize(dst)} bytes)')
    pak_dir = os.path.join(build, name + '_P')
    os.rename(stage, pak_dir)
    pak = os.path.join(build, name + '_P.pak')
    subprocess.run([REPAK, 'pack', '--version', 'V11', '--mount-point', '../../../', pak_dir, pak], check=True)
    os.rename(pak_dir, stage)
    print('built', pak, os.path.getsize(pak), 'bytes')


if __name__ == '__main__':
    # build_mod.py <mod_dir> [<mod_dir> ...] [--name NAME] [--out DIR]
    args = sys.argv[1:]; name = out = None
    if '--name' in args: i = args.index('--name'); name = args[i + 1]; del args[i:i + 2]
    if '--out' in args: i = args.index('--out'); out = os.path.abspath(args[i + 1]); del args[i:i + 2]
    main(args, name, out)
