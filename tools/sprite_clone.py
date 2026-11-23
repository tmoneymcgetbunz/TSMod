"""Clone a character's sprite assets under another override name (renamed copies, no new art).

mod.json key "sprite_clones": list of
  {"char": "N204", "from": "HORSE", "to": ["HORSE_RANK2", "HORSE_RANK3"]}
      copies every FlipbookOutput/<char>/AnimationData/<char>_<Anim>_<from>_<Rank> and
      Flipbook/<char>_<Anim>_<from>_<Rank>_CHARACTER as ..._<to>_...; the AnimationData copy points at the
      flipbook copy, and the flipbooks keep using the original frame textures.
  {"char": "N204", "anim": "UIC_BattleIdle", "overwrite": "DEFAULT", "with": "HORSE"}
      replaces the <overwrite> flipbooks of one animation with renamed copies of the <with> flipbooks.
  {"char": "N204", "frames_from": "TypeHorse", "to_folder": "TypeHorse_Rank2", "only": "UIC_"}
      copies sprite frames Character/<char>/<frames_from>/Frames/* into Character/<char>/<to_folder>/Frames/
      ("" = the plain Frames folder); textures stay those of the source folder. Existing game files are never replaced.
Only name-map strings change (uasset_edit.rename_names); export data is byte-identical to the source.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import uasset_edit as U

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FBO = 'TRIANGLE_STRATEGY/Content/Newera/Data/FlipbookOutput/'
RANKS = ('DEFAULT', 'MIDDLE', 'HIGH')


def _files():
    return [l.strip() for l in open(os.path.join(ROOT, 'pak_filelist.txt'), encoding='utf-8')]


def _write(stage, path, ua, ue):
    out = os.path.join(stage, *path.split('/'))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out + '.uasset', 'wb').write(ua); open(out + '.uexp', 'wb').write(ue)


def apply_to_stage(entries, stage, pak=None):
    if pak is None:
        import tspak
        pak = tspak.Pak(paths.game_pak())
    files = set(f[:-7] for f in _files() if f.endswith('.uasset') and f.startswith(FBO))
    made = []
    for e in entries:
        c = e['char']
        if 'frames_from' in e:
            CH = 'TRIANGLE_STRATEGY/Content/Newera/Character/'
            src_dir = f"{CH}{c}/{e['frames_from']}/Frames/"
            dst_dir = f"{CH}{c}/{e['to_folder'] + '/' if e['to_folder'] else ''}Frames/"
            all_ch = set(f[:-7] for f in _files() if f.endswith('.uasset') and f.startswith(CH))
            srcs = sorted(f for f in all_ch if f.startswith(src_dir) and f.split('/')[-1].startswith(e.get('only', '')))
            g = lambda p: '/Game/' + p.split('Content/', 1)[1]
            for s_ in srcs:
                d = dst_dir + s_.split('/')[-1]
                assert d not in all_ch, f'{d} exists in the game; refusing to replace'
                ua = U.rename_names(pak.read(s_ + '.uasset'), {None: [(g(src_dir), g(dst_dir))]})
                _write(stage, d, ua, pak.read(s_ + '.uexp')); made.append(d)
            print(f"  sprite_clones {c}: {len(srcs)} frames {e['frames_from']} -> {e['to_folder'] or 'Frames'}")
            continue
        if 'to' in e:
            frm = e['from']
            srcs = sorted(f for f in files if f.startswith(f'{FBO}{c}/') and f'_{frm}_' in f.split('/')[-1]
                          and f.split('/')[-1].split(f'_{frm}_')[1].split('_')[0] in RANKS)
            for to in e['to']:
                n = 0
                for s in srcs:
                    d = s.replace(f'_{frm}_', f'_{to}_')
                    assert d not in files, f'{d} already exists in the game'
                    ua = U.rename_names(pak.read(s + '.uasset'), {None: [(f'_{frm}_', f'_{to}_')]})
                    _write(stage, d, ua, pak.read(s + '.uexp')); made.append(d); n += 1
                print(f'  sprite_clones {c}: {n} assets {frm} -> {to}')
        else:
            a, ov, w = e['anim'], e['overwrite'], e['with']
            fc = e.get('from_char', c)             # another character's flipbook may be used (control probes)
            for r in RANKS:
                s = f'{FBO}{fc}/Flipbook/{fc}_{a}_{w}_{r}_CHARACTER'; d = f'{FBO}{c}/Flipbook/{c}_{a}_{ov}_{r}_CHARACTER'
                assert s in files and d in files, (s, d)
                ua = U.rename_names(pak.read(s + '.uasset'), {None: [(f'{fc}_{a}_{w}_{r}', f'{c}_{a}_{ov}_{r}'),
                                                                     (f'/FlipbookOutput/{fc}/', f'/FlipbookOutput/{c}/')]})
                _write(stage, d, ua, pak.read(s + '.uexp')); made.append(d)
            print(f'  sprite_clones {c}: {a} {ov} flipbooks replaced by {fc} {w} copies')
    # verify every written asset: header consistent, hashes valid, self-name matches its path
    for d in made:
        p = os.path.join(stage, *d.split('/'))
        ua = open(p + '.uasset', 'rb').read(); f = U.read_summary(ua)
        names = [n for n, _ in U.read_names(ua, f)[0]]
        me = d.split('/')[-1]
        assert '/Game/' + d.split('Content/', 1)[1] in names and me in names, d
        if '/Character/' in d:                     # frames keep the source folder's textures
            assert any('/Textures/' in n for n in names), d
        assert not U.check_hashes(ua)[1]
        assert f['TotalHeaderSize'][0] == len(ua)
        assert f['BulkDataStartOffset'][0] == len(ua) + os.path.getsize(p + '.uexp') - 4
    return made
