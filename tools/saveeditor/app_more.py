"""Extra tabs and unit actions for the save editor (mixed into app.App).

Shop stock, Quietus orders, Compare, story flags grouped by chapter, and the unit actions: learn everything the unit
qualifies for, promote / demote, export / import a unit, add the TSMod recruits a save lacks.
"""
import os, re
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

from saveeditor import model, checks, story, features as F, recruit_tools as R
from saveeditor.checks import SAFE, RISKY, DANGER

APP = 'TSMod Save Editor'
DOT = '●'
LABELS = {SAFE: 'Safe', RISKY: 'Risky', DANGER: 'Dangerous'}


class MoreTabs:
    # ------------------------------------------------------------------------------------------ building
    def _unit_actions(self, parent):
        b = ttk.Frame(parent); b.pack(fill='x', pady=(2, 0))
        ttk.Button(b, text='Add TSMod recruits…', command=self.add_recruits).pack(fill='x')
        b2 = ttk.Frame(parent); b2.pack(fill='x', pady=(4, 0))
        ttk.Button(b2, text='Export unit…', command=self.export_unit).pack(side='left', fill='x', expand=True)
        ttk.Button(b2, text='Import unit…', command=self.import_unit).pack(side='left', fill='x', expand=True, padx=(4, 0))

    def _unit_class_actions(self, parent, row):
        f = ttk.Frame(parent); f.grid(row=row, column=0, columnspan=6, sticky='w', pady=(2, 0))
        ttk.Button(f, text='Learn all qualifying moves', command=self.learn_all).pack(side='left')
        ttk.Button(f, text='Promote…', command=self.promote).pack(side='left', padx=4)
        ttk.Button(f, text='Demote', command=self.demote).pack(side='left')

    def _shop(self):
        f = self.tabs['Shop']
        ttk.Label(f, text='Shop and quartermaster stock. Double-click a row to set its stock; sold-out items become '
                          'buyable again when restocked.').pack(anchor='w')
        q = ttk.Frame(f); q.pack(fill='x', pady=4)
        ttk.Label(q, text='Search').pack(side='left')
        self.shop_q = tk.StringVar(); e = ttk.Entry(q, textvariable=self.shop_q, width=30); e.pack(side='left', padx=6)
        e.bind('<KeyRelease>', lambda ev: self.show_shop())
        self.shop_zero = tk.BooleanVar(); ttk.Checkbutton(q, text='sold out only', variable=self.shop_zero, command=self.show_shop).pack(side='left')
        ttk.Button(q, text='Restock all sold-out…', command=self.restock_all).pack(side='right')
        fr, self.shop_tv = self._tree(f, ('', 'Item', 'Id', 'Stock', 'Status'), (24, 280, 360, 70, 120), height=22)
        fr.pack(fill='both', expand=True)
        self.shop_tv.bind('<Double-1>', lambda e: self.edit_stock())

    def _orders(self):
        f = self.tabs['Quietus']
        ttk.Label(f, text="Quietus orders the save knows about. Double-click to add or toggle one. Changes are Risky: "
                          "they're normally earned through the story.").pack(anchor='w')
        fr, self.ord_tv = self._tree(f, ('', 'Quietus', 'Id', 'In save', 'Value', 'Flag'), (24, 260, 330, 70, 60, 60), height=22)
        fr.pack(fill='both', expand=True, pady=6)
        self.ord_tv.bind('<Double-1>', lambda e: self.edit_order())

    def _compare(self):
        f = self.tabs['Compare']
        top = ttk.Frame(f); top.pack(fill='x')
        ttk.Label(top, text='Compare the open save (A) with:').pack(side='left')
        ttk.Button(top, text='Another slot…', command=lambda: self.compare_with('slot')).pack(side='left', padx=4)
        ttk.Button(top, text='A backup…', command=lambda: self.compare_with('backup')).pack(side='left')
        ttk.Button(top, text='A file…', command=lambda: self.compare_with('file')).pack(side='left', padx=4)
        self.cmp_lbl = ttk.Label(f, text='', style='Small.TLabel'); self.cmp_lbl.pack(anchor='w', pady=4)
        q = ttk.Frame(f); q.pack(fill='x')
        ttk.Label(q, text='Filter').pack(side='left')
        self.cmp_q = tk.StringVar(); e = ttk.Entry(q, textvariable=self.cmp_q, width=30); e.pack(side='left', padx=6)
        e.bind('<KeyRelease>', lambda ev: self.show_compare())
        fr, self.cmp_tv = self._tree(f, ('Area', 'Item', 'A (open save)', 'B'), (150, 360, 260, 260), height=22)
        fr.pack(fill='both', expand=True, pady=4)
        self.cmp_rows = []

    # ------------------------------------------------------------------------------------------ units
    def learn_all(self):
        uid = self.unit_sel
        if not uid or not self.T: return
        todo = F.learn_qualified(self.save, self.T, uid)
        if not todo: messagebox.showinfo(APP, 'This unit already knows every move its classes grant at its level.'); return
        names = ', '.join(self.T.name_of(a) for _, a, _ in todo)
        n = len(self.save.unit_info(uid)['learned']) + len(todo)
        st, m = (RISKY, f'{n} learned moves: the game shows only the first {checks.SHOWN_LEARNED}') if n > checks.SHOWN_LEARNED else (SAFE, '')
        if not messagebox.askyesno(APP, f'Learn {len(todo)} move(s): {names}?'): return
        self.edit(st, m, lambda: F.learn_all(self.save, self.T, uid, st))

    def promote(self):
        uid = self.unit_sel
        if not uid or not self.T: return
        info = self.save.unit_info(uid); job = info['jobs'][0] if info['jobs'] else None
        opts = F.promote_targets(self.T, job)
        if not opts: messagebox.showinfo(APP, 'This class has no promotion.'); return
        pick = 0 if len(opts) == 1 else self.pick('Promote to which class?', [self.labelled(o) for o in opts])
        if pick is None: return
        self.change_class(uid, job, opts[pick])

    def demote(self):
        uid = self.unit_sel
        if not uid or not self.T: return
        info = self.save.unit_info(uid); job = info['jobs'][0] if info['jobs'] else None
        prev = F.demote_target(self.T, job)
        if not prev: messagebox.showinfo(APP, 'This is already the first class.'); return
        self.change_class(uid, job, prev)

    def change_class(self, uid, old, new):
        st, m = checks.class_status(self.T, uid, new)
        if not messagebox.askyesno(APP, f'Change class to {self.T.name_of(new)}?\nAfterwards you can use "Learn all '
                                        f'qualifying moves" for the moves this class grants.'): return
        self.edit(st, m, lambda: self.save.replace_in_unit(uid, old, new, st))

    def export_unit(self):
        uid = self.unit_sel
        if not uid: return
        name = self.T.name_of(uid) if self.T else uid
        p = filedialog.asksaveasfilename(defaultextension='.tsunit.json', initialfile=f'{name}.tsunit.json',
                                         filetypes=[('TSMod unit', '*.tsunit.json'), ('JSON', '*.json')])
        if p:
            F.export_unit(self.save, self.T, uid, p)
            messagebox.showinfo(APP, f'{name} exported.')

    def import_unit(self):
        if not self.save: return
        p = filedialog.askopenfilename(filetypes=[('TSMod unit', '*.tsunit.json'), ('JSON', '*.json')])
        if not p: return
        try: d = F.read_unit_file(p)
        except Exception as e: messagebox.showerror(APP, str(e)); return
        exists = d['unit'] in self.save.unit_ids()
        msg = (f"Replace {d.get('name')} in this save with the imported copy?" if exists else f"Add {d.get('name')} to this save?")
        if not messagebox.askyesno(APP, msg): return
        if self.T:
            st, why = checks.record_status(self.T, d['unit'], bytes.fromhex(d['record']))
        else:
            st, why = DANGER, 'the game tables are not loaded yet, so the record could not be checked'
        if d.get('save_version') not in (None, self.save.version):
            st, why = DANGER, f"the unit was exported from a save of format {d.get('save_version')}, this one is {self.save.version}"
        self.edit(st, f'importing a unit record: {why}', lambda: F.import_unit(self.save, d, st))

    def add_recruits(self):
        if not self.save or not self.T: return
        if not self.T.mod_paks: messagebox.showinfo(APP, 'No TSMod pak is installed, so there are no recruits to add.'); return
        plan = F.recruit_plan(self.save, self.T)
        if not plan: messagebox.showinfo(APP, 'This save already has every TSMod recruit.'); return
        names = '\n'.join(f'  {p[1]}  ({self.T.name_of(p[2])}, {self.T.name_of(p[3])})' for p in plan)
        if not messagebox.askyesno(APP, f'Add {len(plan)} recruit(s) to this save?\n\n{names}\n\n'
                                        'Your save folder is backed up first. In game, they join your party at the next '
                                        'story scene or world-map visit (once Anna has joined, after the Chapter 1 battle), '
                                        'at the level the game gives its own late joiners. Keep the TSMod pak installed '
                                        'while you play this save.'):
            return
        def go():
            for p in plan: F.add_recruit(self.save, self.T, p[0], RISKY)
        self.edit(RISKY, 'adds unit records', go)

    # ------------------------------------------------------------------------------------------ recruit records
    # Remove / back up / restore / scrub (recruit_tools; mods/recruit_records_proposal.md). Remove, restore and scrub
    # edit the open save in memory like every other edit (Write to slot writes it, after a full backup); back up
    # writes .tsrecruit files only.
    def _recruit_checklist(self, title, intro, uids, preselect=True, extra=None):
        """A modal checklist of recruits (names, level, class). Returns (picked ids, extra checkbox value) or None."""
        win = tk.Toplevel(self.root); win.title(title); win.transient(self.root); win.grab_set()
        body = ttk.Frame(win, padding=10); body.pack(fill='both', expand=True)
        ttk.Label(body, text=intro, wraplength=560, justify='left').pack(anchor='w')
        lb = tk.Listbox(body, selectmode='multiple', height=min(20, max(4, len(uids))), width=70, exportselection=False)
        for u in uids:
            try:
                name, lv, job = R._describe(self.save, self.T, u); lb.insert('end', f'{name}   Lv {lv}   {job}')
            except Exception:
                lb.insert('end', u)
        if preselect: lb.select_set(0, 'end')
        lb.pack(fill='both', expand=True, pady=6)
        bb = ttk.Frame(body); bb.pack(fill='x')
        ttk.Button(bb, text='All', command=lambda: lb.select_set(0, 'end')).pack(side='left')
        ttk.Button(bb, text='None', command=lambda: lb.select_clear(0, 'end')).pack(side='left', padx=4)
        xv = tk.BooleanVar(value=True)
        if extra: ttk.Checkbutton(body, text=extra, variable=xv).pack(anchor='w', pady=(6, 0))
        res = {}
        def ok(): res['v'] = ([uids[i] for i in lb.curselection()], xv.get()); win.destroy()
        fb = ttk.Frame(body); fb.pack(fill='x', pady=(8, 0))
        ttk.Button(fb, text='OK', command=ok).pack(side='right')
        ttk.Button(fb, text='Cancel', command=win.destroy).pack(side='right', padx=6)
        self.root.wait_window(win)
        return res.get('v')

    def export_crash_logs(self):
        """Pick crashes (newest ticked), optionally the crash dumps, and write one zip (crashlogs.py). Needs no save."""
        from saveeditor import crashlogs as CL, safety as S
        crashes = CL.list_crashes()
        if not crashes:
            messagebox.showinfo(APP, 'No crash reports found.\n\nThe game keeps them in '
                                     'Documents\\My Games\\TRIANGLE_STRATEGY\\Steam\\Crashes.'); return
        win = tk.Toplevel(self.root); win.title('Export crash logs'); win.transient(self.root); win.grab_set()
        body = ttk.Frame(win, padding=10); body.pack(fill='both', expand=True)
        ttk.Label(body, wraplength=620, justify='left', text=(
            'Pick the crashes to include (newest first). The zip also gets the TSMod log and a short info file (TSMod '
            'pak hash, editor version, game build). Machine, login and account ids and your Windows user name are '
            'removed from the text files. Nothing is sent: you attach the zip to your report yourself.')).pack(anchor='w')
        lb = tk.Listbox(body, selectmode='multiple', height=min(14, len(crashes)), width=100, exportselection=False)
        for c in crashes:
            lb.insert('end', f'{c["time"]:%Y-%m-%d %H:%M}   {c["error"] or c["frame"]}'[:120])
        lb.select_set(0); lb.pack(fill='both', expand=True, pady=6)
        bb = ttk.Frame(body); bb.pack(fill='x')
        ttk.Button(bb, text='All', command=lambda: lb.select_set(0, 'end')).pack(side='left')
        ttk.Button(bb, text='None', command=lambda: lb.select_clear(0, 'end')).pack(side='left', padx=4)
        dumps = tk.BooleanVar(value=True)
        ttk.Checkbutton(body, variable=dumps, text='Include the crash dumps (UE4Minidump.dmp, about 0.3 MB each). They '
                        'help find the cause, but hold a snapshot of the game\'s memory and can\'t be cleaned.'
                        ).pack(anchor='w', pady=(6, 0))
        res = {}
        def ok():
            res['v'] = [crashes[i] for i in lb.curselection()]; win.destroy()
        fb = ttk.Frame(body); fb.pack(fill='x', pady=(8, 0))
        ttk.Button(fb, text='Export…', command=ok).pack(side='right')
        ttk.Button(fb, text='Cancel', command=win.destroy).pack(side='right', padx=6)
        self.root.wait_window(win)
        picked = res.get('v')
        if not picked: return
        out = filedialog.asksaveasfilename(title='Save the crash report', defaultextension='.zip',
                                           filetypes=[('Zip file', '*.zip')],
                                           initialfile=f'TSMod_crash_report_{picked[0]["time"]:%Y%m%d-%H%M}.zip',
                                           initialdir=os.path.join(os.path.expanduser('~'), 'Desktop'))
        if not out: return
        try:
            paks = os.environ.get('TSMOD_EDITOR_PAKS') or S.find_paks_dir()
            names = CL.export(picked, out, include_dumps=dumps.get(), paks_dir=paks)
        except Exception as e:
            messagebox.showerror(APP, f'Could not write the zip:\n{e}'); return
        logs = [n for n in names if n.startswith('TSMod_log')]
        messagebox.showinfo(APP, f'Wrote {out}\n\n{len(picked)} crash(es){", with dumps" if dumps.get() else ""}; '
                                 f'TSMod log: {"included" if logs else "not found"}.')

    def _recruit_folder(self):
        d = os.path.join(os.path.dirname(self.safety.backup_dir), 'recruit_backups'); os.makedirs(d, exist_ok=True)
        return d

    def _refused(self):
        why = R.refuse_reason(self.save)
        if why: messagebox.showinfo(APP, why)
        return bool(why)

    def backup_recruits(self):
        if not self.save: return
        have = R.in_save(self.save)
        if not have: messagebox.showinfo(APP, 'This save has no TSMod recruits.'); return
        r = self._recruit_checklist('Back up recruit data', 'Each picked character is saved as its own file '
                                    '(.tsrecruit): level, class, moves, weapon and tree purchases, equipped accessories. '
                                    'Restore puts them back into this or another save.', have)
        if not r or not r[0]: return
        folder = filedialog.askdirectory(title='Folder for the backups', initialdir=self._recruit_folder()) or ''
        if not folder: return
        paths = R.backup(self.save, self.T, r[0], folder, source=os.path.basename(self.path or ''))
        messagebox.showinfo(APP, f'{len(paths)} file(s) written to {folder}.')

    def remove_recruits(self):
        if not self.save or self._refused(): return
        have = R.in_save(self.save)
        if not have: messagebox.showinfo(APP, 'This save has no TSMod recruits.'); return
        r = self._recruit_checklist('Remove TSMod recruits', 'The picked characters are removed from this save (their '
                                    'records). Equipped accessories stay in your inventory, unequipped. Other TSMod settings '
                                    'stay; use Scrub TSMod data to remove everything. Nothing is written until Write to slot.',
                                    have, extra='Back up the picked characters first (recommended)')
        if not r or not r[0]: return
        uids, do_backup = r
        if do_backup:
            paths = R.backup(self.save, self.T, uids, self._recruit_folder(), source=os.path.basename(self.path or ''))
            messagebox.showinfo(APP, f'Backed up {len(paths)} character(s) to {self._recruit_folder()}.')
        self.edit(RISKY, f'remove {len(uids)} TSMod recruit(s)', lambda: R.remove(self.save, uids, RISKY))

    def restore_recruits(self):
        if not self.save or self._refused(): return
        files = filedialog.askopenfilenames(title='Recruit backups to restore', initialdir=self._recruit_folder(),
                                            filetypes=[('TSMod recruit backup', '*.tsrecruit')])
        if not files: return
        items, worst = [], SAFE
        for p in files:
            try:
                d = R.read_backup(p)
            except Exception as e:
                messagebox.showerror(APP, f'{os.path.basename(p)}: {e}'); return
            st, msg = R.restore_check(self.save, self.T, d)
            worst = checks.worst([worst, st])
            items.append((d, f"{d['name']}  Lv {d['level']}  {d['class']}  (from {d['source'] or '?'}, {d['date']}): {msg}"))
        lines = '\n'.join('  ' + t for _, t in items)
        if not messagebox.askyesno(APP, f'Restore {len(items)} character(s)?\n\n{lines}\n\nWorst rating: {LABELS[worst]}. '
                                        'An equipped accessory comes with its character (added to the inventory if this '
                                        'save owns fewer). Nothing is written until Write to slot.',
                                   icon='warning' if worst != SAFE else 'question'):
            return
        notes = []
        def go():
            for d, _ in items: notes.extend(R.restore(self.save, d, worst))
        if self.edit(worst, f'restore {len(items)} recruit record(s)', go) and notes:
            messagebox.showinfo(APP, 'Restored. Inventory adjusted:\n' + '\n'.join(notes))

    def scrub_tsmod(self):
        if not self.save or self._refused(): return
        have = R.in_save(self.save)
        if not messagebox.askyesno(APP, f'Scrub TSMod data from this save?\n\nRemoves all {len(have)} TSMod recruit(s) and '
                                        'every other TSMod setting the save holds (the fast Chapter 1 switch), then checks '
                                        'the save against the vanilla game data only.\n\nThe recruits are backed up first '
                                        f'(to {self._recruit_folder()}). Nothing is written until Write to slot.',
                                   icon='warning'):
            return
        if have: R.backup(self.save, self.T, have, self._recruit_folder(), source=os.path.basename(self.path or ''))
        res = {}
        if not self.edit(RISKY, 'scrub TSMod data', lambda: res.update(R.scrub(self.save, self.T, RISKY))): return
        left = res.get('leftovers')
        verdict = ('Vanilla-friendly: no id the vanilla game lacks is left.' if left == [] else
                   'Could not check against the vanilla data (game tables not loaded).' if left is None else
                   f'Still in the save ({len(left)}): {", ".join(left[:8])}{" …" if len(left) > 8 else ""}')
        messagebox.showinfo(APP, f"Removed {len(res.get('removed', []))} recruit(s); cleared {', '.join(res.get('flags_cleared') or []) or 'no other settings'}.\n\n{verdict}\n\n"
                                 'Write to slot to save it. To play it without TSMod, also remove TSMod_P.pak from the game.')

    # ------------------------------------------------------------------------------------------ shop
    def show_shop(self):
        self.shop_tv.delete(*self.shop_tv.get_children())
        if not self.save: return
        q = self.shop_q.get().strip().lower(); T = self.T
        for sid, at, stock, tail in F.shop(self.save):
            name = T.name_of(sid) if T else sid
            if q and q not in name.lower() and q not in sid.lower(): continue
            if self.shop_zero.get() and stock: continue
            state = 'sold out' if stock == 0 else 'in stock'
            s = SAFE if 0 <= stock <= 99 else RISKY
            self.shop_tv.insert('', 'end', iid=str(at), values=(DOT, name, sid, stock, state), tags=(s,))

    def edit_stock(self):
        sel = self.shop_tv.selection()
        if not sel: return
        at = int(sel[0]); vals = self.shop_tv.item(sel[0], 'values')
        new = simpledialog.askstring(APP, f'Stock for {vals[1]}', initialvalue=vals[3], parent=self.root)
        if new is None: return
        v = self.num(new); st, m = checks.count_status(v)
        self.edit(st, m, lambda: F.set_stock(self.save, at, v, st))

    def restock_all(self):
        if not self.save: return
        rows = [r for r in F.shop(self.save) if r[2] == 0]
        if not rows: messagebox.showinfo(APP, 'Nothing is sold out.'); return
        n = simpledialog.askinteger(APP, f'Restock {len(rows)} sold-out item(s) to how many each?', initialvalue=5,
                                    minvalue=1, maxvalue=99, parent=self.root)
        if not n: return
        def go():
            for sid, at, stock, tail in rows: F.set_stock(self.save, at, n, SAFE)
        self.edit(SAFE, '', go)

    # ------------------------------------------------------------------------------------------ Quietus
    def show_orders(self):
        self.ord_tv.delete(*self.ord_tv.get_children())
        if not self.save: return
        have = {k: (v, f) for k, _, v, _, f in self.save.parts['orders']}
        ids = list(have)
        if self.T: ids += [o for o in self.T.rows.get('GOP_Battle_Order', {}) if o not in have]
        for o in ids:
            v, f = have.get(o, ('', ''))
            s = SAFE if o in have else RISKY
            self.ord_tv.insert('', 'end', iid=o, values=(DOT, self.T.name_of(o) if self.T else o, o,
                                                         'yes' if o in have else 'no', v, f), tags=(s,))

    def edit_order(self):
        sel = self.ord_tv.selection()
        if not sel: return
        o = sel[0]; have = {k: (v, f) for k, _, v, _, f in self.save.parts['orders']}
        if o not in have:
            if not messagebox.askyesno(APP, f'Add {self.ord_tv.item(o, "values")[1]} to this save?'): return
            self.edit(RISKY, 'adds a Quietus', lambda: F.set_order(self.save, o, 1, 0, RISKY)); return
        v, f = have[o]
        self.edit(RISKY, 'Quietus flag', lambda: F.set_order(self.save, o, v, 0 if f else 1, RISKY))

    # ------------------------------------------------------------------------------------------ compare
    def compare_with(self, kind):
        if not self.save: return
        path = None
        if kind == 'slot':
            d = self.dir_var.get()
            files = [fn for fn in model.SLOT_FILES if os.path.exists(os.path.join(d, fn)) and os.path.join(d, fn) != self.path]
            pick = self.pick('Compare with which slot?', [model.SLOT_FILES[f] for f in files])
            if pick is not None: path = os.path.join(d, files[pick])
        elif kind == 'backup':
            bks = self.safety.list_backups()
            pick = self.pick('Compare with which backup?', [f"{b['name']}  –  {b.get('reason', '')}" for b in bks])
            if pick is not None:
                fn = os.path.basename(self.path) if self.path else ''
                path = os.path.join(bks[pick]['path'], fn)
                if not os.path.exists(path): messagebox.showinfo(APP, f'That backup has no copy of {self.slot_name()}.'); path = None
        else:
            path = filedialog.askopenfilename(filetypes=[('Save', '*.sav')])
        if not path: return
        try:
            other = model.Save(path)
        except Exception as e:
            messagebox.showerror(APP, str(e)); return
        self.cmp_rows = F.compare(self.save, other, self.T)
        self.cmp_lbl.configure(text=f'A: {self.slot_name()} (as currently edited)    B: {self.slot_name(path)} '
                                    f'({os.path.basename(os.path.dirname(path))})    {len(self.cmp_rows)} difference(s)')
        self.show_compare()

    def show_compare(self):
        self.cmp_tv.delete(*self.cmp_tv.get_children())
        q = self.cmp_q.get().strip().lower()
        for i, (area, item, a, b) in enumerate(self.cmp_rows):
            if q and q not in f'{area} {item}'.lower(): continue
            self.cmp_tv.insert('', 'end', iid=str(i), values=(area, item, a, b))

    # ------------------------------------------------------------------------------------------ flags by chapter
    def show_flags_grouped(self):
        tv = self.flag_tv
        tv.delete(*tv.get_children())
        if not self.save: return
        q = self.flag_q.get().strip().upper(); only = self.flag_on_only.get()
        part_ch = {}
        if self.T:
            for label, groups in story.chapters(self.T):
                for key, title, items in groups: part_ch[key] = label
        groups = {}
        for nm, at, v in self.save.flags['entries']:
            if q and q not in nm: continue
            if only and not v: continue
            m = re.search(r'(MS\d+[A-Z]?_[A-Z]+\d+|UPD\d+_[A-Z]+\d+)', nm)
            ch = part_ch.get(m.group(1)) if m else None
            if not ch and m:
                n = re.match(r'MS(\d+)', m.group(1)); ch = f'Chapter {int(n.group(1))}' if n else 'Other'
            groups.setdefault(ch or 'Not tied to a chapter', []).append((nm, v))
        def order(k):
            m = re.match(r'Chapter (\d+)', k)
            return (0, int(m.group(1))) if m else (1, k)
        for g in sorted(groups, key=order):
            items = groups[g]
            on = sum(1 for _, v in items if v)
            p = tv.insert('', 'end', iid='g:' + g, text=f'{g}   ({on}/{len(items)} set)', open=bool(q))
            for nm, v in items:
                tv.insert(p, 'end', iid=nm, text=nm, values=(v,), tags=(SAFE if v in (0, 1) else DANGER,))


    # ------------------------------------------------------------------------------------------ weapon tree (Units)
    def _unit_tree_panel(self, parent, row):
        ttk.Label(parent, text="Weapon tree: bought nodes (buy new ones in the game; un-buying refunds nothing)",
                  style='Small.TLabel').grid(row=row, column=0, columnspan=6, sticky='w', pady=(6, 0))
        f = ttk.Frame(parent); f.grid(row=row + 1, column=0, columnspan=6, sticky='we')
        fr, self.node_tv = self._tree(f, ('Node', 'Id'), (240, 380), height=4)
        fr.pack(side='left', fill='x', expand=True)
        ttk.Button(f, text='Un-buy', command=self.unbuy).pack(side='left', padx=6, anchor='n')

    def show_unit_tree(self, uid):
        self.node_tv.delete(*self.node_tv.get_children())
        wn = F.weapon_nodes(self.save, uid)
        if wn is None:
            self.node_tv.insert('', 'end', iid='?', values=('(could not read this weapon tree)', '')); return
        for i, (nid, st, en) in enumerate(wn['objects']):
            self.node_tv.insert('', 'end', iid=f'{i}:{nid}', values=(self.T.name_of(nid) if self.T else nid, nid))

    def unbuy(self):
        uid = self.unit_sel; sel = self.node_tv.selection()
        if not uid or not sel or ':' not in sel[0]: return
        nid = sel[0].split(':', 1)[1]
        name = self.T.name_of(nid) if self.T else nid
        st, msg = RISKY, 'un-buying a node does not refund its cost'
        info = self.save.unit_info(uid)
        r = self.T.row('GOP_Battle_Ability', nid) if self.T else None
        if r and r.get('bIsWeaponAbility'):
            st, msg = DANGER, 'this is the weapon skill: the game also registers it elsewhere in the record'
        if not messagebox.askyesno(APP, f'Un-buy {name}?'): return
        self.edit(st, msg, lambda: F.unbuy_node(self.save, uid, nid, st))

    # ------------------------------------------------------------------------------------------ Unlocks
    def _unlocks(self):
        f = self.tabs['Unlocks']
        ttk.Label(f, text='Mental mock battles (cleared on Normal / Hard) and character-story episodes. These are story '
                          'flags, so changes are Risky. Double-click a column value to toggle it.').pack(anchor='w')
        pw = ttk.Panedwindow(f, orient='horizontal'); pw.pack(fill='both', expand=True, pady=6)
        a = ttk.Frame(pw); pw.add(a, weight=3)
        fr, self.mb_tv = self._tree(a, ('Mock battle', 'Chapter', 'Normal', 'Hard'), (300, 70, 70, 70), height=24)
        fr.pack(fill='both', expand=True)
        self.mb_tv.bind('<Double-1>', self.toggle_mock)
        b = ttk.Frame(pw); pw.add(b, weight=2)
        fr, self.cs_tv = self._tree(b, ('Character story', 'Episode', 'Done'), (200, 120, 60), height=24)
        fr.pack(fill='both', expand=True)
        self.cs_tv.bind('<Double-1>', lambda e: self.toggle_story_flag(self.cs_tv))

    FAST_CH1_FLAG = 'TEST_FLAG'          # mods/fast_ch1 reads it; the game never sets or reads it [read]

    def show_tsmod_options(self):
        """Overview → TSMod options: each option's state from the save; greyed out without a save, or when the installed
        game has no TSMod pak (the option would do nothing)."""
        has_pak = bool(self.T and getattr(self.T, 'mod_paks', None))
        try:
            on = bool(self.save.flag(self.FAST_CH1_FLAG)[1]) if self.save else False
            usable = bool(self.save)
        except KeyError:
            on, usable = False, False
        self.fast_ch1.set(on)
        self.fast_ch1_cb.state(['!disabled'] if usable and (has_pak or self.T is None) else ['disabled'])
        self.opt_note.configure(text='' if has_pak or self.T is None else
                                'No TSMod pak is installed, so these options would have no effect.')

    def show_unlocks(self):
        for tv in (self.mb_tv, self.cs_tv): tv.delete(*tv.get_children())
        self.show_tsmod_options()
        if not self.save or not self.T: return
        for qid, title, ch, fn, vn, fh, vh in F.mock_battles(self.save, self.T):
            self.mb_tv.insert('', 'end', iid=qid, values=(title, ch or '', 'yes' if vn else 'no', 'yes' if vh else 'no'))
        for flag, n, ep, ex, v in F.character_stories(self.save):
            self.cs_tv.insert('', 'end', iid=flag, values=(f'Story {n:02d}', f'{ep}' + (' (extra)' if ex else ''), 'yes' if v else 'no'))

    def toggle_fast_ch1(self):
        """The fast Chapter 1 battle switch (mods/fast_ch1): the save's TEST_FLAG. Safe: the game ignores the flag; only the
        TSMod pak reads it, in the Chapter 1 battle."""
        if not self.save: return
        want = 1 if self.fast_ch1.get() else 0
        try:
            self.save.flag(self.FAST_CH1_FLAG)
        except KeyError:
            messagebox.showinfo(APP, 'This save has no TEST_FLAG entry, so the switch can\'t be stored.'); return
        if not self.edit(SAFE, f'fast Chapter 1 battle {"on" if want else "off"}',
                         lambda: self.save.set_flag(self.FAST_CH1_FLAG, want, SAFE)):
            self.fast_ch1.set(not want)

    def toggle_mock(self, event):
        row = self.mb_tv.identify_row(event.y); col = self.mb_tv.identify_column(event.x)
        if not row: return
        r = self.T.row('GOP_Quest_Info', row) or {}
        flag = r.get('ClearFlag_Hard') if col == '#4' else r.get('ClearFlag_Normal')
        try:
            _, v = self.save.flag(flag)
        except KeyError:
            messagebox.showinfo(APP, f'This battle has no {"Hard" if col == "#4" else "Normal"} clear flag in this save '
                                     f'({flag or "none"}), so there is nothing to toggle.'); return
        self.edit(RISKY, 'story flag', lambda: self.save.set_flag(flag, 0 if v else 1, RISKY))

    def toggle_story_flag(self, tv):
        sel = tv.selection()
        if not sel: return
        _, v = self.save.flag(sel[0])
        self.edit(RISKY, 'story flag', lambda: self.save.set_flag(sel[0], 0 if v else 1, RISKY))
