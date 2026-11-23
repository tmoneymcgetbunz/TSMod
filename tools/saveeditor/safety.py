"""Save safety for the editor: game-running check, timestamped backups (with restore and pins), the slot 1 lock,
and verified writes. Nothing here writes outside the save folder and the editor's own data folder.
"""
import datetime, glob, hashlib, json, os, shutil, subprocess, sys

from . import model

KEEP_BACKUPS = 40                    # unpinned backups kept; pinned ones are never pruned


def sha256(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest().upper()


def find_save_dirs():
    """Every Steam user's SaveGames folder: Documents/My Games/TRIANGLE_STRATEGY/Steam on Windows, the same folder in
    the game's Proton prefix on Linux / Steam Deck (tools/paths.py save_roots)."""
    try:
        import paths
        roots = paths.save_roots()
    except Exception:
        roots = [os.path.join(os.path.expanduser('~'), 'Documents', 'My Games', 'TRIANGLE_STRATEGY', 'Steam')]
    out = []
    for r in roots:
        out += [d for d in glob.glob(os.path.join(r, '*', 'SaveGames')) if os.path.isdir(d)]
    return out


def find_paks_dir():
    try:
        import paths                    # tools/paths.py: TS_PAKS_DIR, tools/local_paths.json, usual Steam folders
        return paths.paks_dir()
    except Exception:
        return ''


GAME_EXE = 'TRIANGLE_STRATEGY'      # TRIANGLE_STRATEGY.exe / TRIANGLE_STRATEGY-Win64-Shipping.exe


def game_running(proc='/proc', force_linux=False):
    """True while the game runs. Windows: tasklist. Linux / Steam Deck: the game runs under Proton (Wine), so look for its
    .exe in every process's command line (/proc), skipping this editor's own process. If the check itself fails, answer
    True: the callers then refuse to write, which is the safe side."""
    if os.name == 'nt' and not force_linux:
        try:
            out = subprocess.run(['tasklist', '/fo', 'csv', '/nh'], capture_output=True, text=True,
                                 creationflags=0x08000000).stdout
        except Exception:
            return True
        return GAME_EXE in out.upper()
    me = os.getpid()
    try:
        pids = [d for d in os.listdir(proc) if d.isdigit()]
    except OSError:
        return True
    for d in pids:
        if int(d) == me: continue
        try:
            cmd = open(os.path.join(proc, d, 'cmdline'), 'rb').read().replace(b'\0', b' ').decode('utf-8', 'replace').upper()
        except OSError:
            continue
        if GAME_EXE + '.EXE' in cmd or GAME_EXE + '-WIN64-SHIPPING' in cmd:
            return True
    return False


def open_folder(path):
    """Show a folder in the desktop's file manager (Explorer, Dolphin on Steam Deck, Finder)."""
    if os.name == 'nt':
        os.startfile(path)
    else:
        subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open', path])


class Safety:
    def __init__(self, data_dir, protected_sha=model.PROTECTED_SLOT1_SHA256):
        self.data_dir = data_dir
        self.backup_dir = os.path.join(data_dir, 'backups')
        os.makedirs(self.backup_dir, exist_ok=True)
        self.protected_sha = protected_sha.upper()
        self.slot1_unlocked = False          # per write: the UI asks, then sets it for one write

    # ---- slot 1 lock
    def is_locked(self, path):
        """Slot 1 by name, or any file that is a byte copy of the protected save (wherever it is)."""
        if os.path.basename(path) == 'TRIANGLE_STRATEGY-SaveData_0.sav': return True
        try:
            return os.path.isfile(path) and sha256(path) == self.protected_sha
        except OSError:
            return False

    @staticmethod
    def is_game_save_location(path):
        """True for a game save file name (TRIANGLE_STRATEGY-*.sav) or any path inside a game SaveGames folder: those
        must only be written by write()/restore() (lock, game check, backup, verify)."""
        name = os.path.basename(path)
        if name.upper().startswith('TRIANGLE_STRATEGY-') and name.lower().endswith('.sav'): return True
        d = os.path.normcase(os.path.abspath(os.path.dirname(path)))
        for sd in find_save_dirs():
            sd = os.path.normcase(os.path.abspath(sd))
            if d == sd or d.startswith(sd + os.sep): return True
        parts = [p.upper() for p in d.split(os.sep)]
        return 'SAVEGAMES' in parts and 'TRIANGLE_STRATEGY' in parts

    def locked_reason(self, path):
        if not self.is_locked(path): return ''
        if os.path.basename(path) == 'TRIANGLE_STRATEGY-SaveData_0.sav':
            return 'Slot 1 is locked to keep your main save safe. You can unlock it for a single write.'
        return ('This file is an exact copy of your protected slot 1 save, so it is locked too. '
                'You can unlock it for a single write.')

    # ---- backups
    def backup(self, save_dir, reason, pin=False, keep=None):
        stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        dest = os.path.join(self.backup_dir, stamp + ('-pin' if pin else ''))
        n = 1
        while os.path.exists(dest): dest = f'{dest}_{n}'; n += 1
        os.makedirs(dest)
        manifest = {'reason': reason, 'from': save_dir, 'files': {}}
        for f in sorted(os.listdir(save_dir)):
            src = os.path.join(save_dir, f)
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(dest, f))
                h1, h2 = sha256(src), sha256(os.path.join(dest, f))
                if h1 != h2: raise IOError(f'backup copy of {f} does not match')
                manifest['files'][f] = h1
        json.dump(manifest, open(os.path.join(dest, 'manifest.json'), 'w'), indent=1)
        self.prune(keep)
        return dest

    def list_backups(self):
        out = []
        for d in sorted(os.listdir(self.backup_dir), reverse=True):
            p = os.path.join(self.backup_dir, d)
            m = os.path.join(p, 'manifest.json')
            if os.path.isdir(p) and os.path.exists(m):
                out.append({'name': d, 'path': p, 'pinned': '-pin' in d, **json.load(open(m))})
        return out

    def prune(self, keep=None):
        """Drop unpinned backups beyond KEEP_BACKUPS, oldest first, never the one in `keep` (a restore's source)."""
        keep = os.path.normcase(os.path.abspath(keep)) if keep else None
        unpinned = [b for b in self.list_backups() if not b['pinned']]
        for b in unpinned[KEEP_BACKUPS:]:
            if keep and os.path.normcase(os.path.abspath(b['path'])) == keep: continue
            shutil.rmtree(b['path'], ignore_errors=True)

    def pin(self, backup_path):
        if '-pin' in backup_path: return backup_path
        new = backup_path + '-pin'; os.rename(backup_path, new); return new

    def restore(self, backup_path, filename, save_dir):
        try:
            if game_running(): raise RuntimeError('Close the game first: it can overwrite a restored save.')
            src = os.path.join(backup_path, filename)
            dst = os.path.join(save_dir, filename)
            if self.is_locked(dst) and not self.slot1_unlocked: raise PermissionError(self.locked_reason(dst))
            data = open(src, 'rb').read()            # read first: the backup below must never prune the source
            want = hashlib.sha256(data).hexdigest().upper()
            self.backup(save_dir, f'before restoring {filename} from {os.path.basename(backup_path)}', keep=backup_path)
            tmp = dst + '.tsmod_tmp'
            open(tmp, 'wb').write(data)
            os.replace(tmp, dst)
            if sha256(dst) != want: raise IOError('restored file does not match the backup')
        finally:
            self.slot1_unlocked = False             # the unlock is for one attempt, whatever happens

    # ---- writing
    def write(self, save, dest_path):
        """Write an edited save: game closed, slot lock, full-folder backup, write, re-read and verify."""
        try:
            if game_running(): raise RuntimeError('The game is running. Close it first, or it may overwrite the save.')
            if self.is_locked(dest_path) and not self.slot1_unlocked: raise PermissionError(self.locked_reason(dest_path))
            save_dir = os.path.dirname(dest_path)
            blob = save.encoded()
            tmp = dest_path + '.tsmod_tmp'
            open(tmp, 'wb').write(blob)
            try:
                model.Save(tmp)                          # full parse: raises if the structure is broken
            except (Exception, SystemExit) as e:         # tsunits reports layout problems as SystemExit
                os.remove(tmp)
                raise model.ParseError(f'the edited save does not parse: {e}') from None
            bdir = self.backup(save_dir, f'before writing {os.path.basename(dest_path)}')
            os.replace(tmp, dest_path)
        finally:
            self.slot1_unlocked = False                  # the unlock is for one attempt, whatever happens
        if sha256(dest_path) != hashlib.sha256(blob).hexdigest().upper(): raise IOError('written file does not match')
        model.Save(dest_path)
        return bdir
