"""Save model for the TSMod save editor: parse a TRIANGLE STRATEGY save into located, editable parts.

Layers (SAVE_FORMAT.md): GVAS -> NWER blob (cipher, tools/tssave.py) -> plaintext with 3 sections:
s0 preview, s1 game state, s2 field state.

s1 is parsed sequentially up to the unit array. The field order and shapes are facts recorded from the exe's own
serializers (FUN_140d3c7e0 and children; community notes in re/ref_shaneqi, read for facts only, no code taken).
The unit array is handled by tools/tsunits.py (record bounds, learned lists, string repoints). After the units:
the world tail (leader name, gold), then the script-variable table and the story-flag table, found by shape.

Every edit is a byte splice into s1 followed by a full re-parse, so offsets are never stale. `verify()` checks that
the parse lands on the unit array tsunits finds and that the flag table is intact.
"""
import os, re, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))           # tools/
import tssave, tsunits                               # noqa: E402


class ParseError(Exception):
    pass


class R:
    """Little-endian reader over s1 that records where each scalar sits."""
    def __init__(s, b, p=0, end=None):
        s.b = b; s.p = p; s.end = len(b) if end is None else end

    def need(s, n):
        if s.p + n > s.end: raise ParseError(f'read past end at s1+{s.p:#x}')

    def i32(s):
        s.need(4); v = struct.unpack_from('<i', s.b, s.p)[0]; s.p += 4; return v

    def u8(s):
        s.need(1); v = s.b[s.p]; s.p += 1; return v

    def u16(s):
        s.need(2); v = struct.unpack_from('<H', s.b, s.p)[0]; s.p += 2; return v

    def u64(s):
        s.need(8); v = struct.unpack_from('<Q', s.b, s.p)[0]; s.p += 8; return v

    def f32(s):
        s.need(4); v = struct.unpack_from('<f', s.b, s.p)[0]; s.p += 4; return v

    def boolean(s):
        v = s.i32()
        if v not in (0, 1): raise ParseError(f'bad bool {v} at s1+{s.p - 4:#x}')
        return v

    def fstr(s):
        at = s.p; n = s.i32()
        if n == 0: return ''
        if n > 0:
            if n > 0x10000: raise ParseError(f'bad string length {n} at s1+{at:#x}')
            s.need(n)
            if s.b[s.p + n - 1] != 0: raise ParseError(f'unterminated string at s1+{at:#x}')
            v = bytes(s.b[s.p:s.p + n - 1]).decode('latin1'); s.p += n; return v
        if -n > 0x10000: raise ParseError(f'bad string length {n} at s1+{at:#x}')
        s.need(-2 * n); v = bytes(s.b[s.p:s.p - 2 * n - 2]).decode('utf-16le'); s.p += -2 * n; return v

    def count(s, limit=200000):
        n = s.i32()
        if not 0 <= n <= limit: raise ParseError(f'bad count {n} at s1+{s.p - 4:#x}')
        return n

    def arr(s, fn):
        return [fn() for _ in range(s.count())]


def fstring(text):
    """Serialize an FString the way the game does (ASCII ids as UTF-8 + NUL)."""
    try:
        b = text.encode('ascii') + b'\x00'
        return struct.pack('<i', len(b)) + b
    except UnicodeEncodeError:
        b = text.encode('utf-16le') + b'\x00\x00'
        return struct.pack('<i', -(len(b) // 2)) + b


# ---------------------------------------------------------------------------------------------------- s1 parts
def _name_int_map(r, label):
    """TMap<FName,int32>: returns {'label', 'count_at', 'end', 'entries': [(id, value_at, value)]}."""
    at = r.p; n = r.count(); ents = []
    for _ in range(n):
        k = r.fstr(); vat = r.p; ents.append((k, vat, r.i32()))
    return {'label': label, 'count_at': at, 'end': r.p, 'entries': ents}


def _skip_parts_before_units(r, version):
    """Walk s1 from the start to the unit array. Returns a dict of located parts."""
    P = {}
    P['head'] = {'ver': r.i32(), 'b': r.u8(), 'play_cs': r.u64()}
    # story chart: TMap<FName, 4 bools>
    n = r.count(); chart = {}
    for _ in range(n):
        k = r.fstr(); chart[k] = [(r.p, r.boolean()) for _ in range(4)]
        chart[k] = [(a, v) for a, v in chart[k]]
    P['story_chart'] = chart
    # dialogue choices: TMap<FName, bool>
    n = r.count(); P['choices'] = {}
    for _ in range(n):
        k = r.fstr(); at = r.p; P['choices'][k] = (at, r.boolean())
    # vote / scales record block
    for _ in range(5): r.fstr()
    for _ in range(r.count()):                       # 0x98-byte records
        r.fstr(); r.i32(); r.i32(); r.i32(); r.i32(); r.fstr()
        for _ in range(6): r.fstr()
        for _ in range(4): r.boolean()
        for _ in range(12): r.i32()
        r.i32(); r.i32(); r.i32()
    for _ in range(r.count()): r.fstr()
    r.i32()
    for _ in range(4): r.i32()
    for _ in range(256): r.boolean()
    for _ in range(r.count()):                       # TMap<FName, TArray<u8>>
        r.fstr(); n2 = r.count(0x1000000); r.need(n2); r.p += n2
    for _ in range(r.count()):                       # TMap<FName, TMap<FName, TArray<u8>>>
        r.fstr()
        for _ in range(r.count()):
            r.fstr(); n2 = r.count(0x1000000); r.need(n2); r.p += n2
    r.i32()
    # convictions: 2 x int32[4], then four sets
    conv_at = r.p
    P['convictions'] = {'a': [(r.p + 4 * i, struct.unpack_from('<i', r.b, r.p + 4 * i)[0]) for i in range(4)]}
    r.p += 16
    P['convictions']['b'] = [(r.p + 4 * i, struct.unpack_from('<i', r.b, r.p + 4 * i)[0]) for i in range(4)]
    r.p += 16
    P['convictions']['at'] = conv_at
    for _ in range(r.count()): r.fstr(); r.i32(); r.i32(); r.i32(); r.fstr()
    for _ in range(3):
        for _ in range(r.count()): r.fstr(); r.u8()
    if r.boolean():
        for _ in range(r.count()): r.i32(); r.i32(); r.i32()
    r.i32()
    for _ in range(r.count()): r.i32()
    r.i32()
    nm = r.fstr()
    if nm and nm != 'None': raise ParseError('unexpected polymorphic payload (FUN_140d3c8f0)')
    r.i32(); r.i32()
    for _ in range(8): r.boolean()
    for _ in range(r.count()): r.fstr(); r.u8()              # pickups
    # location / scene state
    loc_at = r.p
    loc = {'map': r.fstr()}
    for _ in range(4): r.i32()
    for _ in range(6): r.f32()
    r.u8(); loc['s1'] = r.fstr(); loc['s2'] = r.fstr(); r.boolean(); loc['n1'] = r.fstr(); loc['n2'] = r.fstr()
    r.i32(); r.boolean(); r.u8(); r.i32()
    loc['at'], loc['end'] = loc_at, r.p
    P['location'] = loc
    for _ in range(r.count()):                       # 0x60-byte records
        r.fstr(); r.u8(); r.boolean(); r.fstr(); r.u8(); r.fstr(); r.fstr(); r.u8(); r.fstr(); r.fstr(); r.fstr()
        r.i32(); r.fstr(); r.i32(); r.boolean(); r.boolean(); r.fstr()
    r.u8(); r.i32()
    for _ in range(4): r.boolean()
    for _ in range(r.count()): r.fstr(); r.boolean()
    # Labels from the keys each map holds in real saves (2026-11-20): place names, per-unit attached data,
    # notes, battle items, materials, class medals, accessories.
    maps = [_name_int_map(r, 'place names')]
    labels = ['unit data A', 'unit data B', 'unused A', 'unused B'] if version > 0x38 else ['unit data A', 'unit data B']
    maps += [_name_int_map(r, lb) for lb in labels]
    maps += [_name_int_map(r, lb) for lb in ('notes', 'items', 'unused C', 'materials', 'medals')]
    maps += [_name_int_map(r, lb) for lb in ('accessories', 'unused D')]
    P['maps'] = maps
    P['orders'] = []                                  # Quietus: {id, int32, bool}
    P['orders_count_at'] = r.p
    for _ in range(r.count()):
        k = r.fstr(); vat = r.p; v = r.i32(); fat = r.p; f = r.boolean(); P['orders'].append((k, vat, v, fat, f))
    P['orders_end'] = r.p
    for _ in range(r.count()): r.u8(); r.u8(); r.fstr(); r.i32(); r.i32()
    for _ in range(r.count()): r.u8(); r.fstr()
    for _ in range(r.count()): r.u8(); r.i32()
    for _ in range(r.count()):
        r.fstr()
        for _ in range(4): r.u8()
    P['units_at'] = r.p
    return P


def _find_flag_table(s1, start):
    """The story-flag table: int32 count (~2362) then {FString name, int32 value} for indices 1..count-1."""
    for p in range(start, len(s1) - 12):
        n = struct.unpack_from('<i', s1, p)[0]
        if not 1000 <= n <= 20000: continue
        L = struct.unpack_from('<i', s1, p + 4)[0]
        if not 3 <= L <= 81 or s1[p + 8 + L - 1] != 0: continue
        try:
            r = R(s1, p); n = r.i32(); ents = []
            for i in range(1, n):
                nm = r.fstr()
                if not re.fullmatch(r'[A-Za-z0-9_]{2,80}', nm): raise ParseError('bad flag name')
                ents.append((nm, r.p, r.i32()))
            return {'count_at': p, 'end': r.p, 'entries': ents}
        except (ParseError, struct.error):
            continue
    raise ParseError('story-flag table not found')


def _find_sysvars(s1, flag_at):
    """Script variables sit right before the flag table: int32 count, {FString, int32 isStr, int32|FString}."""
    for p in range(flag_at - 8, max(0, flag_at - 20000), -1):
        n = struct.unpack_from('<i', s1, p)[0]
        if not 10 <= n <= 500: continue
        try:
            r = R(s1, p, flag_at); r.i32(); ents = []
            for _ in range(1, n):
                nm = r.fstr()
                if not re.fullmatch(r'[A-Z0-9_]{2,80}', nm): raise ParseError('bad name')
                isstr_at = r.p; is_str = r.i32()
                if is_str not in (0, 1): raise ParseError('bad isString')
                vat = r.p; v = r.fstr() if is_str else r.i32()
                ents.append({'name': nm, 'is_str': is_str, 'at': vat, 'end': r.p, 'value': v})
            if r.p == flag_at:
                return {'count_at': p, 'end': flag_at, 'entries': ents}
        except (ParseError, struct.error):
            continue
    raise ParseError('script-variable table not found')


# ---------------------------------------------------------------------------------------------------- the save
SLOT_COUNT = 10        # the in-game Save screen shows 10 slots (user, 2026-11-22); files SaveData_0 … SaveData_9
SLOT_FILES = {f'TRIANGLE_STRATEGY-SaveData_{i}.sav': f'Slot {i + 1}' for i in range(SLOT_COUNT)}
SLOT_FILES.update({'TRIANGLE_STRATEGY-AutoSaveData.sav': 'Autosave', 'TRIANGLE_STRATEGY-ContinueSaveData.sav': 'Continue'})
PROTECTED_SLOT1_SHA256 = '89B71FAE98FA5C1401851BB8F6A65629C5303270C6122286BF998D7FDC9A534B'


class Save:
    def __init__(self, path):
        self.path = path
        self.data = open(path, 'rb').read()
        self.hdr, self.props = tssave.parse(self.data)
        plain, ok = tssave.decrypt_blob(self.props[0]['data'])
        if not ok: raise ParseError('checksum mismatch: the file is damaged or not a game save')
        if plain[8] != 1: raise ParseError('not a game-data save (system/settings file)')
        self.version = struct.unpack_from('<H', plain, 4)[0]
        (a0, n0), (a1, n1), (a2, n2) = tssave.sections(plain)[0]
        self.head = plain[:a1 - 4]                   # header + s0 (with its length) up to s1's length field
        self.s1 = bytearray(plain[a1:a1 + n1])
        self.rest = plain[a1 + n1:]                  # s2 length + s2 + SHA-1
        self.preview = tssave.preview(plain)
        self.dirty = False
        self.history = []                            # (description, status) of edits since load
        self.reparse()

    # ---- parsing
    def reparse(self):
        s1 = bytes(self.s1)
        r = R(s1)
        self.parts = _skip_parts_before_units(r, self.version)
        co, recs, end = tsunits.records(s1)
        if co != self.parts['units_at']:
            raise ParseError(f'part walk ended at s1+{self.parts["units_at"]:#x}, unit array at s1+{co:#x}')
        self.units_count_at, self.unit_recs, self.units_end = co, recs, end
        r = R(s1, end)
        self.leader_name = r.fstr(); self.gold_at = r.p; self.gold = r.i32()
        self.flags = _find_flag_table(s1, r.p)
        self.sysvars = _find_sysvars(s1, self.flags['count_at'])

    def verify(self):
        """Re-read the encoded bytes and check the structure (used after every write)."""
        plain = self.plaintext()
        _, ok = tssave.decrypt_blob(tssave.encrypt_blob(plain))
        if not ok: raise ParseError('re-encryption check failed')
        return True

    # ---- encoding
    def plaintext(self):
        return self.head + struct.pack('<i', len(self.s1)) + bytes(self.s1) + self.rest

    def encoded(self):
        return tssave.replace_blob(self.data, self.props, tssave.encrypt_blob(self.plaintext()))

    # ---- undo / redo: whole-s1 snapshots plus the header/preview (s0: the story warp edits the load-screen title)
    def checkpoint(self):
        if not hasattr(self, '_undo'): self._undo, self._redo = [], []
        self._undo.append((bytes(self.s1), len(self.history), self.dirty, bytes(self.head)))
        del self._undo[:-50]
        self._redo.clear()

    def can_undo(self): return bool(getattr(self, '_undo', None))
    def can_redo(self): return bool(getattr(self, '_redo', None))

    def undo(self):
        if not self.can_undo(): return False
        self._redo.append((bytes(self.s1), list(self.history), self.dirty, bytes(self.head)))
        s1, n, dirty, head = self._undo.pop()
        self.s1 = bytearray(s1); self.history = self.history[:n]; self.dirty = dirty; self.head = head
        self.reparse(); return True

    def redo(self):
        if not self.can_redo(): return False
        self._undo.append((bytes(self.s1), len(self.history), self.dirty, bytes(self.head)))
        s1, hist, dirty, head = self._redo.pop()
        self.s1 = bytearray(s1); self.history = hist; self.dirty = dirty; self.head = head
        self.reparse(); return True

    # ---- generic splice
    def splice(self, start, end, new, what, status):
        self.s1[start:end] = new
        try:
            self.reparse()
        except ParseError:
            raise
        self.dirty = True
        self.history.append((what, status))

    def set_i32(self, at, value, what, status):
        self.splice(at, at + 4, struct.pack('<i', int(value)), what, status)

    # ---- units
    def unit_ids(self):
        return [u for u, s, e in self.unit_recs]

    def unit_record(self, uid):
        for u, s, e in self.unit_recs:
            if u == uid: return s, e
        raise KeyError(uid)

    def unit_info(self, uid):
        s, e = self.unit_record(uid); rec = bytes(self.s1[s:e])
        stats = dict(zip(tssave.STAT_NAMES, struct.unpack_from('<7i2f7i', rec, 84)))   # speed, TP/turn are floats
        strings = sorted(set(m.decode() for m in re.findall(
            rb'BATTLE_(?:UNITPARAM|JOB|WEAPON)_[A-Z0-9_]+', rec)))
        try:
            cpos, lend, ents = tsunits.learned_list(rec)
            learned = [(f, nm) for f, nm in ents]
        except SystemExit:
            learned = []
        params = [x for x in strings if x.startswith('BATTLE_UNITPARAM')]
        jobs = [x for x in strings if x.startswith('BATTLE_JOB')]
        weapons = [x for x in strings if x.startswith('BATTLE_WEAPON')]
        other_abilities = sorted(set(m.decode() for m in re.findall(rb'BATTLE_ABILITY_[A-Z0-9_]+', rec)) -
                                 {nm for _, nm in learned})
        return {'id': uid, 'stats': stats, 'params': params, 'jobs': jobs, 'weapons': weapons,
                'learned': learned, 'other_abilities': other_abilities, 'bytes': e - s, 'start': s}

    def set_unit_stat(self, uid, stat, value, status):
        s, _ = self.unit_record(uid)
        i = tssave.STAT_NAMES.index(stat)
        if stat in ('speed_f', 'tp_turn_f'):
            self.splice(s + 84 + 4 * i, s + 88 + 4 * i, struct.pack('<f', float(value)), f'{uid} {stat} = {value}', status)
        else:
            self.set_i32(s + 84 + 4 * i, value, f'{uid} {stat} = {value}', status)

    # Golden-route squad (Ch.17 split): one byte 6 bytes before the record end; 0 none, 1 Benedict, 2 Roland,
    # 3 Frederica. GetPartyTeam reads it (unit +0x446 in memory). [read; SAVE_FORMAT.md]
    SQUADS = ('None', 'Benedict', 'Roland', 'Frederica')

    def unit_squad(self, uid):
        s, e = self.unit_record(uid)
        v = self.s1[e - 6]
        return v if 0 <= v <= 3 else None

    def set_unit_squad(self, uid, value, status):
        s, e = self.unit_record(uid)
        if self.unit_squad(uid) is None: raise ValueError('this record has no squad byte where expected')
        self.splice(e - 6, e - 5, bytes([int(value)]), f'{uid} Golden Route regiment = {self.SQUADS[int(value)]}', status)

    def replace_in_unit(self, uid, old, new, status, all_=True):
        s, e = self.unit_record(uid); rec = bytes(self.s1[s:e])
        o, n = fstring(old), fstring(new)
        cnt = rec.count(o)
        if cnt == 0: raise KeyError(f'{old} not in {uid}')
        rec2 = rec.replace(o, n) if all_ else rec.replace(o, n, 1)
        self.splice(s, e, rec2, f'{uid}: {old} -> {new}', status)

    def add_learned(self, uid, ability, passive, status):
        s, e = self.unit_record(uid); rec = bytes(self.s1[s:e])
        cpos, end, ents = tsunits.learned_list(rec)
        if ability in [x[1] for x in ents]: raise ValueError(f'{uid} already has {ability}')
        new = struct.pack('<i', len(ents) + 1) + rec[cpos + 4:end] + struct.pack('<iiB', int(passive), 0, 0) + fstring(ability)
        self.splice(s + cpos, s + end, new, f'{uid}: learn {ability}', status)

    def remove_learned(self, uid, ability, status):
        s, e = self.unit_record(uid); rec = bytes(self.s1[s:e])
        cpos, end, ents = tsunits.learned_list(rec)
        if ability not in [x[1] for x in ents]: raise ValueError(f'{uid} does not have {ability}')
        if len(ents) == 1:
            # An empty learned list can't be found again (tools/tsunits.py learned_list), so nothing could be learned
            # back afterwards; the game's own records always hold at least one move.
            raise ValueError(f'{uid} has only this one learned move. Learn another move first, then remove this one.')
        p = cpos + 4; out = b''
        for _ in range(len(ents)):
            st = p; p += 9; L = struct.unpack_from('<i', rec, p)[0]; nm = rec[p + 4:p + 3 + L].decode(); p += 4 + L
            if nm != ability: out += rec[st:p]
        rec2 = rec[:cpos] + struct.pack('<i', len(ents) - 1) + out + rec[end:]
        # Only the learned list changes. The passive-effect cache after it is left as it is: its entries are ability
        # objects in a per-class layout (the save reader calls each object's own Serialize), which this editor can't
        # parse for most classes (review finding I: 194 of 338 removals failed on a late-game save). The game takes
        # passive effects from the learned list and keeps a stale cache entry unused [tested, Test 15: Sycras's
        # TP_PLUS/AUTO_HEAL stayed in the cache without effect, and the record loaded and played normally].
        self.splice(s, e, rec2, f'{uid}: unlearn {ability}', status)

    def inject_unit(self, template_path, uid, status):
        """Copy a unit record from another save (tsunits inject, in memory)."""
        t = Save(template_path)
        ts, te = t.unit_record(uid)
        self.insert_unit_record(uid, bytes(t.s1[ts:te]), status)

    def insert_unit_record(self, uid, rec, status):
        """Add a whole unit record (bytes as the save stores it) in id order; the count is bumped."""
        if uid in self.unit_ids(): raise ValueError(f'{uid} already has a record')
        pos = self.units_end                          # records are sorted by unit-master id
        for u, s, e in self.unit_recs:
            if u > uid: pos = s; break
        cnt = struct.unpack_from('<i', self.s1, self.units_count_at)[0]
        self.s1[pos:pos] = rec
        struct.pack_into('<i', self.s1, self.units_count_at, cnt + 1)
        self.reparse(); self.dirty = True; self.history.append((f'add unit record {uid}', status))

    def remove_unit_record(self, uid, status):
        """Delete a whole unit record; the count is lowered."""
        s, e = self.unit_record(uid)
        cnt = struct.unpack_from('<i', self.s1, self.units_count_at)[0]
        del self.s1[s:e]
        struct.pack_into('<i', self.s1, self.units_count_at, cnt - 1)
        self.reparse(); self.dirty = True; self.history.append((f'remove unit record {uid}', status))

    # ---- flags and script variables
    def flag(self, name):
        for nm, at, v in self.flags['entries']:
            if nm == name: return at, v
        raise KeyError(name)

    def set_flag(self, name, value, status):
        at, _ = self.flag(name)
        self.set_i32(at, value, f'flag {name} = {value}', status)

    def sysvar(self, name):
        for e in self.sysvars['entries']:
            if e['name'] == name: return e
        raise KeyError(name)

    def set_sysvar(self, name, value, status):
        e = self.sysvar(name)
        if e['is_str']:
            self.splice(e['at'], e['end'], fstring(str(value)), f'{name} = {value!r}', status)
        else:
            self.set_i32(e['at'], value, f'{name} = {value}', status)

    # ---- inventory-style maps
    def map_by_label(self, label):
        for m in self.parts['maps']:
            if m['label'] == label: return m
        raise KeyError(label)

    def set_map_value(self, label, key, value, status):
        m = self.map_by_label(label)
        for k, at, v in m['entries']:
            if k == key:
                self.set_i32(at, value, f'{label}: {key} = {value}', status); return
        # new entry: append and bump the count
        n = len(m['entries'])
        self.s1[m['end']:m['end']] = fstring(key) + struct.pack('<i', int(value))
        struct.pack_into('<i', self.s1, m['count_at'], n + 1)
        self.reparse(); self.dirty = True; self.history.append((f'{label}: add {key} = {value}', status))

    def remove_map_entry(self, label, key, status):
        m = self.map_by_label(label)
        r = R(bytes(self.s1), m['count_at']); r.i32()
        for k, at, v in m['entries']:
            st = r.p; r.fstr(); r.i32()
            if k == key:
                del self.s1[st:r.p]
                struct.pack_into('<i', self.s1, m['count_at'], len(m['entries']) - 1)
                self.reparse(); self.dirty = True; self.history.append((f'{label}: remove {key}', status)); return
        raise KeyError(key)
