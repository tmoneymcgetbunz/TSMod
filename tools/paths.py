"""Where the game and its saves are. Used by every tool that reads the game's own pak, and by the save editor.

Game paks, resolution order:
1. the TS_PAKS_DIR environment variable (the game's Content/Paks folder);
2. tools/local_paths.json {"paks_dir": "..."} (not committed);
3. every Steam library listed in Steam's libraryfolders.vdf (Windows, Linux and Steam Deck, incl. SD cards);
4. the usual Windows library folders.

Saves (save_roots): Windows keeps them in Documents/My Games/TRIANGLE_STRATEGY/Steam. On Linux and Steam Deck the game
runs through Proton, which keeps the same folder inside the game's prefix:
<library>/steamapps/compatdata/<app id>/pfx/drive_c/users/steamuser/Documents/My Games/TRIANGLE_STRATEGY/Steam.

TS_STEAM_ROOTS (os.pathsep-separated) replaces the built-in Steam root list (used by the offline tests).
"""
import glob, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
GAME_DIR = 'TRIANGLE STRATEGY'
SUB = os.path.join('steamapps', 'common', GAME_DIR, 'TRIANGLE_STRATEGY', 'Content', 'Paks')
PAK_NAME = 'TRIANGLE_STRATEGY-WindowsNoEditor.pak'
APP_ID = '1850510'                  # read from appmanifest_1850510.acf (2026-11-22); also found at run time
SAVE_TAIL = os.path.join('My Games', 'TRIANGLE_STRATEGY', 'Steam')


def steam_roots():
    """Steam install folders on this machine (existing ones only)."""
    env = os.environ.get('TS_STEAM_ROOTS')
    if env:
        cands = env.split(os.pathsep)
    elif os.name == 'nt':
        cands = [r'C:\Program Files (x86)\Steam', r'C:\Program Files\Steam']
    else:
        h = os.path.expanduser('~')
        cands = [os.path.join(h, '.local', 'share', 'Steam'), os.path.join(h, '.steam', 'steam'),
                 os.path.join(h, '.steam', 'root'),
                 os.path.join(h, '.var', 'app', 'com.valvesoftware.Steam', '.local', 'share', 'Steam')]   # Flatpak Steam
    out = []
    for c in cands:
        if c and os.path.isdir(c):
            r = os.path.realpath(c)
            if r not in out: out.append(r)
    return out


def library_dirs():
    """Every Steam library folder: the roots plus the "path" entries of steamapps/libraryfolders.vdf (SD cards...)."""
    out = []
    def add(p):
        if p and os.path.isdir(p):
            r = os.path.realpath(p)
            if r not in out: out.append(r)
    for root in steam_roots():
        add(root)
        for vdf in (os.path.join(root, 'steamapps', 'libraryfolders.vdf'), os.path.join(root, 'config', 'libraryfolders.vdf')):
            try:
                txt = open(vdf, encoding='utf-8', errors='replace').read()
            except OSError:
                continue
            for m in re.finditer(r'"path"\s+"([^"]*)"', txt):
                add(m.group(1).replace('\\\\', '\\'))
    return out


def app_ids():
    """The game's Steam app id(s) from the appmanifest in each library, plus the known one."""
    ids = []
    for lib in library_dirs():
        for acf in glob.glob(os.path.join(lib, 'steamapps', 'appmanifest_*.acf')):
            try:
                txt = open(acf, encoding='utf-8', errors='replace').read()
            except OSError:
                continue
            if re.search(r'"installdir"\s+"%s"' % re.escape(GAME_DIR), txt):
                m = re.search(r'"appid"\s+"(\d+)"', txt)
                if m and m.group(1) not in ids: ids.append(m.group(1))
    if APP_ID not in ids: ids.append(APP_ID)
    return ids


def candidates():
    env = os.environ.get('TS_PAKS_DIR')
    if env: yield env
    local = os.path.join(HERE, 'local_paths.json')
    if os.path.exists(local):
        p = json.load(open(local, encoding='utf-8')).get('paks_dir')
        if p: yield p
    for lib in library_dirs():
        yield os.path.join(lib, SUB)
    if os.name == 'nt':
        for drive in 'CDEFGH':
            for lib in ('SteamLibrary', 'Steam', r'Games\SteamLibrary', r'Program Files (x86)\Steam'):
                yield os.path.join(f'{drive}:\\', lib, SUB)


def paks_dir():
    for c in candidates():
        if os.path.exists(os.path.join(c, PAK_NAME)): return c
    raise FileNotFoundError('Triangle Strategy not found. Set TS_PAKS_DIR to its Content/Paks folder, '
                            'or put {"paks_dir": "..."} in tools/local_paths.json.')


def game_pak():
    return os.path.join(paks_dir(), PAK_NAME)


def save_roots():
    """Folders holding <steam user id>/SaveGames: Documents on Windows, the Proton prefix(es) elsewhere."""
    roots = [os.path.join(os.path.expanduser('~'), 'Documents', SAVE_TAIL)]
    for lib in library_dirs():
        for aid in app_ids():
            roots.append(os.path.join(lib, 'steamapps', 'compatdata', aid, 'pfx', 'drive_c', 'users', 'steamuser',
                                      'Documents', SAVE_TAIL))
    out = []
    for r in roots:
        if os.path.isdir(r) and r not in out: out.append(r)
    return out
