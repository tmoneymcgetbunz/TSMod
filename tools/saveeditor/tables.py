"""Game tables for the save editor's checks, read from the player's own pak files.

The vanilla pak's DataTables (and English text) are extracted once with tools/tspak.py (pure Python; repak.exe only
with TSMOD_PYPAK=0) and cached; every installed TSMod pak
(TSMod_*.pak in Content/Paks) is extracted too and overlays the vanilla rows, so the editor knows the ids the
installed mod adds. The cache is keyed by each pak's size and modification time.
"""
import glob, json, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import dtparse                                      # noqa: E402

# The publicly posted PC key (tools/tspak.py).
AES_KEY = '0x75D4C74524DE13DD968F3DE80349A6C984912E76A67E6851280EF1F01BFE4946'
DT = 'TRIANGLE_STRATEGY/Content/Newera/Data/DataTables'
NEEDED = ['GOP_Battle_Ability', 'GOP_Battle_Job', 'GOP_Battle_Weapon', 'GOP_Battle_UnitParam', 'GOP_Unit_Master',
          'GOP_Battle_Accessary', 'GOP_Battle_Armor', 'GOP_Battle_Order', 'GOP_Battle_Info', 'GOP_Quest_Info',
          'GOP_Battle_StatusEffect', 'GOP_Item_Battle', 'GOP_Item_ClassMedal', 'GOP_Item_UpgradeMaterial',
          'GOP_Item_Status_Up', 'GOP_Item_Negotiate', 'GOP_Item_Pickup', 'GOP_Item_Drop', 'GOP_StoryChartTable',
          'GOP_Battle_WeaponAbilityTree', 'GOP_Note', 'GOP_Unit_Attached_Data_Set', 'GOP_PlaceNameSet', 'GOP_PlaceName',
          'GOP_Battle_AttackParam', 'GOP_Battle_CorrectParam']
TEXT = ['GOP_Text_Ability', 'GOP_Text_Common', 'GOP_Text_Job', 'GOP_Text_Weapon', 'GOP_Text_Item',
        'GOP_Text_Accessary', 'GOP_Text_StoryChart', 'GOP_Text_Note', 'GOP_Text_Quest']
# Character and place names in every language the game ships, to show a save made in any language in English.
OTHER_LANGS = ['jp', 'de', 'fr', 'it', 'es', 'cn', 'tw', 'ko']
CACHE_VERSION = 4                 # 4: + AttackParam / CorrectParam tables (review finding F), stamped only on success


def find_repak():
    for p in (os.path.join(os.path.dirname(HERE), 'repak', 'repak.exe'), os.path.join(HERE, 'repak.exe')):
        if os.path.exists(p): return p
    raise FileNotFoundError('repak.exe not found (tools/repak/)')


def use_python_reader():
    """Read paks with tools/tspak.py (the default everywhere since 2026-11-22: byte-identical output to repak on the game
    pak and a TSMod pak, 0.5 s instead of ~80 s, ~20 s with the pure-Python AES fallback; and it runs on Linux / Steam
    Deck). TSMOD_PYPAK=0 uses repak.exe instead (Windows, if present)."""
    if os.environ.get('TSMOD_PYPAK') == '0' and os.name == 'nt':
        try:
            find_repak(); return False
        except FileNotFoundError:
            return True
    return True


def extract_python(pak, includes, out):
    """tspak.py equivalent of `repak unpack -i ... -o out`: writes each listed file that the pak has to out/<path>.
    Returns how many were written. Raises on an unreadable pak."""
    import tspak                                       # tools/tspak.py (+ tools/aes_py.py without pycryptodome)
    p = tspak.Pak(pak)
    try:
        n = 0
        for path in includes:
            if path not in p.files: continue           # absent from this pak: normal for a mod pak
            dst = os.path.join(out, *path.split('/'))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, 'wb') as f: f.write(p.read(path))
            n += 1
        return n
    finally:
        p.f.close()


class Tables:
    def __init__(self, paks_dir, cache_dir, log=print):
        self.paks_dir, self.cache_dir, self.log = paks_dir, cache_dir, log
        self.rows = {}           # table -> {row: {field: value}}
        self.text = {}           # text key -> English
        self.mod_paks = []
        self.all_ids = set()
        self.foreign = {}        # a name in another language -> the same text key's English

    def _extract(self, pak, key, out):
        stamp = os.path.join(out, 'stamp.json')
        st = os.stat(pak); want = {'size': st.st_size, 'mtime': int(st.st_mtime), 'v': CACHE_VERSION}
        try:
            if os.path.exists(stamp) and json.load(open(stamp)) == want: return
        except ValueError:
            pass                                        # a damaged stamp: extract again
        self.log("Reading the game's data (one time, about a minute)..." if key else f'Reading {os.path.basename(pak)}...')
        # Start clean: a table the previous pak had and this one doesn't must not linger and overlay the game's rows.
        shutil.rmtree(out, ignore_errors=True)
        os.makedirs(out, exist_ok=True)
        includes = []
        for t in NEEDED: includes += [f'{DT}/{t}.uasset', f'{DT}/{t}.uexp']
        for t in TEXT: includes += [f'{DT}/Text/en/{t}.uasset', f'{DT}/Text/en/{t}.uexp']
        if key:                                       # the game pak: Common text in the other languages too
            for lg in OTHER_LANGS: includes += [f'{DT}/Text/{lg}/GOP_Text_Common.uasset', f'{DT}/Text/{lg}/GOP_Text_Common.uexp']
        core = os.path.join(out, *DT.split('/'), 'GOP_Battle_Ability.uasset')
        if use_python_reader():                       # Linux / Steam Deck, or no repak.exe
            try:
                extract_python(pak, includes, out)
            except Exception as e:
                raise RuntimeError(f'could not read {os.path.basename(pak)}: {e}')
            if key and not os.path.exists(core):
                raise RuntimeError(f'could not read {os.path.basename(pak)}: no data tables found')
            json.dump(want, open(stamp, 'w'))
            return
        cmd = [find_repak()] + (['-a', key] if key else []) + ['unpack', '-q', '-f', '-o', out]
        for i in includes: cmd += ['-i', i]
        cmd.append(pak)
        flags = 0x08000000 if os.name == 'nt' else 0      # no console window
        r = subprocess.run(cmd, check=False, capture_output=True, creationflags=flags)
        # repak exits 0 when an include is simply absent from the pak (normal for a mod pak) and 1 on a real failure
        # (unreadable pak, wrong key, disk error) [tested 2026-11-22]. Only a good extraction gets the stamp, so a failed
        # one is retried next start instead of being trusted.
        if r.returncode != 0 or (key and not os.path.exists(core)):
            err = (r.stderr or b'').decode('utf-8', 'replace').strip()[-300:]
            raise RuntimeError(f'could not read {os.path.basename(pak)} (repak exit {r.returncode}): {err or "no output"}')
        json.dump(want, open(stamp, 'w'))

    def _load_dir(self, root):
        base = os.path.join(root, *DT.split('/'))
        for t in NEEDED:
            p = os.path.join(base, t + '.uasset')
            if os.path.exists(p):
                try:
                    _, rows = dtparse.parse(p)
                    tab = self.rows.setdefault(t, {})
                    for k, r in rows.items(): tab[k] = {f: v['v'] for f, v in r.items()}
                except Exception as e:
                    self.log(f'  could not read {t}: {e}')
        for t in TEXT:
            p = os.path.join(base, 'Text', 'en', t + '.uasset')
            if os.path.exists(p):
                try:
                    _, rows = dtparse.parse(p)
                    for k, r in rows.items():
                        v = r.get('Text', {}).get('v')
                        if isinstance(v, str): self.text[k] = v
                except Exception as e:
                    self.log(f'  could not read {t}: {e}')

    def _load_foreign(self, root):
        base = os.path.join(root, *DT.split('/'), 'Text')
        for lg in OTHER_LANGS:
            p = os.path.join(base, lg, 'GOP_Text_Common.uasset')
            if not os.path.exists(p): continue
            try:
                _, rows = dtparse.parse(p)
            except Exception:
                continue
            for k, r in rows.items():
                if not k.startswith(('TEXT_COMMON_CH_NAME_', 'TEXT_COMMON_PLACE_', 'TEXT_COMMON_COUNTRY_', 'TEXT_COMMON_TERRITORY_')): continue
                v = r.get('Text', {}).get('v')
                if isinstance(v, str) and v.strip() and k in self.text: self.foreign.setdefault(v.strip(), self.text[k])

    def english(self, text):
        """A character or place name written in another language -> English (unchanged if unknown)."""
        return self.foreign.get((text or '').strip(), text)

    def place_of_level(self, level):
        """Level record (e.g. A1_EX_Ruins) -> English place name via the game's place-name tables."""
        if not level: return ''
        ps = self.row('GOP_PlaceNameSet', 'PLACENAMESET_' + level.upper())
        pn = self.row('GOP_PlaceName', (ps or {}).get('PlaceNameSet1'))
        if not pn: return ''
        for f in ('PlaceNameId', 'TerritoryNameId', 'CountryNameId'):
            t = self.text.get(pn.get(f))
            if t: return t.strip(' -')
        return ''

    def load(self):
        vanilla = os.path.join(self.paks_dir, 'TRIANGLE_STRATEGY-WindowsNoEditor.pak')
        if not os.path.exists(vanilla): raise FileNotFoundError(f'game pak not found: {vanilla}')
        out = os.path.join(self.cache_dir, 'vanilla'); self._extract(vanilla, AES_KEY, out); self._load_dir(out)
        self._load_foreign(out)
        # The game's own ids, before any TSMod pak overlays rows (Scrub TSMod data checks a save against these).
        self.vanilla_ids = set()
        for t in self.rows.values(): self.vanilla_ids |= set(t)
        self.mod_paks = sorted(glob.glob(os.path.join(self.paks_dir, 'TSMod*.pak')))
        for pak in self.mod_paks:
            out = os.path.join(self.cache_dir, 'mod_' + re.sub(r'\W', '_', os.path.basename(pak)))
            self._extract(pak, None, out); self._load_dir(out)
        self.all_ids = set()
        for t in self.rows.values(): self.all_ids |= set(t)
        return self

    # ---- lookups
    def row(self, table, key):
        return self.rows.get(table, {}).get(key)

    def name_of(self, rid):
        """English display name for a unit, ability, class, weapon or item id (falls back to the id)."""
        if not rid: return ''
        o = self.row('GOP_Battle_Order', rid)
        if o:
            if o.get('BattleOrderName') in self.text: return self.text[o['BattleOrderName']]
            rid = o.get('Ability') or rid                      # TSMod's Smuggle row names its ability
        for table, field in (('GOP_Battle_Ability', 'AbilityName'), ('GOP_Battle_Job', 'JobName'),
                             ('GOP_Battle_Weapon', 'WeaponName'), ('GOP_Battle_Accessary', 'AccessaryName')):
            r = self.row(table, rid)
            if r and r.get(field) in self.text: return self.text[r[field]]
        m = re.match(r'UNIT_MASTER_CH_([A-Z0-9]+)', rid)
        if m:
            r = self.row('GOP_Unit_Master', rid)
            key = (r or {}).get('CharacterName') or f'TEXT_COMMON_CH_NAME_{m.group(1)}'
            if key in self.text: return self.text[key]
        for key in (f'TEXT_{rid}_NAME', rid.replace('ITEM_', 'TEXT_ITEM_NAME_', 1), f'TEXT_ITEM_NAME_{rid[5:]}'):
            if key in self.text: return self.text[key]
        for t in self.rows:
            if t.startswith('GOP_Item'):
                r = self.rows[t].get(rid)
                if r:
                    for f, v in r.items():
                        if 'Name' in f and isinstance(v, str) and v in self.text: return self.text[v]
        return rid

    def unit_classes(self, uid):
        """Every class a unit can hold: its param's class and the promotion chain from it (classes are linked)."""
        um = self.row('GOP_Unit_Master', uid) or {}
        param = self.row('GOP_Battle_UnitParam', um.get('GrowthUnitBattleParamId'))
        if not param:
            m = re.match(r'UNIT_MASTER_CH_([A-Z0-9]+)', uid)
            param = m and (self.row('GOP_Battle_UnitParam', f'BATTLE_UNITPARAM_CH_{m.group(1)}_PARTY') or
                           self.row('GOP_Battle_UnitParam', f'BATTLE_UNITPARAM_CH_{m.group(1)}'))
        out, todo = set(), [param.get('UnitClass')] if param else []
        while todo:
            j = todo.pop()
            if not j or j == 'None' or j in out or j not in self.rows.get('GOP_Battle_Job', {}): continue
            out.add(j); r = self.rows['GOP_Battle_Job'][j]
            todo += [r.get(f) for f in ('JobTypeBefore', 'JobTypeAfter1', 'JobTypeAfter2', 'JobTypeAfter3',
                                         'JobTypeParallel1', 'JobTypeParallel2')]
        return out

    def class_learnables(self, jobs):
        out = set()
        for j in jobs:
            r = self.row('GOP_Battle_Job', j) or {}
            for k in range(1, 11):
                a = r.get(f'LearnableAbility{k}')
                if a and a != 'None': out.add(a)
        return out

    def weapon_line(self, weapon):
        """A weapon and its rank-up / rank-down chain, plus every ability its trees grant."""
        seen, todo, abil = set(), [weapon], set()
        while todo:
            w = todo.pop()
            if not w or w == 'None' or w in seen: continue
            r = self.row('GOP_Battle_Weapon', w)
            if not r: continue
            seen.add(w); todo += [r.get('RankUpWeapon'), r.get('RankDownWeapon')]
            if r.get('Ability') and r['Ability'] != 'None': abil.add(r['Ability'])
            t = self.row('GOP_Battle_WeaponAbilityTree', r.get('WeaponAbilityTree'))
            for f, v in (t or {}).items():
                if f.startswith('AbilityId') and v and v != 'None': abil.add(v)
        return seen, abil
