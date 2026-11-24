"""TSMod Save Editor: a standalone Tkinter app for TRIANGLE STRATEGY saves. 

Every value is editable. Each edit is rated Safe / Risky / Dangerous from the game's own tables (vanilla pak +
the installed TSMod pak). Writes go to the real save folder only while the game is closed, after a full-folder
backup, and are re-read and verified. Slot 1 is locked unless unlocked for one write.

Run:  .venv/Scripts/pythonw tools/saveeditor/TSModSaveEditor.pyw   (or: python -m saveeditor from tools/)
"""
import os, sys, threading, traceback, time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from saveeditor import model, checks, tables, story, safety, features   # noqa: E402
from saveeditor.app_more import MoreTabs                              # noqa: E402
from saveeditor.checks import SAFE, RISKY, DANGER                     # noqa: E402

APP = 'TSMod Save Editor'
COLORS = {SAFE: '#2e9e44', RISKY: '#d08a00', DANGER: '#d33a2c'}
LABELS = {SAFE: 'Safe', RISKY: 'Risky', DANGER: 'Dangerous'}
DOT = '●'
FAITH = ['(unused)', 'Liberty', 'Utility', 'Morality']        # EFaithType order: NONE, FREEDOM, BENEFIT, MORAL
ITEM_MAPS = [('Battle items', 'items'), ('Materials', 'materials'), ('Class medals', 'medals'),
             ('Accessories', 'accessories'), ('Notes', 'notes')]
ITEM_TABLES = {'items': ['GOP_Item_Battle'], 'materials': ['GOP_Item_UpgradeMaterial'],
               'medals': ['GOP_Item_ClassMedal'], 'accessories': ['GOP_Battle_Accessary'], 'notes': ['GOP_Note']}


def data_dir():
    d = os.environ.get('TSMOD_EDITOR_DATA') or os.path.join(HERE, 'editor_data')
    os.makedirs(d, exist_ok=True)
    return d


class App(MoreTabs):
    def __init__(self, root):
        self.root = root
        root.title(APP)
        # 1280x860 by default, shrunk to fit smaller screens (Steam Deck: 1280x800 with the desktop's panel).
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        w, h = min(1280, sw - 20), min(860, sh - 80)
        root.geometry(f'{w}x{h}+{max(0, (sw - w) // 2)}+0')
        root.minsize(min(1100, w), min(720, h))
        self.safety = safety.Safety(data_dir())
        self.T = None                       # tables (loaded in the background)
        self.save = None
        self.path = None
        self.unit_sel = None
        self._style()
        self.tips = Tips(root)
        self._build()
        self.tip_units = self.tips.tree(self.unit_tv); self.tip_learn = self.tips.tree(self.learn_tv)
        self.tip_items = self.tips.tree(self.item_tv); self.tip_iss = self.tips.tree(self.iss_tv)
        env_dir = os.environ.get('TSMOD_EDITOR_SAVEDIR')          # testing: point the editor at a copy
        self.save_dirs = [env_dir] if env_dir else safety.find_save_dirs()
        self.dir_var.set(self.save_dirs[0] if self.save_dirs else '')
        self.refresh_slots()
        self.tick()
        self._q = []
        threading.Thread(target=self._load_tables, daemon=True).start()
        self.poll_tables()

    # ------------------------------------------------------------------------------------------ layout
    def _style(self):
        st = ttk.Style()
        try: st.theme_use('vista' if os.name == 'nt' else 'clam')
        except tk.TclError: pass
        st.configure('Treeview', rowheight=22)
        st.configure('Hdr.TLabel', font=('Segoe UI', 11, 'bold'))
        st.configure('Small.TLabel', foreground='#555')

    def _build(self):
        top = ttk.Frame(self.root, padding=(8, 6)); top.pack(fill='x')
        ttk.Label(top, text='Save folder').grid(row=0, column=0, sticky='w')
        self.dir_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.dir_var, width=70).grid(row=0, column=1, sticky='we', padx=4)
        ttk.Button(top, text='Browse…', command=self.browse_dir).grid(row=0, column=2)
        ttk.Label(top, text='Slot').grid(row=1, column=0, sticky='w', pady=(4, 0))
        self.slot_var = tk.StringVar()
        self.slot_box = ttk.Combobox(top, textvariable=self.slot_var, state='readonly', width=68)
        self.slot_box.grid(row=1, column=1, sticky='we', padx=4, pady=(4, 0))
        self.slot_box.bind('<<ComboboxSelected>>', lambda e: self.open_selected(quiet=True))
        bar = ttk.Frame(top); bar.grid(row=1, column=2, columnspan=4, sticky='w', pady=(4, 0))
        ttk.Button(bar, text='Open', command=self.open_selected).pack(side='left')
        ttk.Button(bar, text='Open file…', command=self.open_file).pack(side='left', padx=4)
        self.write_btn = ttk.Button(bar, text='Write to slot', command=self.write_slot)
        self.write_btn.pack(side='left', padx=(12, 4))
        ttk.Button(bar, text='Copy to slot…', command=self.copy_to_slot).pack(side='left')
        ttk.Button(bar, text='Save copy as…', command=self.save_copy).pack(side='left', padx=4)
        ttk.Button(bar, text='Discard changes', command=self.reload).pack(side='left', padx=4)
        ttk.Button(bar, text='Undo', width=6, command=self.undo).pack(side='left', padx=(12, 0))
        ttk.Button(bar, text='Redo', width=6, command=self.redo).pack(side='left', padx=4)
        self.root.bind_all('<Control-z>', self.undo); self.root.bind_all('<Control-y>', self.redo)
        top.columnconfigure(1, weight=1)
        self.game_lbl = ttk.Label(top, text=''); self.game_lbl.grid(row=0, column=3, padx=(16, 0), sticky='w')
        self.lock_lbl = ttk.Label(top, text='', foreground=COLORS[RISKY]); self.lock_lbl.grid(row=0, column=4, padx=8, sticky='w')

        self.nb = ttk.Notebook(self.root); self.nb.pack(fill='both', expand=True, padx=8, pady=4)
        self.tabs = {}
        for name in ('Overview', 'Units', 'Items', 'Shop', 'Quietus', 'Story', 'Unlocks', 'Issues', 'Compare', 'Backups', 'Changes'):
            f = ttk.Frame(self.nb, padding=8); self.nb.add(f, text=name); self.tabs[name] = f
        self._overview(); self._units(); self._items(); self._shop(); self._orders(); self._story(); self._unlocks(); self._issues()
        self._compare(); self._backups(); self._changes()

        sb = ttk.Frame(self.root, padding=(8, 2)); sb.pack(fill='x')
        self.status = ttk.Label(sb, text='Loading game data… (the first start takes about a minute)'); self.status.pack(side='left')
        leg = ttk.Frame(sb); leg.pack(side='right')
        for s in (SAFE, RISKY, DANGER):
            tk.Label(leg, text=f'{DOT} {LABELS[s]}', fg=COLORS[s]).pack(side='left', padx=4)
        self.summary = tk.Label(sb, text='', cursor='hand2'); self.summary.pack(side='right', padx=12)
        self.summary.bind('<Button-1>', lambda e: self.nb.select(self.tabs['Issues']))

    def _tree(self, parent, cols, widths, height=12):
        fr = ttk.Frame(parent)
        tv = ttk.Treeview(fr, columns=cols, show='headings', height=height, selectmode='browse')
        for c, w in zip(cols, widths):
            tv.heading(c, text=c); tv.column(c, width=w, stretch=(w > 150))
        vs = ttk.Scrollbar(fr, orient='vertical', command=tv.yview); tv.configure(yscrollcommand=vs.set)
        tv.pack(side='left', fill='both', expand=True); vs.pack(side='right', fill='y')
        for s in (SAFE, RISKY, DANGER): tv.tag_configure(s, foreground=COLORS[s])
        return fr, tv

    def _dot(self, parent):
        lb = tk.Label(parent, text=DOT, fg='#999'); return lb

    def _set_dot(self, lb, status, msg=''):
        lb.configure(fg=COLORS.get(status, '#999'))
        lb.tip = msg
        lb.bind('<Enter>', lambda e: self.status.configure(text=f'{LABELS.get(status, "")}: {msg}' if msg else LABELS.get(status, '')))

    # ---- Overview
    def _overview(self):
        f = self.tabs['Overview']
        self.ov_info = ttk.Label(f, text='Open a slot to begin.', justify='left'); self.ov_info.grid(row=0, column=0, columnspan=4, sticky='w')
        # Mod status and the recruits button share one cell (row 0), so the separator in row 1 never crosses the button.
        rf = ttk.Frame(f); rf.grid(row=0, column=4, columnspan=2, sticky='nw', padx=(30, 0))
        self.mod_lbl = ttk.Label(rf, text=''); self.mod_lbl.pack(anchor='w')
        r1 = ttk.Frame(rf); r1.pack(anchor='w', pady=(6, 0))
        ttk.Button(r1, text='Add TSMod recruits…', command=self.add_recruits).pack(side='left')
        ttk.Button(r1, text='Remove TSMod recruits…', command=self.remove_recruits).pack(side='left', padx=4)
        ttk.Button(r1, text='Scrub TSMod data…', command=self.scrub_tsmod).pack(side='left')
        r2 = ttk.Frame(rf); r2.pack(anchor='w', pady=(4, 0))
        ttk.Button(r2, text='Back up recruit data…', command=self.backup_recruits).pack(side='left')
        ttk.Button(r2, text='Restore recruit data…', command=self.restore_recruits).pack(side='left', padx=4)
        ttk.Button(r2, text='Export crash logs…', command=self.export_crash_logs).pack(side='left')
        ttk.Separator(f).grid(row=1, column=0, columnspan=6, sticky='we', pady=8)
        # TSMod options (user design, 2026-11-23): settings the TSMod pak reads from the save.
        opt = ttk.LabelFrame(f, text='TSMod options', padding=(10, 6)); opt.grid(row=2, column=4, rowspan=7, columnspan=2,
                                                                                 sticky='nw', padx=(30, 0))
        self.fast_ch1 = tk.BooleanVar(value=False)
        self.fast_ch1_cb = ttk.Checkbutton(opt, text='Fast Chapter 1 battle', variable=self.fast_ch1,
                                           command=self.toggle_fast_ch1)
        self.fast_ch1_cb.pack(anchor='w')
        ttk.Label(opt, text='Enemies at 1 HP, won on the first defeat, no in-battle talk. Cutscenes and story unchanged.',
                  style='Small.TLabel', wraplength=330).pack(anchor='w', padx=(22, 0))
        self.opt_note = ttk.Label(opt, text='', style='Small.TLabel', foreground='gray', wraplength=350)
        self.opt_note.pack(anchor='w', pady=(6, 0))
        ttk.Label(f, text='Gold', style='Hdr.TLabel').grid(row=2, column=0, sticky='w')
        self.gold_var = tk.StringVar(); ttk.Entry(f, textvariable=self.gold_var, width=14).grid(row=2, column=1, sticky='w')
        self.gold_dot = self._dot(f); self.gold_dot.grid(row=2, column=2, sticky='w')
        ttk.Button(f, text='Apply', command=self.apply_gold).grid(row=2, column=3, sticky='w')
        ttk.Label(f, text='Scales of Conviction', style='Hdr.TLabel').grid(row=3, column=0, sticky='w', pady=(14, 2))
        ttk.Label(f, text='Raw conviction points. Votes and route conditions read them, so changes are Risky.',
                  style='Small.TLabel', wraplength=340).grid(row=4, column=0, columnspan=4, sticky='w')   # left of the options box
        self.conv_vars = []
        for i in range(1, 4):
            ttk.Label(f, text=FAITH[i]).grid(row=4 + i, column=0, sticky='w')
            v = tk.StringVar(); ttk.Entry(f, textvariable=v, width=14).grid(row=4 + i, column=1, sticky='w')
            self.conv_vars.append(v)
        ttk.Button(f, text='Apply convictions', command=self.apply_conv).grid(row=8, column=1, sticky='w', pady=4)
        ttk.Label(f, text='Script variables', style='Hdr.TLabel').grid(row=9, column=0, sticky='w', pady=(14, 2))
        fr, self.var_tv = self._tree(f, ('Variable', 'Value'), (300, 420), height=10)
        fr.grid(row=10, column=0, columnspan=6, sticky='nsew')
        self.var_tv.bind('<Double-1>', lambda e: self.edit_var())
        ttk.Label(f, text='Double-click to edit. All script variables are Risky (story and battle state).',
                  style='Small.TLabel').grid(row=11, column=0, columnspan=6, sticky='w')
        f.rowconfigure(10, weight=1); f.columnconfigure(5, weight=1)

    # ---- Units
    def _units(self):
        f = self.tabs['Units']
        left = ttk.Frame(f); left.pack(side='left', fill='y')
        fr, self.unit_tv = self._tree(left, ('', 'Unit', 'Lv', 'Class'), (24, 150, 40, 170), height=26)
        fr.pack(fill='y', expand=True)
        self.unit_tv.bind('<<TreeviewSelect>>', lambda e: self.show_unit())
        b = ttk.Frame(left); b.pack(fill='x', pady=4)
        ttk.Button(b, text='Add unit from another save…', command=self.inject_unit).pack(fill='x')
        self._unit_actions(left)
        right = ttk.Frame(f, padding=(12, 0)); right.pack(side='left', fill='both', expand=True)
        self.u_title = ttk.Label(right, text='', style='Hdr.TLabel'); self.u_title.grid(row=0, column=0, columnspan=6, sticky='w')
        self.u_vars = {}; self.u_dots = {}
        r = 1
        for i, (key, label) in enumerate((('level', 'Level'), ('exp', 'EXP'))):
            ttk.Label(right, text=label).grid(row=r, column=3 * i, sticky='w')
            v = tk.StringVar(); ttk.Entry(right, textvariable=v, width=8).grid(row=r, column=3 * i + 1, sticky='w')
            d = self._dot(right); d.grid(row=r, column=3 * i + 2, sticky='w'); self.u_vars[key] = v; self.u_dots[key] = d
        r += 1
        ttk.Label(right, text='Stats (the game recomputes these on level-up and battle entry)', style='Small.TLabel').grid(row=r, column=0, columnspan=6, sticky='w', pady=(6, 0))
        r += 1
        stat_keys = ['hp', 'tp', 'str', 'int', 'def', 'mdf', 'dex', 'agi', 'luk', 'speed_f', 'move_x100', 'jump_up']
        for i, k in enumerate(stat_keys):
            rr, cc = r + i // 3, (i % 3) * 2
            ttk.Label(right, text=k.replace('_f', '').replace('_x100', ' ×100').upper()).grid(row=rr, column=cc, sticky='w')
            v = tk.StringVar(); ttk.Entry(right, textvariable=v, width=8).grid(row=rr, column=cc + 1, sticky='w')
            self.u_vars[k] = v
        r += 4
        ttk.Button(right, text='Apply level, EXP and stats', command=self.apply_unit_stats).grid(row=r, column=0, columnspan=3, sticky='w', pady=6)
        r += 1
        ttk.Label(right, text='Class').grid(row=r, column=0, sticky='w')
        self.class_var = tk.StringVar(); self.class_box = ttk.Combobox(right, textvariable=self.class_var, width=46)
        self.class_box.grid(row=r, column=1, columnspan=3, sticky='we'); self.class_dot = self._dot(right); self.class_dot.grid(row=r, column=4)
        ttk.Button(right, text='Change', command=lambda: self.change_id('class')).grid(row=r, column=5, sticky='w')
        r += 1
        ttk.Label(right, text='Weapon').grid(row=r, column=0, sticky='w')
        self.weapon_var = tk.StringVar(); self.weapon_box = ttk.Combobox(right, textvariable=self.weapon_var, width=46)
        self.weapon_box.grid(row=r, column=1, columnspan=3, sticky='we'); self.weapon_dot = self._dot(right); self.weapon_dot.grid(row=r, column=4)
        ttk.Button(right, text='Change', command=lambda: self.change_id('weapon')).grid(row=r, column=5, sticky='w')
        r += 1
        ttk.Label(right, text='Golden Route Regiment Leader').grid(row=r, column=0, sticky='w')
        self.squad_var = tk.StringVar()
        self.squad_box = ttk.Combobox(right, textvariable=self.squad_var, width=20, state='readonly',
                                      values=list(model.Save.SQUADS))
        self.squad_box.grid(row=r, column=1, sticky='w'); self.squad_dot = self._dot(right); self.squad_dot.grid(row=r, column=4)
        ttk.Button(right, text='Change', command=self.change_squad).grid(row=r, column=5, sticky='w')
        self.tips.attach(self.squad_box, lambda: "Which general's squad this unit joins on the Golden route (Chapter 17 "
                         "split onward). For TSMod recruits the mod keeps this choice at the split; None means the mod's default.")
        r += 1
        self._unit_class_actions(right, r)
        r += 1
        ttk.Label(right, text='Learned moves (the game\'s unit screens show the first 7)',
                  style='Small.TLabel').grid(row=r, column=0, columnspan=6, sticky='w', pady=(8, 0))
        r += 1
        fr, self.learn_tv = self._tree(right, ('', 'Move', 'Id', 'Kind'), (24, 200, 300, 70), height=7)
        fr.grid(row=r, column=0, columnspan=6, sticky='nsew'); right.rowconfigure(r, weight=1)
        r += 1
        lb = ttk.Frame(right); lb.grid(row=r, column=0, columnspan=6, sticky='we', pady=4)
        self.learn_var = tk.StringVar(); self.learn_box = ttk.Combobox(lb, textvariable=self.learn_var, width=50)
        self.learn_box.pack(side='left')
        self.learn_passive = tk.BooleanVar(); ttk.Checkbutton(lb, text='passive', variable=self.learn_passive).pack(side='left', padx=4)
        ttk.Button(lb, text='Learn', command=self.learn).pack(side='left')
        ttk.Button(lb, text='Unlearn selected', command=self.unlearn).pack(side='left', padx=4)
        r += 1
        self._unit_tree_panel(right, r)
        r += 2
        self.u_other = ttk.Label(right, text='', style='Small.TLabel', wraplength=640, justify='left')
        self.u_other.grid(row=r, column=0, columnspan=6, sticky='w')

    # ---- Items
    def _items(self):
        f = self.tabs['Items']
        top = ttk.Frame(f); top.pack(fill='x')
        self.item_map = tk.StringVar(value=ITEM_MAPS[0][0])
        for lab, key in ITEM_MAPS:
            ttk.Radiobutton(top, text=lab, value=lab, variable=self.item_map, command=self.show_items).pack(side='left', padx=4)
        fr, self.item_tv = self._tree(f, ('', 'Item', 'Id', 'Count'), (24, 260, 380, 70), height=20)
        fr.pack(fill='both', expand=True, pady=6)
        self.item_tv.bind('<Double-1>', lambda e: self.edit_item())
        b = ttk.Frame(f); b.pack(fill='x')
        self.add_item_var = tk.StringVar(); self.add_item_box = ttk.Combobox(b, textvariable=self.add_item_var, width=60)
        self.add_item_box.pack(side='left')
        ttk.Label(b, text='Count').pack(side='left', padx=(8, 2))
        self.add_count = tk.StringVar(value='1'); ttk.Entry(b, textvariable=self.add_count, width=6).pack(side='left')
        ttk.Button(b, text='Add / set', command=self.add_item).pack(side='left', padx=6)
        ttk.Button(b, text='Remove selected', command=self.remove_item).pack(side='left')
        ttk.Label(f, text='Double-click a row to change its count.',
                  style='Small.TLabel').pack(anchor='w', pady=4)

    # ---- Story
    def _story(self):
        f = self.tabs['Story']
        self.story_now = ttk.Label(f, text='', style='Hdr.TLabel'); self.story_now.pack(anchor='w')
        pw = ttk.Panedwindow(f, orient='horizontal'); pw.pack(fill='both', expand=True, pady=6)
        left = ttk.Frame(pw); pw.add(left, weight=1)
        ttk.Label(left, text='Set current chapter / story position').pack(anchor='w')
        fr = ttk.Frame(left); fr.pack(fill='both', expand=True)
        self.ch_tv = ttk.Treeview(fr, columns=('idx',), show='tree headings', height=18, selectmode='browse')
        self.ch_tv.heading('#0', text='Chapter / part / story point'); self.ch_tv.heading('idx', text='#')
        self.ch_tv.column('#0', width=360); self.ch_tv.column('idx', width=50, stretch=False)
        vs = ttk.Scrollbar(fr, orient='vertical', command=self.ch_tv.yview); self.ch_tv.configure(yscrollcommand=vs.set)
        self.ch_tv.pack(side='left', fill='both', expand=True); vs.pack(side='right', fill='y')
        ttk.Button(left, text='Go to this story point', command=self.set_story).pack(anchor='w', pady=4)
        ttk.Label(left, text='Points with their own world-map marker can be picked (grey ones play on their own). '
                             'The save then resumes on the world map with that marker; flags from later in the story '
                             'are cleared, earlier ones and the party stay. Going back on this run\'s own path is Risky; '
                             'forward or onto another route is Dangerous. Try it on a spare slot first (Copy to slot…).',
                  style='Small.TLabel', wraplength=480, justify='left').pack(anchor='w')
        right = ttk.Frame(pw); pw.add(right, weight=1)
        sf = ttk.Frame(right); sf.pack(fill='x')
        ttk.Label(sf, text='Story flags').pack(side='left')
        self.flag_q = tk.StringVar(); e = ttk.Entry(sf, textvariable=self.flag_q, width=30); e.pack(side='left', padx=6)
        e.bind('<KeyRelease>', lambda ev: self.show_flags())
        self.flag_on_only = tk.BooleanVar(); ttk.Checkbutton(sf, text='set only', variable=self.flag_on_only, command=self.show_flags).pack(side='left')
        fr = ttk.Frame(right)
        self.flag_tv = ttk.Treeview(fr, columns=('Value',), show='tree headings', height=20, selectmode='browse')
        self.flag_tv.heading('#0', text='Chapter / flag'); self.flag_tv.heading('Value', text='Value')
        self.flag_tv.column('#0', width=360); self.flag_tv.column('Value', width=60, stretch=False)
        for st_ in (SAFE, RISKY, DANGER): self.flag_tv.tag_configure(st_, foreground=COLORS[st_])
        vs = ttk.Scrollbar(fr, orient='vertical', command=self.flag_tv.yview); self.flag_tv.configure(yscrollcommand=vs.set)
        self.flag_tv.pack(side='left', fill='both', expand=True); vs.pack(side='right', fill='y')
        fr.pack(fill='both', expand=True, pady=4)
        self.flag_tv.bind('<Double-1>', lambda e: self.toggle_flag())
        ttk.Label(right, text='Double-click toggles a flag (Risky).', style='Small.TLabel').pack(anchor='w')

    # ---- Issues
    def _issues(self):
        f = self.tabs['Issues']
        ttk.Label(f, text='Every check the editor runs on this save. Select a row and use Fix where one is offered.').pack(anchor='w')
        fr, self.iss_tv = self._tree(f, ('', 'Status', 'Area', 'Item', 'Details'), (24, 80, 80, 220, 640), height=22)
        fr.pack(fill='both', expand=True, pady=6)
        b = ttk.Frame(f); b.pack(fill='x')
        ttk.Button(b, text='Fix selected', command=self.fix_issue).pack(side='left')
        ttk.Button(b, text='Re-check', command=self.refresh_issues).pack(side='left', padx=6)

    # ---- Backups
    def _backups(self):
        f = self.tabs['Backups']
        ttk.Label(f, text='The whole save folder is copied here before every write and every restore. '
                          'The latest 40 are kept; pinned backups are kept forever.', wraplength=900).pack(anchor='w')
        fr, self.bk_tv = self._tree(f, ('Backup', 'Reason', 'Pinned'), (180, 600, 60), height=18)
        fr.pack(fill='both', expand=True, pady=6)
        b = ttk.Frame(f); b.pack(fill='x')
        ttk.Button(b, text='Back up now', command=self.backup_now).pack(side='left')
        ttk.Button(b, text='Restore a slot from selected…', command=self.restore).pack(side='left', padx=6)
        ttk.Button(b, text='Pin selected', command=self.pin).pack(side='left')
        ttk.Button(b, text='Open backups folder', command=lambda: safety.open_folder(self.safety.backup_dir)).pack(side='left', padx=6)

    # ---- Changes
    def _changes(self):
        f = self.tabs['Changes']
        ttk.Label(f, text='Edits made since this save was opened. Nothing is written until you choose Write to slot.').pack(anchor='w')
        fr, self.chg_tv = self._tree(f, ('', 'Status', 'Change'), (24, 80, 900), height=24)
        fr.pack(fill='both', expand=True, pady=6)

    # ------------------------------------------------------------------------------------------ background
    def _load_tables(self):
        """Worker thread: never touches Tk; results go through self._q, which the UI polls (poll_tables)."""
        try:
            paks = os.environ.get('TSMOD_EDITOR_PAKS') or safety.find_paks_dir()
            T = tables.Tables(paks, os.path.join(data_dir(), 'cache'), lambda m: self._q.append(('msg', m))).load()
            self._q.append(('done', T))
        except Exception as e:
            self._q.append(('fail', e))

    def poll_tables(self):
        while self._q:
            kind, val = self._q.pop(0)
            if kind == 'msg': self.status.configure(text=val)
            elif kind == 'fail': self.status.configure(text=f'Could not load game tables: {val}. Checks are off.')
            else:
                self.T = val
                mods = ', '.join(os.path.basename(p) for p in val.mod_paks) or 'none'
                self.status.configure(text=f'Game data loaded. Installed TSMod pak: {mods}.')
                self.fill_story_tree(); self.refresh_slots(); self.refresh_all(); return
        self.root.after(200, self.poll_tables)

    def tick(self):
        running = safety.game_running()
        self.game_lbl.configure(text=('Game: RUNNING (writes blocked)' if running else 'Game: closed'),
                                foreground=(COLORS[DANGER] if running else COLORS[SAFE]))
        self.root.after(3000, self.tick)

    # ------------------------------------------------------------------------------------------ slots
    def browse_dir(self):
        d = filedialog.askdirectory(initialdir=self.dir_var.get() or os.path.expanduser('~'))
        if d: self.dir_var.set(d); self.refresh_slots()

    SLOT_PLACEHOLDER = 'Select a save file…'

    def describe_file(self, p, label):
        """One line for a save file, as the slot list shows it: leader, level, play time, date saved, story point
        (chapter), and [locked] / [TSMod] marks. Used by the slot list and the restore list."""
        try:
            s = model.Save(p); pv = s.preview
            leader = self.T.english(pv['leader']) if self.T else pv['leader']
            desc = f"{label}:  {leader}, Lv {pv['level']},  {self.play_time(pv['play_time'])},  saved {pv['saved'][:16]}"
            try:
                desc += f",  {story.describe(s.sysvar('SCENARIO_ANCHOR')['value'], self.T)}"
            except Exception:
                pass
        except Exception as e:
            return f'{label}: (cannot read: {e})' + ('   [locked]' if self.safety.is_locked(p) else '')
        if self.safety.is_locked(p): desc += '   [locked]'
        if any(u.startswith(('UNIT_MASTER_CH_N', 'UNIT_MASTER_CH_M')) for u in s.unit_ids()): desc += '   [TSMod]'
        return desc

    def refresh_slots(self):
        """The slot list: a placeholder first (nothing is picked at start), then every save file in the folder. Called
        again once the game tables load, so leader names show in English; the current pick is kept."""
        d = self.dir_var.get(); items = [self.SLOT_PLACEHOLDER]; prev = None
        i = self.slot_box.current()
        if getattr(self, 'slot_paths', None) and 0 < i < len(self.slot_paths): prev = self.slot_paths[i]
        self.slot_paths = [None]
        if os.path.isdir(d):
            for fn, label in model.SLOT_FILES.items():
                p = os.path.join(d, fn)
                if not os.path.exists(p): continue
                items.append(self.describe_file(p, label)); self.slot_paths.append(p)
        self.slot_box['values'] = items
        self.slot_box.current(self.slot_paths.index(prev) if prev in self.slot_paths else 0)

    def confirm_discard(self):
        if self.save and self.save.dirty:
            return messagebox.askyesno(APP, 'This slot has edits that are not written yet. Discard them?')
        return True

    def open_selected(self, quiet=False):
        i = self.slot_box.current()
        if i <= 0 or not self.slot_paths[i]:
            if not quiet: messagebox.showinfo(APP, 'Pick a save file in the Slot list first.')
            return
        self.open_path(self.slot_paths[i])

    def open_file(self):
        p = filedialog.askopenfilename(filetypes=[('Triangle Strategy save', '*.sav'), ('All files', '*.*')])
        if p: self.open_path(p)

    def open_path(self, p):
        if not self.confirm_discard(): return
        try:
            self.save = model.Save(p); self.path = p
        except Exception as e:
            messagebox.showerror(APP, f'Could not open {self.slot_name(p)}:\n{e}'); return
        self.lock_lbl.configure(text=('Slot 1: LOCKED' if self.safety.is_locked(p) else ''))
        self.refresh_all()
        self.status.configure(text=f'Opened {self.slot_name(p)}: {len(self.save.unit_recs)} units.')

    def reload(self):
        if self.path and self.confirm_discard():
            self.save = None; self.open_path(self.path)

    @staticmethod
    def play_time(text):
        """'8 days, 2:49:52' -> '194 h 49 min'."""
        import re as _re
        m = _re.match(r'(?:(\d+) days?, )?(\d+):(\d+):\d+', text or '')
        if not m: return text
        h = int(m.group(1) or 0) * 24 + int(m.group(2))
        return f'{h} h {int(m.group(3))} min'

    def slot_name(self, path=None):
        path = path or self.path
        if not path: return ''
        fn = os.path.basename(path)
        return model.SLOT_FILES.get(fn, fn)

    def title(self):
        name = self.slot_name()
        self.root.title(f'{APP}  -  {name}{"  (unsaved changes)" if self.save and self.save.dirty else ""}')

    # ------------------------------------------------------------------------------------------ editing helpers
    def _squad_status(self, uid, sq):
        if sq is None: return DANGER, 'No squad byte where expected in this record.'
        if uid[15:16] in 'NM': return SAFE, 'TSMod recruit: the mod reads this at the Chapter 17 split and keeps it.'
        return RISKY, 'Vanilla unit: the split screen normally decides this; changing it after the split moves the unit between squads.'

    def change_squad(self):
        uid = getattr(self, 'unit_sel', None)
        if not uid or not self.save or self.squad_var.get() not in model.Save.SQUADS: return
        v = model.Save.SQUADS.index(self.squad_var.get())
        st, _ = self._squad_status(uid, self.save.unit_squad(uid))
        if self.edit(st, f'set the Golden Route regiment of {uid} to {self.squad_var.get()}',
                     lambda: self.save.set_unit_squad(uid, v, st)):
            self.refresh_all()

    def edit(self, status, msg, fn):
        """Run an edit after the status gate: Dangerous edits ask first."""
        if not self.save: return False
        if status == DANGER and not messagebox.askyesno(APP, f'This edit is Dangerous:\n\n{msg}\n\nApply it anyway?', icon='warning'):
            return False
        self.save.checkpoint()
        try:
            fn()
        except (Exception, SystemExit) as e:        # tsunits reports layout problems as SystemExit: roll back, stay open
            self.save.undo(); self.save._redo.clear()          # roll back anything half-applied
            messagebox.showerror(APP, f'The edit failed and nothing was changed:\n{e}')
            self.refresh_all()
            return False
        self.refresh_all()
        return True

    def undo(self, event=None):
        if self.save and self.save.undo(): self.refresh_all(); self.status.configure(text='Undone.')

    def redo(self, event=None):
        if self.save and self.save.redo(): self.refresh_all(); self.status.configure(text='Redone.')

    def num(self, s, cast=int):
        try: return cast(str(s).replace(',', '').strip())
        except ValueError: messagebox.showerror(APP, f'Not a number: {s}'); raise

    # ---- overview
    def apply_gold(self):
        v = self.num(self.gold_var.get()); st, m = checks.gold_status(v)
        self.edit(st, m, lambda: self.save.set_i32(self.save.gold_at, v, f'gold = {v:,}', st))

    def apply_conv(self):
        vals = [self.num(v.get()) for v in self.conv_vars]
        def go():
            for i, v in enumerate(vals, 1):
                at, old = self.save.parts['convictions']['a'][i]
                if v != old: self.save.set_i32(at, v, f'{FAITH[i]} = {v}', RISKY)
        self.edit(RISKY, 'convictions', go)

    def edit_var(self):
        sel = self.var_tv.selection()
        if not sel or not self.save: return
        name = self.var_tv.item(sel[0], 'values')[0]
        e = self.save.sysvar(name)
        new = simpledialog.askstring(APP, f'{name}', initialvalue=str(e['value']), parent=self.root)
        if new is None: return
        val = new if e['is_str'] else self.num(new)
        st = RISKY
        if name == 'SCENARIO_ANCHOR' and not 0 < val < len(story.anchors()): st = DANGER
        self.edit(st, f'{name} = {val}', lambda: self.save.set_sysvar(name, val, st))

    # ---- units
    def show_unit(self):
        sel = self.unit_tv.selection()
        if not sel or not self.save: return
        uid = sel[0]; self.unit_sel = uid
        info = self.save.unit_info(uid); T = self.T
        name = T.name_of(uid) if T else uid
        self.u_title.configure(text=f'{name}   ({uid})' if name != uid else uid)
        for k, v in self.u_vars.items():
            val = info['stats'].get(k, '')
            v.set(f'{val:g}' if isinstance(val, float) else str(val))
        st, m = checks.level_status(info['stats']['level']); self._set_dot(self.u_dots['level'], st, m)
        st, m = checks.exp_status(info['stats']['exp']); self._set_dot(self.u_dots['exp'], st, m)
        sq = self.save.unit_squad(uid)
        self.squad_var.set(model.Save.SQUADS[sq] if sq is not None else '')
        self._set_dot(self.squad_dot, *self._squad_status(uid, sq))
        job = info['jobs'][0] if info['jobs'] else ''
        wpn = info['weapons'][0] if info['weapons'] else ''
        self.class_var.set(self.labelled(job)); self.weapon_var.set(self.labelled(wpn))
        if T:
            classes = sorted(T.unit_classes(uid) | set(info['jobs']))
            self.class_box['values'] = [self.labelled(c) for c in classes]
            line = set()
            for w in info['weapons']: line |= T.weapon_line(w)[0]
            self.weapon_box['values'] = [self.labelled(w) for w in sorted(line)]
            s, m = checks.class_status(T, uid, job) if job else (RISKY, 'no class found'); self._set_dot(self.class_dot, s, m)
            s, m = checks.id_status(T, wpn, 'weapon') if wpn else (RISKY, 'no weapon found'); self._set_dot(self.weapon_dot, s, m)
            kit = T.class_learnables(T.unit_classes(uid) | set(info['jobs']))
            for w in info['weapons']:
                kit |= {a for a in T.weapon_line(w)[1] if not a.startswith('BATTLE_ABILITY_WEAPON_')}
            self.learn_box['values'] = [f'{T.name_of(a)}  [{a}]' for a in sorted(kit, key=T.name_of)]
        self.learn_tv.delete(*self.learn_tv.get_children()); self.tip_learn.clear()
        for flag, ab in info['learned']:
            s, m = checks.ability_status(T, uid, ab, info) if T else (SAFE, '')
            self.tip_learn[ab] = f'{LABELS[s]}' + (f': {m}' if m else ": part of this unit's kit")
            self.learn_tv.insert('', 'end', iid=ab, values=(DOT, T.name_of(ab) if T else ab, ab, 'passive' if flag else 'command'), tags=(s,))
        self.show_unit_tree(uid)
        acc = features.accessories(self.save, uid)
        self.u_other.configure(text=('Equipped accessories: ' + ', '.join((T.name_of(a) if T else a) for a in acc)) if acc
                               else 'No accessories equipped.')

    def pick(self, title, options):
        return PickDialog(self.root, title, options).result if options else None

    def labelled(self, rid):
        return f'{self.T.name_of(rid)}  [{rid}]' if self.T and rid else rid

    @staticmethod
    def unlabel(text):
        text = text.strip()
        return text[text.rfind('[') + 1:-1] if text.endswith(']') else text

    def apply_unit_stats(self):
        uid = self.unit_sel
        if not uid: return
        info = self.save.unit_info(uid); changes = []
        for k, v in self.u_vars.items():
            cast = float if k == 'speed_f' else int
            new = self.num(v.get(), cast); old = info['stats'][k]
            if new != old: changes.append((k, new))
        if not changes: return
        sts = []
        for k, new in changes:
            if k == 'level': sts.append(checks.level_status(new))
            elif k == 'exp': sts.append(checks.exp_status(new))
            else: sts.append(checks.stat_status(k, new))
        st = checks.worst(s for s, _ in sts); msg = '; '.join(m for _, m in sts if m)
        def go():
            for (k, new), (s, _) in zip(changes, sts): self.save.set_unit_stat(uid, k, new, s)
        self.edit(st, msg, go)

    def change_id(self, kind):
        uid = self.unit_sel
        if not uid: return
        info = self.save.unit_info(uid)
        old = (info['jobs'] if kind == 'class' else info['weapons'])
        new = self.unlabel((self.class_var if kind == 'class' else self.weapon_var).get())
        if not old or not new or new == old[0]: return
        if self.T:
            st, m = checks.class_status(self.T, uid, new) if kind == 'class' else checks.id_status(self.T, new, 'weapon')
        else:
            st, m = RISKY, 'tables not loaded'
        if kind == 'weapon' and st == SAFE:
            st, m = RISKY, 'weapon-tree purchases stay with the old weapon id'
        self.edit(st, m, lambda: self.save.replace_in_unit(uid, old[0], new, st))

    def learn(self):
        uid = self.unit_sel
        if not uid: return
        txt = self.learn_var.get().strip()
        ab = txt[txt.rfind('[') + 1:-1] if txt.endswith(']') else txt
        info = self.save.unit_info(uid)
        st, m = checks.ability_status(self.T, uid, ab, info) if self.T else (RISKY, 'tables not loaded')
        if len(info['learned']) >= checks.SHOWN_LEARNED and st == SAFE:
            st, m = RISKY, f'more than {checks.SHOWN_LEARNED} learned moves: the unit screens show only the first {checks.SHOWN_LEARNED}'
        self.edit(st, m, lambda: self.save.add_learned(uid, ab, self.learn_passive.get(), st))

    def unlearn(self):
        uid = self.unit_sel; sel = self.learn_tv.selection()
        if not uid or not sel: return
        self.edit(SAFE, '', lambda: self.save.remove_learned(uid, sel[0], SAFE))

    def inject_unit(self):
        if not self.save: return
        p = filedialog.askopenfilename(title='Save that has the unit record', filetypes=[('Save', '*.sav')])
        if not p: return
        try: src = model.Save(p)
        except Exception as e: messagebox.showerror(APP, str(e)); return
        missing = [u for u in src.unit_ids() if u not in self.save.unit_ids()]
        if not missing: messagebox.showinfo(APP, 'That save has no unit this one lacks.'); return
        names = [f'{self.T.name_of(u) if self.T else u}  [{u}]' for u in missing]
        pick = PickDialog(self.root, 'Add which unit?', names).result
        if pick is None: return
        uid = missing[pick]
        if self.T:
            src = model.Save(p); s, e = src.unit_record(uid)
            st, m = checks.record_status(self.T, uid, bytes(src.s1[s:e]))
        else:
            st, m = DANGER, 'the game tables are not loaded yet, so the record could not be checked'
        self.edit(st, m, lambda: self.save.inject_unit(p, uid, st))

    # ---- items
    def current_map(self):
        lab = self.item_map.get()
        return dict(ITEM_MAPS)[lab]

    def show_items(self):
        self.item_tv.delete(*self.item_tv.get_children()); self.tip_items.clear()
        if not self.save: return
        key = self.current_map(); T = self.T
        for k, at, v in self.save.map_by_label(key)['entries']:
            s = SAFE; why = ''
            if T:
                s1, m1 = checks.id_status(T, k)
                s2, m2 = checks.count_status(v)
                if k.startswith('NOTE_'): s1, m1 = SAFE, ''
                s = checks.worst([s1, s2]); why = '; '.join(x for x in (m1, m2) if x)
            self.tip_items[k] = f'{LABELS[s]}' + (f': {why}' if why else '')
            self.item_tv.insert('', 'end', iid=k, values=(DOT, T.name_of(k) if T else k, k, v), tags=(s,))
        if T:
            ids = set()
            for t in ITEM_TABLES[key]: ids |= set(T.rows.get(t, {}))
            self.add_item_box['values'] = [f'{T.name_of(i)}  [{i}]' for i in sorted(ids, key=T.name_of)]

    def edit_item(self):
        sel = self.item_tv.selection()
        if not sel: return
        k = sel[0]; old = self.item_tv.item(k, 'values')[3]
        new = simpledialog.askstring(APP, f'Count for {self.item_tv.item(k, "values")[1]}', initialvalue=old, parent=self.root)
        if new is None: return
        v = self.num(new); st, m = checks.count_status(v)
        self.edit(st, m, lambda: self.save.set_map_value(self.current_map(), k, v, st))

    def add_item(self):
        txt = self.add_item_var.get().strip()
        k = txt[txt.rfind('[') + 1:-1] if txt.endswith(']') else txt
        if not k: return
        v = self.num(self.add_count.get()); st, m = checks.count_status(v)
        if self.T:
            s2, m2 = checks.id_status(self.T, k)
            if checks.ORDER[s2] < checks.ORDER[st]: st, m = s2, m2
        self.edit(st, m, lambda: self.save.set_map_value(self.current_map(), k, v, st))

    def remove_item(self):
        sel = self.item_tv.selection()
        if sel: self.edit(SAFE, '', lambda: self.save.remove_map_entry(self.current_map(), sel[0], SAFE))

    # ---- story
    def fill_story_tree(self):
        self.ch_tv.delete(*self.ch_tv.get_children())
        if not self.T: return
        for label, groups in story.chapters(self.T):
            c = self.ch_tv.insert('', 'end', text=label, open=False)
            for key, title, items in groups:
                g = self.ch_tv.insert(c, 'end', text=f'{key}' + (f'   {title}' if title else ''), open=False)
                for i, a in items:
                    ok = story.is_target(i)
                    self.ch_tv.insert(g, 'end', iid=f'a{i}', text=a[3:] + ('' if ok else f'   ({story.point_kind(i)})'),
                                      values=(i,), tags=() if ok else ('nomarker',))
        self.ch_tv.tag_configure('nomarker', foreground='gray')

    def set_story(self):
        if not self.save: return
        sel = self.ch_tv.selection()
        if not sel or not sel[0].startswith('a'):
            messagebox.showinfo(APP, 'Pick a story point (the innermost rows).'); return
        idx = int(sel[0][1:])
        try:
            plan = story.warp_plan(self.save, idx, self.T)
        except (ValueError, KeyError) as e:
            messagebox.showinfo(APP, f'This point can\'t be used:\n\n{e}'); return
        if plan['direction'] == 'forward':
            return self.forward_dialog(idx)
        st = plan['status']
        flags = plan['flags_off']
        msg = (f"Go to {story.describe(idx, self.T)}\n"
               f"Direction: {plan['direction']} (from {plan['current'] or '?'})\n\n"
               f"World map: {', '.join(plan['markers'])} (character-story markers kept)\n"
               f"Story flags cleared (they belong after this point): {len(flags)}"
               + (f"\n  {', '.join(flags[:6])}{' …' if len(flags) > 6 else ''}" if flags else '') + "\n"
               "The save resumes on the world map; earlier flags, choices, the party and items stay as they are.")
        if plan['direction'] != 'back' and plan['direction'] != 'same point':
            msg += ("\n\nNot a point this run has passed: the story's joins, events and flags in between won't happen, "
                    "so the run may not match what the story expects.")
        if st != DANGER and not messagebox.askyesno(APP, msg + '\n\nApply? (Try it on a spare slot first: Copy to slot…)'): return
        self.edit(st, msg, lambda: story.set_position(self.save, idx, st, self.T))

    def forward_dialog(self, idx):
        """Forward story jump (story.forward_jump): pick how each branch on the way goes, optional side recruits and a
        level boost, then apply (Dangerous). The dialog is kept small; the summary lists what changes."""
        A = story.anchors()
        choices = {}
        win = tk.Toplevel(self.root); win.title('Jump forward in the story (experimental)'); win.transient(self.root)
        win.grab_set()
        body = ttk.Frame(win, padding=10); body.pack(fill='both', expand=True)
        ttk.Label(body, text=f"From {story.describe(self.save.sysvar('SCENARIO_ANCHOR')['value'], self.T)}\n"
                             f"to {story.describe(idx, self.T)}", justify='left').pack(anchor='w')
        ttk.Label(body, text='How the story goes at each branch on the way (votes and exploration outcomes):',
                  foreground='gray').pack(anchor='w', pady=(8, 2))
        bf = ttk.Frame(body); bf.pack(fill='x')
        boxes = {}

        def label(i, n, reaches):
            return f"{i}: {story.describe(A.index(n), self.T)}" + ('' if reaches else '   (does not lead to the target)')

        def render():
            for w in bf.winfo_children(): w.destroy()
            boxes.clear()
            path, decisions, ch = story.branch_decisions(self.save, idx, choices)
            choices.clear(); choices.update(ch)
            for r, (a, var, opts, v) in enumerate(decisions):
                ttk.Label(bf, text=f"{story.describe(A.index(a), self.T)}  [{var}]").grid(row=2 * r, column=0, sticky='w')
                cb = ttk.Combobox(bf, state='readonly', width=90, values=[label(*o) for o in opts])
                cb.current(v); cb.grid(row=2 * r + 1, column=0, sticky='w', padx=(16, 0), pady=(0, 4))
                cb.bind('<<ComboboxSelected>>', lambda e, var=var, cb=cb: (choices.__setitem__(var, cb.current()), render()))
                boxes[var] = cb
            if not decisions: ttk.Label(bf, text='(no branches on the way)').grid(row=0, column=0, sticky='w')
            ok = path and path[-1] == A[idx]
            status.configure(text=f'{len(path) - 1} story points on the way.' if ok else
                             'These choices do not lead to the target: change a branch above.')
            apply_btn.configure(state='normal' if ok else 'disabled')

        opt = ttk.Frame(body); opt.pack(fill='x', pady=(8, 0))
        rec = story.recommended_level(A[idx]) or 1
        lv_on = tk.BooleanVar(value=True); lv_val = tk.IntVar(value=rec)
        ttk.Checkbutton(opt, text='Raise party members below level', variable=lv_on).pack(side='left')
        ttk.Spinbox(opt, from_=1, to=50, width=4, textvariable=lv_val).pack(side='left', padx=4)
        ttk.Label(opt, text=f'to it, and teach their class moves up to it (this part recommends Lv {rec})').pack(side='left')
        keep = tk.BooleanVar(value=False)
        ttk.Checkbutton(body, text="Keep current party members (skip the story's departures, e.g. Roland leaving after "
                                   "the Chapter 1 battle until Chapter 2)", variable=keep).pack(anchor='w', pady=(4, 0))
        cand = story.recruit_candidates(self.save)
        rf = ttk.LabelFrame(body, text='Also recruit (characters this run never had; the story offers them through optional '
                                       'events and conviction):', padding=4)
        rf.pack(fill='both', expand=True, pady=(8, 0))
        lb = tk.Listbox(rf, selectmode='multiple', height=min(8, max(3, len(cand))), exportselection=False)
        for u in cand: lb.insert('end', f'{self.T.name_of(u) if self.T else u}   ({u[15:]})')
        lb.pack(side='left', fill='both', expand=True)
        ttk.Button(rf, text='All', command=lambda: lb.select_set(0, 'end')).pack(side='left', padx=4, anchor='n')
        status = ttk.Label(body, text=''); status.pack(anchor='w', pady=(8, 0))
        bb = ttk.Frame(body); bb.pack(fill='x', pady=(8, 0))

        def apply():
            recruits = [cand[i] for i in lb.curselection()]
            level = int(lv_val.get()) if lv_on.get() else None
            try:
                plan = story.forward_plan(self.save, idx, choices)
            except ValueError as e:
                messagebox.showinfo(APP, str(e), parent=win); return
            nm = lambda u: self.T.name_of(u) if self.T else u
            joins = [nm(u) for u, old, new in plan['party'] if new == 1]
            leaves = [(u, nm(u)) for u, old, new in plan['party'] if new == 2]
            if keep.get(): leaves = [(u, n) for u, n in leaves if self.save.s1[self.save.unit_record(u)[1] - 7] != 1]
            party_txt = ''
            if joins: party_txt += f"\nJoin the party on the way: {', '.join(joins)}."
            if leaves:
                party_txt += f"\nLeave the party on the way (as in the story): {', '.join(n for _, n in leaves)}."
                if any(u == 'UNIT_MASTER_CH_P002' for u, _ in leaves):
                    party_txt += (" Roland leaves after the Chapter 1 battle and rejoins in Chapter 2's second "
                                  "exploration; tick \"Keep current party members\" to keep him.")
            msg = (f"Jump forward to {story.describe(idx, self.T)} (experimental: it replays the story's main state, not everything a playthrough does)\n"
                   f"{len(plan['path']) - 1} story points replayed from the game's scripts: {len(plan['flags_on'])} story "
                   f"flags set, {len(plan['flags_off'])} cleared, {len(plan['party'])} party changes, {len(plan['uad'])} "
                   f"outfit sets, branch values {', '.join(f'{k}={v}' for k, v in plan['choices'].items()) or 'none'}."
                   + party_txt
                   + (f"\nAlso recruited: {len(recruits)}." if recruits else '')
                   + (f"\nParty members below Lv {level} raised to it." if level else '')
                   + (f"\n{plan['skipped']} script steps with conditions the editor can't read were skipped." if plan['skipped'] else '')
                   + "\n\nNot replayed: conviction, items, gold, talk, tutorials, in-scene choices. Then the story warp: the "
                     "save resumes on the world map at the target. Try it on a spare slot first (Copy to slot…).")
            win.destroy()
            kp = keep.get()
            self.edit(DANGER, msg, lambda: story.forward_jump(self.save, idx, choices, DANGER, self.T, recruits, level, kp))

        apply_btn = ttk.Button(bb, text='Jump…', command=apply); apply_btn.pack(side='right')
        ttk.Button(bb, text='Cancel', command=win.destroy).pack(side='right', padx=6)
        render()

    def show_flags(self):
        return self.show_flags_grouped()

    def show_flags_flat(self):
        self.flag_tv.delete(*self.flag_tv.get_children())
        if not self.save: return
        q = self.flag_q.get().strip().upper(); only = self.flag_on_only.get()
        n = 0
        for nm, at, v in self.save.flags['entries']:
            if q and q not in nm: continue
            if only and not v: continue
            self.flag_tv.insert('', 'end', iid=nm, values=(nm, v), tags=(SAFE if v in (0, 1) else DANGER,))
            n += 1
            if n >= 3000: break

    def toggle_flag(self):
        sel = self.flag_tv.selection()
        if not sel or sel[0].startswith('g:'): return
        nm = sel[0]; _, v = self.save.flag(nm); new = 0 if v else 1
        st, m = checks.flag_status(new)
        self.edit(st, m, lambda: self.save.set_flag(nm, new, st))

    # ---- issues
    def refresh_issues(self):
        self.iss_tv.delete(*self.iss_tv.get_children()); self.issues = []; self.tip_iss.clear()
        if not self.save or not self.T:
            self.summary.configure(text=''); return
        try:
            self.issues = checks.report(self.save, self.T)
        except Exception as e:
            self.issues = [checks.Finding(DANGER, 'Editor', 'check failed', str(e))]
        for i, f in enumerate(self.issues):
            self.tip_iss[str(i)] = f'{LABELS[f.status]}: {f.message}' + (f'\nFix available: {f.fix_label}' if f.fix else '')
            self.iss_tv.insert('', 'end', iid=str(i), values=(DOT, LABELS[f.status], f.area, f.item,
                                                              f.message + (f'   [fix: {f.fix_label}]' if f.fix else '')), tags=(f.status,))
        cnt = {s: sum(1 for f in self.issues if f.status == s) for s in (DANGER, RISKY)}
        worst = DANGER if cnt[DANGER] else RISKY if cnt[RISKY] else SAFE
        self.summary.configure(text=f'{DOT} {cnt[DANGER]} dangerous, {cnt[RISKY]} risky', fg=COLORS[worst])

    def fix_issue(self):
        sel = self.iss_tv.selection()
        if not sel: return
        f = self.issues[int(sel[0])]
        if not f.fix: messagebox.showinfo(APP, 'No automatic fix for this one.'); return
        self.edit(SAFE, '', f.fix)

    # ---- backups
    def refresh_backups(self):
        self.bk_tv.delete(*self.bk_tv.get_children())
        for b in self.safety.list_backups():
            self.bk_tv.insert('', 'end', iid=b['path'], values=(b['name'], b.get('reason', ''), 'yes' if b['pinned'] else ''))

    def backup_now(self):
        d = self.dir_var.get()
        if not os.path.isdir(d): return
        self.safety.backup(d, 'manual backup', pin=True); self.refresh_backups()

    def pin(self):
        sel = self.bk_tv.selection()
        if sel: self.safety.pin(sel[0]); self.refresh_backups()

    def restore(self):
        sel = self.bk_tv.selection()
        if not sel: return
        files = [f for f in sorted(os.listdir(sel[0])) if f.endswith('.sav') and f in model.SLOT_FILES]
        files += [f for f in sorted(os.listdir(sel[0])) if f.endswith('.sav') and f not in files]   # e.g. SystemData
        labels = [self.describe_file(os.path.join(sel[0], f), model.SLOT_FILES.get(f, f)) if f in model.SLOT_FILES
                  else f for f in files]
        pick = PickDialog(self.root, 'Restore which file into the save folder?', labels).result
        if pick is None: return
        fn = files[pick]; dst = os.path.join(self.dir_var.get(), fn)
        if self.safety.is_locked(dst):
            if not self.unlock_slot1(dst): return
        if not messagebox.askyesno(APP, f'Replace {model.SLOT_FILES.get(fn, fn)} in the save folder with the copy from '
                                        f'{os.path.basename(sel[0])}?\nThe current folder is backed up first.'):
            self.safety.slot1_unlocked = False; return
        try:
            self.safety.restore(sel[0], fn, self.dir_var.get())
            messagebox.showinfo(APP, 'Restored and verified.'); self.refresh_slots(); self.refresh_backups()
        except Exception as e:
            messagebox.showerror(APP, str(e))

    # ------------------------------------------------------------------------------------------ writing
    def unlock_slot1(self, path):
        reason = self.safety.locked_reason(path)
        what = 'slot 1' if os.path.basename(path) == 'TRIANGLE_STRATEGY-SaveData_0.sav' else 'this copy of slot 1'
        if not messagebox.askyesno(APP, f'{reason}\n\nUnlock {what} for this one write?', icon='warning'): return False
        typed = simpledialog.askstring(APP, f'Type UNLOCK to confirm writing {what}:', parent=self.root)
        if (typed or '').strip().upper() != 'UNLOCK': return False
        self.safety.slot1_unlocked = True
        return True

    def fresh_check(self):
        """(worst rating, text) of a full check of the save as it would be written, against the file it was opened
        from: only problems the edits added count, so the rating can't hide e.g. an imported record whose ids the
        installed pak lacks (review finding E)."""
        hist = [s for _, s in self.save.history]
        if not self.T:
            return checks.worst(hist + [RISKY]), '\n\nThe game tables are still loading: the save was NOT re-checked.'
        try:
            base = checks.report(model.Save(self.path), self.T) if self.path and os.path.exists(self.path) else []
        except (Exception, SystemExit):
            base = []
        try:
            new = checks.new_findings(base, checks.report(self.save, self.T))
        except (Exception, SystemExit) as e:
            return DANGER, f'\n\nThe full check failed on the edited save: {e}'
        if not new: return checks.worst(hist), '\n\nFull check: no new problems.'
        lines = '\n'.join(f'  {LABELS[f.status]}: {f.area} / {f.item}: {f.message}' for f in new[:8])
        return (checks.worst(hist + [f.status for f in new]),
                f'\n\nFull check, problems the edits add ({len(new)}):\n{lines}' + ('\n  …' if len(new) > 8 else ''))

    def write_slot(self):
        if not self.save or not self.path: return
        if not self.save.dirty: messagebox.showinfo(APP, 'No changes to write.'); return
        if safety.game_running(): messagebox.showerror(APP, 'The game is running. Close it first.'); return
        if self.safety.is_locked(self.path) and not self.unlock_slot1(self.path): return
        worst, check = self.fresh_check()
        lines = '\n'.join(f'  {LABELS[s]}: {d}' for d, s in self.save.history[-25:])
        if not messagebox.askyesno(APP, f'Write {len(self.save.history)} change(s) to {self.slot_name()}?\n'
                                        f'Worst rating: {LABELS[worst]}\n\n{lines}{check}\n\nThe whole save folder is backed up first.',
                                   icon=('warning' if worst != SAFE else 'question')):
            self.safety.slot1_unlocked = False; return
        try:
            bdir = self.safety.write(self.save, self.path)
        except Exception as e:
            messagebox.showerror(APP, f'Nothing was written:\n{e}'); return
        messagebox.showinfo(APP, f'Written and checked.\nThe previous files are in the Backups tab ({os.path.basename(bdir)}).')
        p = self.path; self.save = None; self.open_path(p); self.refresh_slots(); self.refresh_backups()

    def copy_to_slot(self):
        """Write the open save (with any edits) into another slot of the save folder: same checks as Write."""
        if not self.save: return
        d = self.dir_var.get()
        targets = [(fn, lab) for fn, lab in model.SLOT_FILES.items() if lab.startswith('Slot') and os.path.join(d, fn) != self.path]
        labels = [f'{lab}' + ('  (exists: will be replaced)' if os.path.exists(os.path.join(d, fn)) else '  (empty)') +
                  ('  [locked]' if self.safety.is_locked(os.path.join(d, fn)) else '') for fn, lab in targets]
        pick = PickDialog(self.root, 'Copy this save into which slot?', labels).result
        if pick is None: return
        dest = os.path.join(d, targets[pick][0])
        if safety.game_running(): messagebox.showerror(APP, 'The game is running. Close it first.'); return
        if self.safety.is_locked(dest) and not self.unlock_slot1(dest): return
        worst, check = self.fresh_check()
        if not messagebox.askyesno(APP, f'Write this save into {targets[pick][1]}?\nWorst rating: {LABELS[worst]}{check}\n\n'
                                        'The whole save folder is backed up first.',
                                   icon=('warning' if worst != SAFE else 'question')):
            self.safety.slot1_unlocked = False; return
        try:
            bdir = self.safety.write(self.save, dest)
        except Exception as e:
            messagebox.showerror(APP, f'Nothing was written:\n{e}'); return
        messagebox.showinfo(APP, f'Copied into {targets[pick][1]} and checked.\nThe previous files are in the Backups tab.')
        self.refresh_slots(); self.refresh_backups()

    def save_copy(self):
        if not self.save: return
        p = filedialog.asksaveasfilename(defaultextension='.sav', filetypes=[('Save', '*.sav')],
                                         initialfile='edited_copy.sav')
        if not p: return
        if (os.path.abspath(os.path.dirname(p)) == os.path.abspath(self.dir_var.get())
                or self.safety.is_game_save_location(p)):
            messagebox.showerror(APP, 'That is a game save folder or a game save file name. Use "Write to slot" or '
                                      '"Copy to slot…" there: they check the game is closed, keep slot 1 locked and '
                                      'back up first.'); return
        if self.safety.is_locked(p):
            messagebox.showerror(APP, 'That file is a copy of your protected slot 1 save; it is not overwritten. '
                                      'Pick another name.'); return
        tmp = p + '.tsmod_tmp'
        try:
            open(tmp, 'wb').write(self.save.encoded()); model.Save(tmp)
            os.replace(tmp, p)
        except (Exception, SystemExit) as e:
            if os.path.exists(tmp): os.remove(tmp)
            messagebox.showerror(APP, f'Nothing was written:\n{e}'); return
        messagebox.showinfo(APP, f'Saved and verified: {p}')

    # ------------------------------------------------------------------------------------------ refresh
    def refresh_all(self):
        self.title(); self.refresh_backups()
        if not self.save: return
        s = self.save; T = self.T; pv = s.preview
        try: anchor = s.sysvar('SCENARIO_ANCHOR')['value']
        except KeyError: anchor = None
        leader = T.english(pv['leader']) if T else pv['leader']
        place = ''
        for var in ('TRANSITION_LEVEL_RECORD', 'MAIN_LEVEL_RECORD_BEFORE_QUEST'):
            try:
                place = T.place_of_level(s.sysvar(var)['value']) if T else ''
            except KeyError:
                place = ''
            if place: break
        self.ov_info.configure(text=(f"Leader: {leader}   Level {pv['level']}" + (f"   Location: {place}" if place else '') + "\n"
                                     f"Saved: {pv['saved'][:16]}   Play time: {self.play_time(pv['play_time'])}\n"
                                     f"Units: {len(s.unit_recs)}   Story: {story.describe(anchor, self.T) if anchor is not None else '?'}"))
        self.gold_var.set(f'{s.gold:,}'); st, m = checks.gold_status(s.gold); self._set_dot(self.gold_dot, st, m)
        for i, v in enumerate(self.conv_vars, 1): v.set(str(s.parts['convictions']['a'][i][1]))
        self.var_tv.delete(*self.var_tv.get_children())
        for e in s.sysvars['entries']:
            self.var_tv.insert('', 'end', iid=e['name'], values=(e['name'], e['value'] if e['name'] != 'SCENARIO_ANCHOR'
                                                                 else f"{e['value']}  ({story.describe(e['value'], self.T)})"))
        sel = self.unit_sel
        self.unit_tv.delete(*self.unit_tv.get_children()); self.tip_units.clear()
        for uid in s.unit_ids():
            info = s.unit_info(uid)
            st = SAFE; why = []
            if T:
                res = [checks.id_status(T, uid, 'unit'), checks.level_status(info['stats']['level'])]
                res += [checks.class_status(T, uid, j) for j in info['jobs']]
                for _, a in info['learned']:
                    r = checks.ability_status(T, uid, a, info)
                    res.append((r[0], f'{T.name_of(a)}: {r[1]}' if r[1] else ''))
                if len(info['learned']) > checks.SHOWN_LEARNED:
                    res.append((RISKY, f"{len(info['learned'])} learned moves: the game shows only the first {checks.SHOWN_LEARNED}"))
                st = checks.worst(r[0] for r in res); why = [r[1] for r in res if r[1]]
            self.tip_units[uid] = LABELS[st] + (':\n' + '\n'.join(why) if why else ': no problems found')
            job = info['jobs'][0] if info['jobs'] else ''
            self.unit_tv.insert('', 'end', iid=uid, values=(DOT, T.name_of(uid) if T else uid, info['stats']['level'],
                                                            T.name_of(job) if T and job else job), tags=(st,))
        if sel and self.unit_tv.exists(sel): self.unit_tv.selection_set(sel); self.unit_tv.see(sel); self.show_unit()
        elif sel:
            # The unit isn't in this save (another save was opened): clear the panel, so no action targets a stale id.
            self.unit_sel = None
            self.u_title.configure(text='Pick a unit')
            for v in self.u_vars.values(): v.set('')
        self.show_items(); self.show_flags(); self.show_shop(); self.show_orders(); self.show_unlocks()
        if T:
            ms = features.mod_summary(s, T)
            if ms['missing']:
                txt = (f"TSMod: this save uses {len(ms['missing'])} id(s) the installed TSMod pak doesn't have. "
                       f"It probably needs another TSMod version. See Issues.")
                self.mod_lbl.configure(text=txt, foreground=COLORS[DANGER])
            elif ms['recruits'] or ms['mod_ids']:
                self.mod_lbl.configure(text=f"TSMod: {len(ms['recruits'])} recruit(s); every TSMod id the save uses is in the "
                                            f"installed pak ({', '.join(ms['paks']) or 'none'}).", foreground=COLORS[SAFE])
            else:
                self.mod_lbl.configure(text='No TSMod content in this save.', foreground='#555')
        self.story_now.configure(text=f'Current story position: {story.describe(anchor, self.T) if anchor is not None else "?"}')
        self.chg_tv.delete(*self.chg_tv.get_children())
        for i, (d, stt) in enumerate(s.history):
            self.chg_tv.insert('', 'end', iid=str(i), values=(DOT, LABELS[stt], d), tags=(stt,))
        self.refresh_issues()


class Tips:
    """Hover tooltips: for plain widgets (attach) and per Treeview row (rows[tree][iid] = text)."""
    def __init__(self, root):
        self.root, self.win, self.rows = root, None, {}

    def _show(self, x, y, text):
        self.hide()
        if not text: return
        self.win = tw = tk.Toplevel(self.root); tw.wm_overrideredirect(True); tw.wm_geometry(f'+{x + 14}+{y + 12}')
        tk.Label(tw, text=text, justify='left', background='#ffffe6', relief='solid', borderwidth=1,
                 wraplength=420, padx=6, pady=3).pack()

    def hide(self, event=None):
        if self.win: self.win.destroy(); self.win = None

    def attach(self, widget, text_fn):
        widget.bind('<Enter>', lambda e: self._show(e.x_root, e.y_root, text_fn()), add='+')
        widget.bind('<Leave>', self.hide, add='+')

    def tree(self, tv):
        self.rows[tv] = {}; last = [None]
        def motion(e):
            iid = tv.identify_row(e.y)
            if iid == last[0]: return
            last[0] = iid; self._show(e.x_root, e.y_root, self.rows[tv].get(iid, ''))
        tv.bind('<Motion>', motion, add='+')
        tv.bind('<Leave>', lambda e: (self.hide(), last.__setitem__(0, None)), add='+')
        return self.rows[tv]


class PickDialog(simpledialog.Dialog):
    def __init__(self, parent, title, options):
        self.options = options; self.result = None
        super().__init__(parent, title)

    def body(self, master):
        w = min(150, max(70, max((len(o) for o in self.options), default=0) + 2))   # long save descriptions fit
        self.lb = tk.Listbox(master, width=w, height=min(18, max(4, len(self.options))))
        for o in self.options: self.lb.insert('end', o)
        self.lb.pack(fill='both', expand=True)
        if self.options: self.lb.selection_set(0)
        return self.lb

    def apply(self):
        sel = self.lb.curselection()
        self.result = sel[0] if sel else None


def main():
    root = tk.Tk()
    try:
        App(root)
    except Exception:
        messagebox.showerror(APP, traceback.format_exc()); raise
    root.mainloop()


if __name__ == '__main__':
    main()
