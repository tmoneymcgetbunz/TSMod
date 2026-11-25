"""Export crash logs (user design, 2026-11-23): pick crashes from the game's Crashes folder, write one zip the player
sends by hand. Nothing is sent anywhere.

The zip holds, per picked crash, CrashContext.runtime-xml (machine, login and account ids blanked; the Windows user
name in paths replaced) and, if ticked, UE4Minidump.dmp (as is: it is a memory snapshot, so it can't be cleaned);
the TSMod release log (TSMod_log.txt and TSMod_log.old.txt, from the game's working folder, cleaned the same way);
and info.txt (TSMod pak hash, editor version, game build, crash list).

Crashes live in <Documents>/My Games/TRIANGLE_STRATEGY/Steam/Crashes/<UE4CC-...>/ (the save folder's parent's sibling),
on Linux / Steam Deck inside the game's Proton prefix. Read-only on everything except the zip it writes.
"""
import datetime, getpass, glob, hashlib, os, re, zipfile

EDITOR_VERSION = '1.0.1 (2026-11-25)'
CONTEXT = 'CrashContext.runtime-xml'
DUMP = 'UE4Minidump.dmp'
LOG_NAMES = ('TSMod_log.txt', 'TSMod_log.old.txt')
BLANK_TAGS = ('MachineId', 'LoginId', 'EpicAccountId', 'ExecutionGuid', 'UserName', 'ComputerName')


def _paths():
    import paths                               # tools/paths.py (the editor puts tools/ on sys.path)
    return paths


def crash_roots():
    """Every Crashes folder next to a save root (one per Steam / Proton location)."""
    try:
        roots = _paths().save_roots()
    except Exception:
        roots = [os.path.join(os.path.expanduser('~'), 'Documents', 'My Games', 'TRIANGLE_STRATEGY', 'Steam')]
    out = []
    for r in roots:
        c = os.path.join(r, 'Crashes')
        if os.path.isdir(c) and c not in out: out.append(c)
    return out


def _tag(text, name):
    m = re.search(r'<%s>([^<]*)</%s>' % (name, name), text)
    return m.group(1).strip() if m else ''


def list_crashes(roots=None):
    """[{'dir', 'time' (datetime), 'error', 'frame', 'has_dump', 'dump_size'}], newest first."""
    out = []
    for root in (crash_roots() if roots is None else roots):
        for d in glob.glob(os.path.join(root, '*')):
            ctx = os.path.join(d, CONTEXT)
            if not os.path.isfile(ctx): continue
            try:
                txt = open(ctx, encoding='utf-8', errors='replace').read()
            except OSError:
                continue
            stack = _tag(txt, 'CallStack')
            frame = next((l.strip() for l in stack.splitlines() if l.strip()), '')
            dump = os.path.join(d, DUMP)
            out.append({'dir': d, 'time': datetime.datetime.fromtimestamp(os.path.getmtime(ctx)),
                        'error': _tag(txt, 'ErrorMessage')[:200], 'frame': frame[:160],
                        'has_dump': os.path.isfile(dump), 'dump_size': os.path.getsize(dump) if os.path.isfile(dump) else 0})
    return sorted(out, key=lambda c: c['time'], reverse=True)


def clean(text, user=None):
    """Blank identifying values: the id tags, the Windows / Linux user name in paths, Steam ids."""
    for t in BLANK_TAGS:
        text = re.sub(r'(<%s>)[^<]*(</%s>)' % (t, t), r'\1(removed)\2', text)
    text = re.sub(r'(?i)([A-Z]:[\\/]+(?:Users|Documents and Settings)[\\/]+)[^\\/<>"\r\n]+', r'\1<user>', text)
    text = re.sub(r'(/home/)[^/<>"\r\n]+', r'\1<user>', text)
    text = re.sub(r'\b7656119\d{10}\b', '<steamid>', text)
    if user is None:
        try:
            user = getpass.getuser()
        except Exception:
            user = ''
    if user and len(user) >= 3 and user.lower() not in ('steamuser', 'user', 'deck'):
        text = re.sub(re.escape(user), '<user>', text, flags=re.I)
    return text


def game_dirs(paks_dir):
    """Folders the game may use as its working folder: Binaries/Win64 first [inferred], then the game folders."""
    if not paks_dir: return []
    game = os.path.dirname(os.path.dirname(os.path.abspath(paks_dir)))          # .../TRIANGLE_STRATEGY
    return [os.path.join(game, 'Binaries', 'Win64'), game, os.path.dirname(game)]


def find_logs(paks_dir):
    out = []
    for d in game_dirs(paks_dir):
        for n in LOG_NAMES:
            p = os.path.join(d, n)
            if os.path.isfile(p) and p not in out: out.append(p)
    return out


def game_build():
    """The Steam build id from the game's appmanifest, or ''."""
    try:
        P = _paths()
        for lib in P.library_dirs():
            for aid in P.app_ids():
                acf = os.path.join(lib, 'steamapps', f'appmanifest_{aid}.acf')
                if os.path.isfile(acf):
                    m = re.search(r'"buildid"\s+"(\d+)"', open(acf, encoding='utf-8', errors='replace').read())
                    if m: return m.group(1)
    except Exception:
        pass
    return ''


def pak_info(paks_dir):
    """[(name, size, sha256)] for every TSMod pak in the Paks folder."""
    out = []
    for p in sorted(glob.glob(os.path.join(paks_dir or '', 'TSMod*.pak'))):
        h = hashlib.sha256()
        with open(p, 'rb') as f:
            for chunk in iter(lambda: f.read(1 << 20), b''): h.update(chunk)
        out.append((os.path.basename(p), os.path.getsize(p), h.hexdigest().upper()))
    return out


def export(crashes, out_zip, include_dumps=True, paks_dir='', user=None):
    """Write the zip. `crashes` = entries from list_crashes(). Returns the list of names written."""
    names = []
    info = [f'TSMod crash report, exported {datetime.datetime.now():%Y-%m-%d %H:%M:%S}',
            f'Editor version: {EDITOR_VERSION}', f'Game build (Steam): {game_build() or "unknown"}']
    paks = pak_info(paks_dir)
    info += [f'Pak: {n}  {s:,} bytes  SHA-256 {h}' for n, s, h in paks] or ['Pak: no TSMod pak found']
    info.append(f'Crashes: {len(crashes)}; crash dumps {"included" if include_dumps else "left out"}')
    with zipfile.ZipFile(out_zip, 'w', zipfile.ZIP_DEFLATED) as z:
        for c in crashes:
            sub = f'{c["time"]:%Y%m%d-%H%M%S}_{os.path.basename(c["dir"])}'
            txt = open(os.path.join(c['dir'], CONTEXT), encoding='utf-8', errors='replace').read()
            z.writestr(f'{sub}/{CONTEXT}', clean(txt, user)); names.append(f'{sub}/{CONTEXT}')
            if include_dumps and c['has_dump']:
                z.write(os.path.join(c['dir'], DUMP), f'{sub}/{DUMP}'); names.append(f'{sub}/{DUMP}')
            info.append(f'  {c["time"]:%Y-%m-%d %H:%M:%S}  {c["error"] or c["frame"]}')
        logs = find_logs(paks_dir)
        for p in logs:
            z.writestr(os.path.basename(p), clean(open(p, encoding='utf-8', errors='replace').read(), user))
            names.append(os.path.basename(p))
        info.append(f'TSMod log: {", ".join(os.path.basename(p) for p in logs) if logs else "not found"}')
        z.writestr('info.txt', clean('\n'.join(info) + '\n', user)); names.append('info.txt')
    return names
