"""Render a battle map's WhiteBox grid (BP_BaseBlock actors) as text.

  python wbmap.py <..._WB.umap> [x,y x,y ...]   (optional coordinates to mark with *)

Each cell shows terrain letter + height. Letters: S=stone, o=soil, W=water, h=shallow,
P=pier, F=flooring, R=roof, #=nopass, ?=other. Blank = no block.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dtparse as D

LET = {'STONE': 'S', 'SOIL': 'o', 'WATER': 'W', 'SHALLOW': 'h', 'PIER': 'P',
       'FLOORING': 'F', 'ROOF': 'R', 'NOPASS': '#'}


def load(umap):
    return load_bytes(open(umap, 'rb').read(), open(umap[:-5] + '.uexp', 'rb').read())


def load_bytes(ua, ue):
    """{(x, y): (EMapAttribute name, height)} from a _WB sublevel's .umap and .uexp bytes."""
    names, imps, exps, th = D.read_exports(ua)
    def cname(i): return imps[-i - 1][3] if i < 0 else exps[i - 1]['name'] if i > 0 else 'None'
    cells = {}
    for e in exps:
        if cname(e['cls']) != 'BP_BaseBlock_C': continue
        p = D.Parser(names, ue); p.r.p = e['off'] - th
        try:
            pr = {k: v['v'] for k, v in p.props().items()}
        except Exception:                      # a block whose extra properties dtparse can't read: skip it
            bad = cells.setdefault('_unreadable', [])
            bad.append(e['name'])
            continue
        x, y = pr.get('MapPosX', 0), pr.get('MapPosY', 0)
        attr = str(pr.get('MapAttribute', 'EMapAttribute::NONE')).split('::')[-1]
        cells[(x, y)] = (attr, pr.get('Height', 0))
    return cells


if __name__ == '__main__':
    cells = load(sys.argv[1])
    marks = {tuple(map(int, a.split(','))) for a in sys.argv[2:]}
    mx = max(x for x, _ in cells); my = max(y for _, y in cells)
    print('    ' + ''.join(f'{x:>4}' for x in range(mx + 1)))
    for y in range(my + 1):
        row = []
        for x in range(mx + 1):
            if (x, y) in cells:
                a, h = cells[(x, y)]
                s = LET.get(a, '?') + str(h)
            else:
                s = ''
            if (x, y) in marks: s = '*' + s
            row.append(f'{s:>4}')
        print(f'{y:>3} ' + ''.join(row))
