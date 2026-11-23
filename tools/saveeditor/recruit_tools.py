"""TSMod recruit records in a save: remove, back up, restore, and scrub every TSMod trace (user design 2026-11-23;
mods/recruit_records_proposal.md).

What a save holds for a recruit [read 2026-11-23]: everything is inside the character's own unit record (level,
EXP, stats, class, learned moves, weapon, tree purchases, weapon skills, equipped accessories, squad byte end-6,
party-state byte end-7). Outside the records the game keeps only vanilla data about them (dialogue history, outfit-set
entries that name vanilla rows). Equipped accessories are counted in the inventory map too (owned = map count,
equipped ones included [inferred from every count >= the units wearing it]), so removing a record leaves the item
owned and unequipped; restoring a record into a save that owns fewer adds the missing ones.

Refused: Continue saves (header byte 0x0A = 2) and any save with TSMod ids outside the recruit records (a suspended
battle references deployed units; the Test 23 crash came from such state).
"""
import base64, datetime, json, os, re

from . import model, checks

HERE = os.path.dirname(os.path.abspath(__file__))
FORMAT = 'tsmod-recruit'
FORMAT_VERSION = 1
FAST_CH1_FLAG = 'TEST_FLAG'          # mods/fast_ch1 (the game never sets or reads it)
TSMOD_FLAGS = [FAST_CH1_FLAG]        # every piece of TSMod save state outside the records; keep SAVE_FORMAT.md in step
MOD_ID = re.compile(rb'(?<![A-Z0-9_])[A-Z0-9_]*_[NM]\d{3}P(?:_[A-Z0-9_]*)?(?![A-Z0-9_])|'
                    rb'(?<![A-Z0-9_])BATTLE_UNITPARAM_CH_[NM]\d{3}_PARTY(?![A-Z0-9_])')
ACC = re.compile(rb'BATTLE_ACCESSARY_[A-Z0-9_]+(?=\x00)')


def recruit_ids():
    """The 20 TSMod recruits' unit ids (the editor's recruit data)."""
    return sorted(json.load(open(os.path.join(HERE, 'recruit_records.json'), encoding='utf-8'))['records'])


def in_save(save):
    have = set(save.unit_ids())
    return [u for u in recruit_ids() if u in have]


def save_kind(save):
    """0 slot, 1 autosave, 2 Continue (plaintext byte 0x0A) [read: SAVE_FORMAT.md, checked on three saves]."""
    return save.plaintext()[10]


def refuse_reason(save):
    """Why recruit records can't be removed or restored in this save, or None."""
    if save_kind(save) == 2:
        return 'This is a Continue save (a suspended battle). Load it, finish or leave the battle, save to a slot, then edit that.'
    b = bytes(save.s1)
    recs = [(s, e) for u, s, e in save.unit_recs if u in set(recruit_ids())]
    outside = sorted({m.group().decode() for m in MOD_ID.finditer(b) if not any(s <= m.start() < e for s, e in recs)})
    if outside:
        return (f'This save references TSMod ids outside the recruit records ({", ".join(outside[:4])}'
                f'{" …" if len(outside) > 4 else ""}), e.g. a saved battle. Save to a slot outside battle first.')
    return None


def equipped_accessories(rec):
    """{accessory id: number of slots} in one record (an id written once per slot it occupies)."""
    out = {}
    for m in ACC.finditer(rec):
        k = m.group().decode(); out[k] = out.get(k, 0) + 1
    return out


def _describe(save, T, uid):
    info = save.unit_info(uid)
    name = T.name_of(uid) if T else uid
    job = info['jobs'][0] if info['jobs'] else ''
    return name, info['stats']['level'], (T.name_of(job) if T and job else job)


def backup(save, T, uids, folder, source=''):
    """Write one file per recruit; returns the paths."""
    os.makedirs(folder, exist_ok=True)
    out = []
    stamp = datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S')
    for uid in uids:
        s, e = save.unit_record(uid)
        name, lv, job = _describe(save, T, uid)
        d = {'format': FORMAT, 'format_version': FORMAT_VERSION, 'unit': uid, 'name': name, 'level': lv, 'class': job,
             'save_version': save.version, 'source': source, 'date': stamp,
             'tsmod_paks': [os.path.basename(p) for p in getattr(T, 'mod_paks', [])] if T else [],
             'record': base64.b64encode(bytes(save.s1[s:e])).decode()}
        safe = re.sub(r'[^\w-]+', '_', name)
        p = os.path.join(folder, f'{safe}_Lv{lv}_{stamp}.tsrecruit')
        with open(p, 'w', encoding='utf-8') as f: json.dump(d, f, ensure_ascii=False, indent=1)
        out.append(p)
    return out


def read_backup(path):
    d = json.load(open(path, encoding='utf-8'))
    if d.get('format') != FORMAT: raise ValueError(f'{os.path.basename(path)} is not a TSMod recruit backup')
    if d.get('format_version', 0) > FORMAT_VERSION:
        raise ValueError(f'{os.path.basename(path)} was made by a newer editor')
    d['record_bytes'] = base64.b64decode(d['record'])
    return d


def remove(save, uids, status):
    """Delete these recruits' records (accessories stay owned and become unequipped). Returns the removed ids."""
    why = refuse_reason(save)
    if why: raise ValueError(why)
    done = []
    for uid in uids:
        if uid in save.unit_ids():
            save.remove_unit_record(uid, status); done.append(uid)
    return done


def restore_check(save, T, d):
    """(rating, message) for restoring one backup into this save (no change)."""
    if d['save_version'] != save.version:
        return checks.DANGER, (f"the backup is from save format version {d['save_version']:#x}, this save is "
                               f"{save.version:#x}: the record layout may differ")
    if T is not None:
        st, msg = checks.record_status(T, d['unit'], d['record_bytes'])
        if st == checks.DANGER: return st, msg
    return checks.RISKY, ("replaces the character's record" if d['unit'] in save.unit_ids() else 'adds the character')


def restore(save, d, status):
    """Put one backup's record into the save (replace or add); add owned accessories the save lacks. Returns notes."""
    why = refuse_reason(save)
    if why: raise ValueError(why)
    uid, rec = d['unit'], d['record_bytes']
    notes = []
    if uid in save.unit_ids():
        save.remove_unit_record(uid, status); notes.append('replaced the existing record')
    save.insert_unit_record(uid, rec, status)
    # Owned accessories must cover every equipped one: count what all records wear now.
    worn = {}
    for u, s, e in save.unit_recs:
        for k, n in equipped_accessories(bytes(save.s1[s:e])).items(): worn[k] = worn.get(k, 0) + n
    owned = {k: v for k, _, v in save.map_by_label('accessories')['entries']}
    for k in equipped_accessories(rec):
        if owned.get(k, 0) < worn.get(k, 0):
            save.set_map_value('accessories', k, worn[k], status); notes.append(f'{k}: owned {owned.get(k, 0)} -> {worn[k]}')
    return notes


def leftover_ids(save, T):
    """Ids in the save that the vanilla game lacks (TSMod's), without the known vanilla orphans and drop/money ids."""
    seen = {x.decode() for x in re.findall(checks.ID_PATTERN, save.plaintext())}
    van = getattr(T, 'vanilla_ids', set())
    return sorted(x for x in seen - van - checks.VANILLA_ORPHANS if not x.startswith(('ITEM_DROP', 'ITEM_MONEY')))


def scrub(save, T, status):
    """Remove every recruit and every other TSMod state the save can hold, then check the save against the vanilla
    tables. Returns {'removed', 'flags_cleared', 'leftovers'} (leftovers empty = vanilla-friendly as far as the ids go)."""
    removed = remove(save, in_save(save), status)
    cleared = []
    for fl in TSMOD_FLAGS:
        try:
            if save.flag(fl)[1]: save.set_flag(fl, 0, status); cleared.append(fl)
        except KeyError:
            pass
    return {'removed': removed, 'flags_cleared': cleared, 'leftovers': leftover_ids(save, T) if T else None}
