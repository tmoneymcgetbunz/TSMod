"""Offline check: will an ability's animation render on a given character's sprite?

[tested Test 14, 2026-11-16] An ability's AttackParam.FlipbookId -> AnimationAssetTable row -> ATK_* NeweraAnimationData.
That asset references flipbooks in one of two ways:
  * generic:  /Game/Newera/Character/000/<flipbook>  -> swapped at runtime for the unit's own frames of that group
              (Character/<id>/Frames/<group>NN_*). Unit lacks the group => grey placeholder frames.
              (Herosbane=ATK_Suppress on Rufus, Twinsgate Bulwark=Fortress on Svarog, Rosellan Resolve=PowerRise on Jerrom)
  * foreign:  /Game/Newera/Character/<other id>/...    -> plays that character's own sprite
              (Under Conviction's Banner=ATK_Energize shows Serenoa, Saltiron Valor=ATK_Lod_Slash shows Avlora)

  python tools/anim_check.py <CHAR> <FlipbookId|BATTLE_ABILITY_...> ...
  python tools/anim_check.py <CHAR> --groups          # list the unit's frame groups
  python tools/anim_check.py <CHAR> --scan            # every AnimationAssetTable row that renders cleanly on CHAR
  Add --variant TypeHorse (any folder under Character/<id>/) to check only that variant's frames, e.g. a mounted
  unit's horse set (Batch C, Clarus). Without it, every Frames folder of the character counts.
"""
import os, re, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tspak, dtparse as D, uasset_edit as U

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAK = paths.game_pak()
DTP = 'TRIANGLE_STRATEGY/Content/Newera/Data/DataTables/'
CH = 'TRIANGLE_STRATEGY/Content/Newera/Character/'
GROUP = re.compile(r'^(.*?\d[a-z])')          # atktsd0a_skill -> atktsd0a, magicstick0a -> magicstick0a

_pak = None
def pak():
    global _pak
    _pak = _pak or tspak.Pak(PAK)
    return _pak


def _table(name):
    base = os.path.join(ROOT, 'extracted', *DTP.split('/'), name)
    if not os.path.exists(base + '.uasset'):
        os.makedirs(os.path.dirname(base), exist_ok=True)
        for e in ('.uasset', '.uexp'): open(base + e, 'wb').write(pak().read(DTP + name + e))
    return base


def anim_table():
    base = _table('AnimationAssetTable')
    ua = open(base + '.uasset', 'rb').read(); ue = open(base + '.uexp', 'rb').read()
    nm = [n for n, _ in U.read_names(ua, U.read_summary(ua))[0]]
    _, rows = D.parse(base + '.uasset')
    return {k: nm[struct.unpack_from('<i', ue, r['AnimationData']['off'])[0]] for k, r in rows.items()}


def ability_flipbook(ab_id):
    _, A = D.parse(_table('GOP_Battle_Ability') + '.uasset')
    _, P = D.parse(_table('GOP_Battle_AttackParam') + '.uasset')
    ap = A[ab_id]['AttackParam']['v']
    return P[ap]['FlipbookId']['v'] if ap in P else None


def refs(asset_path):
    p = asset_path.split('.')[0].replace('/Game/', 'TRIANGLE_STRATEGY/Content/') + '.uasset'
    ua = pak().read(p)
    return [n for n, _ in U.read_names(ua, U.read_summary(ua))[0] if n.startswith('/Game/Newera/Character/')]


def frame_group(frame):
    """walk03_LB -> walk, atkswd0a01_LU -> atkswd0a, throw_socket_LB -> throw"""
    f = re.sub(r'(_[A-Z]+\d?)$', '', frame)
    f = re.sub(r'\d\d$', '', f)
    return f.lower().split('_')[0]


def groups(char, variant=None):
    out = set()
    pre = f'{CH}{char}/{variant}/Frames/' if variant else f'{CH}{char}/'
    for n in pak().files:
        if n.startswith(pre) and '/Frames/' in n and n.endswith('.uasset'):
            out.add(frame_group(n.split('/')[-1][:-7]))
    return out


def check(char, fid, anims=None, have=None):
    anims = anims or anim_table(); have = have if have is not None else groups(char)
    if fid in (None, 'None'): return 'OK (no animation)', []
    if fid not in anims: return f'? {fid} not in AnimationAssetTable', []
    bad, warn = [], []
    me = anims[fid].split('.')[0]
    for r in refs(anims[fid]):
        parts = r.split('/')        # /Game/Newera/Character/<id>/...
        cid = parts[4]
        if r == me or '/Effect/' in r: continue          # the animation asset itself, particle configs
        if cid == '000':
            g = parts[-1].lower().split('_')[0]           # atkswd0a_skill00 -> atkswd0a, throw_socket -> throw
            if g == 'booby': continue                     # trap prop, not a unit pose
            if g not in have: bad.append(f'missing frames {g}')
        elif cid not in (char, 'weapon', 'Common', 'common') and not cid.startswith('weapon'):
            leaf = parts[-1].lower()
            if leaf.endswith('_socket') or leaf.startswith('atk0a') or 'weapon' in leaf or 'launcher' in leaf:
                warn.append(f'{cid} prop/weapon flipbook')    # held item or thrown prop, not the body sprite
            else:
                bad.append(f'plays {cid} sprite')
    # Test 14 exception: Wolffort's Aegis (Cover_P001, needs atkswd0a) looked fine on Symon, who only has atktsd0a.
    return ('OK' if not bad else 'BAD') + (' (warn)' if warn and not bad else ''), sorted(set(bad + warn))


if __name__ == '__main__':
    char, args = sys.argv[1], sys.argv[2:]
    variant = None
    if '--variant' in args:
        i = args.index('--variant'); variant = args[i + 1]; args = args[:i] + args[i + 2:]
    have = groups(char, variant)
    if args == ['--groups']:
        print(sorted(have)); sys.exit()
    anims = anim_table()
    if args == ['--scan']:
        for fid in sorted(anims):
            try: st, why = check(char, fid, anims, have)
            except Exception as e: continue
            if st.startswith('OK'): print(f'  {fid:34} {anims[fid].split("/")[-1].split(".")[0]}')
        sys.exit()
    for a in args:
        fid = ability_flipbook(a) if a.startswith('BATTLE_ABILITY_') else a
        st, why = check(char, fid, anims, have)
        print(f'  {a:46} {str(fid):26} {st} {"; ".join(why)}')
