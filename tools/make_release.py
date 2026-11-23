"""Assemble the player download: release/TSMod_v1/ and release/TSMod_v1.zip.

  python tools/make_release.py --pak mods/_combined/release_v1/TSMod_P.pak
  python tools/make_release.py --editor-only        (refresh only SaveEditor/, keep the pak that is there)

Contents:
  TSMod_P.pak                    the release pak (copied from --pak)
  README.txt                     release/TSMod_v1/README.txt (kept as is; edit it there)
  SaveEditor/                    the save editor, self-contained:
    TSMod Save Editor.bat        Windows launcher (calls tools/saveeditor/TSModSaveEditor.bat)
    TSMod Save Editor.sh         Linux / Steam Deck launcher
    tools/saveeditor/...         the editor (no cache, backups, __pycache__ or dev generators)
    tools/<module>.py            the tools modules it imports (found by following its imports)
Writes only under release/.
"""
import argparse, hashlib, os, re, shutil, sys, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, 'tools')
OUT = os.path.join(ROOT, 'release', 'TSMod_v1')
SKIP_DIRS = {'__pycache__', 'editor_data', 'cache', 'backups'}
SKIP_FILES = {'make_story_data.py', 'make_forward_data.py'}        # dev generators (need the decompiled scripts)


def editor_deps():
    """tools/*.py modules the editor imports, transitively."""
    local = {os.path.splitext(f)[0] for f in os.listdir(TOOLS) if f.endswith('.py')}
    se = os.path.join(TOOLS, 'saveeditor')
    todo = [os.path.join(se, f) for f in os.listdir(se) if f.endswith(('.py', '.pyw')) and f not in SKIP_FILES]
    seen, need = set(), set()
    while todo:
        f = todo.pop()
        if f in seen: continue
        seen.add(f)
        src = open(f, encoding='utf-8', errors='replace').read()
        mods = set()
        for n in re.findall(r'^\s*import ([\w, ]+)', src, re.M):
            mods |= {x.strip().split(' as ')[0] for x in n.split(',')}
        mods |= set(re.findall(r'^\s*from ([\w.]+) import', src, re.M))
        for m in mods:
            b = m.split('.')[0]
            if b in local and b not in need:
                need.add(b); todo.append(os.path.join(TOOLS, b + '.py'))
    return sorted(need)


BAT = '@echo off\r\nrem Starts the TSMod Save Editor (tools\\saveeditor\\TSModSaveEditor.bat).\r\n' \
      'call "%~dp0tools\\saveeditor\\TSModSaveEditor.bat" %*\r\n'
SH = '#!/bin/sh\n# Starts the TSMod Save Editor (tools/saveeditor/TSModSaveEditor.sh).\n' \
     'exec sh "$(cd "$(dirname "$0")" && pwd)/tools/saveeditor/TSModSaveEditor.sh" "$@"\n'


def build_editor(dst):
    if os.path.isdir(dst): shutil.rmtree(dst)
    se_src, se_dst = os.path.join(TOOLS, 'saveeditor'), os.path.join(dst, 'tools', 'saveeditor')
    for base, dirs, files in os.walk(se_src):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        rel = os.path.relpath(base, se_src)
        for f in files:
            if f in SKIP_FILES or f.endswith('.pyc'): continue
            os.makedirs(os.path.join(se_dst, rel), exist_ok=True)
            shutil.copy2(os.path.join(base, f), os.path.join(se_dst, rel, f))
    deps = editor_deps()
    for m in deps:
        shutil.copy2(os.path.join(TOOLS, m + '.py'), os.path.join(dst, 'tools', m + '.py'))
    open(os.path.join(dst, 'TSMod Save Editor.bat'), 'w', newline='').write(BAT)
    open(os.path.join(dst, 'TSMod Save Editor.sh'), 'w', newline='\n').write(SH)
    return deps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pak'); ap.add_argument('--editor-only', action='store_true')
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    if not a.editor_only:
        if not a.pak or not os.path.isfile(a.pak): sys.exit('--pak <built TSMod_P.pak> is required')
        shutil.copy2(a.pak, os.path.join(OUT, 'TSMod_P.pak'))
    deps = build_editor(os.path.join(OUT, 'SaveEditor'))
    if not os.path.isfile(os.path.join(OUT, 'README.txt')): sys.exit('release/TSMod_v1/README.txt is missing')
    zpath = OUT + '.zip'
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
        for base, dirs, files in os.walk(OUT):
            for f in files:
                p = os.path.join(base, f)
                z.write(p, os.path.join('TSMod_v1', os.path.relpath(p, OUT)))
    pak = os.path.join(OUT, 'TSMod_P.pak')
    h = hashlib.sha256(open(pak, 'rb').read()).hexdigest().upper() if os.path.isfile(pak) else 'none'
    print(f'editor deps: {", ".join(deps)}')
    print(f'{zpath}: {os.path.getsize(zpath):,} bytes; pak SHA-256 {h}')


if __name__ == '__main__':
    main()
