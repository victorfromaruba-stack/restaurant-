"""Taco Brava: ground beef street tacos (gt). usage: python3 taco.py"""
import math, random, os, subprocess, sys
from artlib import Svg, f, rot, smooth_closed, smooth_open, blob, blob_pts, poly, mix, specks, rrect_path, goo_filter
import food

HERE = os.path.dirname(os.path.abspath(__file__))
SVG = os.path.join(HERE, "taco-brava", "gt.svg")
OUT = "/home/claude/work/brand-hub/taco-brava/assets/art/gt.webp"
RENDER = "/home/claude/work/tools/render_svg.py"


def powder_filter(s, seed, color, disp=26, soft=6, dens=3.0, grain=1.6):
    """Powdery pigment: displaced rough shape, density fading to sparse grains at the edges."""
    fid = s.uid("pw")
    s.d(f'<filter id="{fid}" filterUnits="userSpaceOnUse" x="0" y="0" width="{s.w}" height="{s.h}" color-interpolation-filters="sRGB">'
        f'<feTurbulence type="fractalNoise" baseFrequency="0.012 0.04" numOctaves="3" seed="{seed}" result="t"/>'
        f'<feDisplacementMap in="SourceGraphic" in2="t" scale="{disp}" xChannelSelector="R" yChannelSelector="G" result="d"/>'
        f'<feGaussianBlur in="d" stdDeviation="{soft}" result="b"/>'
        f'<feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="{seed+5}" result="g"/>'
        f'<feComposite in="b" in2="g" operator="arithmetic" k1="0" k2="{dens}" k3="{-grain}" k4="0.12" result="a"/>'
        f'<feFlood flood-color="{color}" result="c"/>'
        f'<feComposite in="c" in2="a" operator="in"/>'
        f'</filter>')
    return f"url(#{fid})"


def brush_smear(s, path_pts, width, color, rng, seed):
    """Painterly dry-brush / powder smear along a path."""
    out = []
    N = len(path_pts)
    ws = []
    for i in range(N):
        t = i / (N - 1)
        ws.append(width * (0.25 + 0.75 * math.sin(math.pi * t) ** 0.5))
    d = food.stroke_band(path_pts, ws, rng, wob=0.05)
    pf = powder_filter(s, seed, color)
    # main body
    out.append(f'<g filter="{pf}"><path d="{d}" fill="#000"/></g>')
    # bristle streaks along the stroke
    br = []
    for k in range(70):
        off = rng.uniform(-1.05, 1.05)
        i0 = rng.randint(0, N // 3); i1 = rng.randint(N // 2, N - 1)
        seg = []
        for i in range(i0, i1):
            x, y = path_pts[i]
            x0, y0 = path_pts[max(i - 1, 0)]; x1, y1 = path_pts[min(i + 1, N - 1)]
            tx, ty = x1 - x0, y1 - y0; L = math.hypot(tx, ty) or 1
            seg.append((x - ty / L * ws[i] * off + rng.uniform(-1, 1), y + tx / L * ws[i] * off))
        br.append(f'<path d="{smooth_open(seg)}" stroke="#000" stroke-width="{f(rng.uniform(1.5, 4))}" fill="none" stroke-linecap="round" opacity="{rng.uniform(0.3, 0.8):.2f}"/>')
    out.append(f'<g filter="{powder_filter(s, seed + 2, mix(color, "#000000", 0.18), disp=6, soft=0.8, dens=2.2, grain=1.0)}" opacity="0.55">{"".join(br[:35])}</g>')
    out.append(f'<g filter="{powder_filter(s, seed + 3, mix(color, "#ffffff", 0.25), disp=6, soft=0.8, dens=2.2, grain=1.0)}" opacity="0.45">{"".join(br[35:])}</g>')
    # loose dust specks around
    dust = []
    for _ in range(160):
        i = rng.randrange(N)
        x, y = path_pts[i]
        o = rng.gauss(0, ws[i] * 0.9)
        x0, y0 = path_pts[max(i - 1, 0)]; x1, y1 = path_pts[min(i + 1, N - 1)]
        tx, ty = x1 - x0, y1 - y0; L = math.hypot(tx, ty) or 1
        dust.append(poly(x - ty / L * o, y + tx / L * o, rng.uniform(0.8, 2.4), rng))
    out.append(f'<path d="{"".join(dust)}" fill="{color}" opacity="0.6"/>')
    return "".join(out)


def stone_plate(s, cx, cy, w, h, ang, rng):
    a = math.radians(ang)
    pts = []
    r = 26
    hw, hh = w / 2, h / 2
    for (ccx, ccy, st) in [(hw - r, -hh + r, -90), (hw - r, hh - r, 0), (-hw + r, hh - r, 90), (-hw + r, -hh + r, 180)]:
        for i in range(7):
            t = math.radians(st + 90 * i / 6)
            p = rot((ccx + math.cos(t) * r, ccy + math.sin(t) * r), a)
            pts.append((cx + p[0], cy + p[1]))
    d = "M" + "L".join(f"{f(x)},{f(y)}" for x, y in pts) + "Z"
    out = []
    # hard sun shadow + soft ambient
    out.append(s.shadow(d, 22, 26, 7, 0.32, "#5a3a10"))
    out.append(s.shadow(d, 8, 10, 14, 0.25, "#3a2408"))
    g = s.lin(cx - hw, cy - hh, cx + hw, cy + hh, [(0, "#F7F3EA"), (0.55, "#EFE9DD"), (1, "#E2DACB")])
    out.append(f'<path d="{d}" fill="{g}"/>')
    # stone grain
    tex = s.texture(freq=0.035, scale=0.9, seed=77, spec=0.0, gain=1.3, octaves=3, region='x="-2%" y="-2%" width="104%" height="104%"')
    out.append(f'<path d="{d}" fill="#EFE9DD" filter="{tex}" opacity="0.45" style="mix-blend-mode:multiply"/>')
    cl = s.clip(d)
    sp = {("#8B8072", 0.55): [], ("#B9AE9C", 0.6): [], ("#6E6458", 0.45): [], ("#ffffff", 0.7): []}
    keys = list(sp.keys())
    for _ in range(int(w * h / 380)):
        x = cx + rng.uniform(-hw, hw); y = cy + rng.uniform(-hh, hh)
        sp[keys[rng.randrange(4)]].append(poly(x, y, rng.uniform(0.6, 1.9), rng))
    out.append(f'<g clip-path="{cl}">{specks(sp)}')
    # bevelled edge: light top-left rim, darker bottom-right rim
    out.append(f'<path d="{d}" fill="none" stroke="#ffffff" stroke-width="5" opacity="0.7" transform="translate(2,2)" filter="{s.blur(1.5)}"/>')
    out.append(f'<path d="{d}" fill="none" stroke="#9c8f78" stroke-width="7" opacity="0.35" transform="translate(-3,-3)" filter="{s.blur(2.5)}"/>')
    out.append('</g>')
    return "".join(out)


def tortilla(s, cx, cy, R, rng, seed):
    out = []
    d = blob(cx, cy, R, R * 0.97, rng, n=40, amp=0.022, a0=rng.uniform(0, 3))
    # under-tortilla sliver (street tacos come doubled)
    d2 = blob(cx + 5, cy + 6, R * 0.995, R * 0.965, rng, n=40, amp=0.025, a0=rng.uniform(0, 3))
    out.append(s.shadow(d2, 18, 22, 5, 0.36, "#4a2c08"))
    out.append(s.shadow(d2, 4, 5, 3, 0.3, "#3a2005"))
    out.append(f'<path d="{d2}" fill="#E2C285"/>')
    g = s.rad(cx - R * 0.25, cy - R * 0.3, R * 1.25, [(0, "#FAE8B6"), (0.55, "#F4D99A"), (0.85, "#E9C27C"), (1, "#D6A55A")])
    tex = s.texture(freq=0.04, scale=1.2, seed=seed, spec=0.0, gain=1.3, octaves=3, blot=0.35, blot_freq=0.02,
                    blot_col=(0.86, 0.7, 0.42))
    out.append(f'<g filter="{tex}"><path d="{d}" fill="{g}"/></g>')
    cl = s.clip(d)
    # toasted leopard spots from thresholded noise
    fid = s.uid("ts")
    s.d(f'<filter id="{fid}" x="-5%" y="-5%" width="110%" height="110%" color-interpolation-filters="sRGB">'
        f'<feTurbulence type="fractalNoise" baseFrequency="0.045" numOctaves="4" seed="{seed+9}" result="n"/>'
        f'<feColorMatrix in="n" type="matrix" values="0 0 0 0 0.62 0 0 0 0 0.36 0 0 0 0 0.12 0 0 0 -10 3.7" result="sp"/>'
        f'<feTurbulence type="fractalNoise" baseFrequency="0.11" numOctaves="3" seed="{seed+19}" result="n2"/>'
        f'<feColorMatrix in="n2" type="matrix" values="0 0 0 0 0.3 0 0 0 0 0.14 0 0 0 0 0.05 0 0 0 -14 4.3" result="sp2"/>'
        f'<feMerge><feMergeNode in="sp"/><feMergeNode in="sp2"/></feMerge>'
        f'<feComposite in2="SourceAlpha" operator="in"/>'
        f'</filter>')
    out.append(f'<g clip-path="{cl}"><path d="{d}" fill="#000" filter="url(#{fid})" opacity="0.75"/>')
    # masa flecks
    fl = []
    for _ in range(int(R * R / 60)):
        a = rng.uniform(0, 2 * math.pi); t = math.sqrt(rng.random()) * R
        fl.append(poly(cx + math.cos(a) * t, cy + math.sin(a) * t, rng.uniform(0.6, 1.5), rng))
    out.append(f'<path d="{"".join(fl)}" fill="#A47A3E" opacity="0.45"/>')
    # gently lifted rim
    out.append(f'<path d="{d}" fill="none" stroke="#fff6dc" stroke-width="6" opacity="0.5" transform="translate(3,3)" filter="{s.blur(2.5)}"/>')
    out.append(f'<path d="{d}" fill="none" stroke="#8a5a20" stroke-width="8" opacity="0.25" transform="translate(-4,-4)" filter="{s.blur(3)}"/>')
    out.append('</g>')
    return "".join(out), d


def beef(s, cx, cy, R, rng, seed):
    """Crumbly seasoned ground beef: granular bump-lit mass with loose crumbles at the edge."""
    out = []
    pts = blob_pts(cx, cy, R, R * 0.93, rng, n=34, amp=0.07, jitter=0.03, a0=rng.uniform(0, 3))
    md = smooth_closed(pts)
    # loose crumbles breaking the silhouette
    bits = []
    for _ in range(46):
        a = rng.uniform(0, 2 * math.pi); t = R * rng.uniform(0.9, 1.1)
        bits.append(blob(cx + math.cos(a) * t, cy + math.sin(a) * t * 0.93, rng.uniform(4, 9), rng.uniform(3.5, 7), rng, n=7, amp=0.25, a0=rng.uniform(0, 3)))
    allp = md + "".join(bits)
    out.append(f'<path d="{allp}" fill="#2a1003" opacity="0.55" transform="translate(7,9)" filter="{s.blur(5)}"/>')
    out.append(f'<path d="{allp}" fill="#1c0802" opacity="0.5" transform="translate(2,3)" filter="{s.blur(1.5)}"/>')
    g = s.rad(cx - R * 0.25, cy - R * 0.3, R * 1.35, [(0, "#C46E42"), (0.4, "#A65632"), (0.75, "#824022"), (1, "#5A2612")])
    tex = s.texture(freq=0.08, scale=3.4, seed=50 + seed, spec=0.18, spec_exp=14, blot=0.6, blot_freq=0.035,
                    blot_col=(0.45, 0.12, 0.05), gain=1.3, octaves=2, table="0 0 0.2 0.75 1 1", spec_elev=36)
    out.append(f'<g filter="{tex}"><path d="{allp}" fill="{g}"/></g>')
    # distinct crumbles on top
    gids = []
    for (a, b, c) in [("#C77548", "#93462A", "#4E1E0C"), ("#B5603A", "#7E3820", "#3E1608"), ("#A8542F", "#6A2C14", "#331104")]:
        gid = s.uid("bf")
        s.d(f'<radialGradient id="{gid}" cx="0.35" cy="0.32" r="0.8"><stop offset="0" stop-color="{a}"/><stop offset="0.55" stop-color="{b}"/><stop offset="1" stop-color="{c}"/></radialGradient>')
        gids.append(gid)
    cr, crs = [], []
    for _ in range(int(R * 0.9)):
        a = rng.uniform(0, 2 * math.pi); tt = math.sqrt(rng.random()) * R * 0.92
        x, y = cx + math.cos(a) * tt, cy + math.sin(a) * tt
        sz = rng.uniform(3.5, 7.5)
        p = blob(x, y, sz, sz * rng.uniform(0.6, 0.95), rng, n=7, amp=0.25, a0=rng.uniform(0, 3))
        cr.append(f'<path d="{p}" fill="url(#{gids[rng.randrange(3)]})"/>')
        crs.append(p)
    out.append(f'<path d="{"".join(crs)}" fill="#1a0702" opacity="0.55" transform="translate(2,2.6)" filter="{s.blur(1.3)}"/>')
    out.append("".join(cr))
    # crisp browned bits and specks of chili seasoning
    cl = s.clip(md)
    sp = {("#3A1406", 0.6): [], ("#C4703E", 0.55): [], ("#8E2A10", 0.5): []}
    keys = list(sp.keys())
    for _ in range(int(R * 1.6)):
        a = rng.uniform(0, 2 * math.pi); tt = math.sqrt(rng.random()) * R
        sp[keys[rng.randrange(3)]].append(poly(cx + math.cos(a) * tt, cy + math.sin(a) * tt, rng.uniform(1.2, 3.2), rng))
    out.append(f'<g clip-path="{cl}">{specks(sp)}</g>')
    return "".join(out)


def cilantro(s, pts_fn, n, rng):
    """Chopped cilantro: scalloped leaf pieces and a few fine flecks."""
    leaves = {"#2E7A20": [], "#46A030": [], "#62B83E": [], "#22621A": []}
    keys = list(leaves.keys())
    sh, veins, hi = [], [], []
    for _ in range(n):
        x, y = pts_fn()
        sz = rng.uniform(12, 20)
        a = rng.uniform(0, 2 * math.pi)
        # leaf with 3 rounded, toothed lobes
        pts = []
        m = 18
        for i in range(m):
            th = 2 * math.pi * i / m
            lobe = 0.62 + 0.38 * abs(math.cos(1.5 * th)) ** 0.7
            tooth = 1 + 0.08 * math.cos(9 * th)
            r = sz * 0.55 * lobe * tooth * (0.75 if math.cos(th) < -0.6 else 1.0)
            p = rot((math.cos(th) * r, math.sin(th) * r * 0.9), a)
            pts.append((x + p[0], y + p[1]))
        d = smooth_closed(pts)
        leaves[keys[rng.randrange(4)]].append(d)
        sh.append(d)
        for k in (-1, 0, 1):
            la = a + k * 1.05
            veins.append(f"M{f(x - math.cos(a)*sz*0.2)},{f(y - math.sin(a)*sz*0.2)}L{f(x+math.cos(la)*sz*0.42)},{f(y+math.sin(la)*sz*0.42)}")
        hp = rot((-sz * 0.15, -sz * 0.2), 0)
        hi.append(f"M{f(x-sz*0.3)},{f(y-sz*0.05)}Q{f(x-sz*0.25)},{f(y-sz*0.3)} {f(x)},{f(y-sz*0.33)}")
    out = [f'<g fill="#0b2405" opacity="0.45" transform="translate(2.5,3.5)" filter="{s.blur(1.6)}"><path d="{"".join(sh)}"/></g>']
    for col, ds in leaves.items():
        out.append(f'<path d="{"".join(ds)}" fill="{col}"/>')
    out.append(f'<path d="{"".join(veins)}" stroke="#9FD27C" stroke-width="0.9" opacity="0.6" fill="none"/>')
    out.append(f'<path d="{"".join(hi)}" stroke="#E6F7C8" stroke-width="1.2" opacity="0.45" fill="none" stroke-linecap="round"/>')
    fl = []
    for _ in range(n):
        x, y = pts_fn()
        fl.append(poly(x, y, rng.uniform(1.2, 2.6), rng))
    out.append(f'<path d="{"".join(fl)}" fill="#3C8C2A" opacity="0.9"/>')
    return "".join(out)


def salsa(s, cx, cy, R, rng):
    """A spoonful of red salsa: flat glossy puddle with tomato, onion and chili flecks."""
    out = []
    d = blob(cx, cy, R, R * 0.8, rng, n=26, amp=0.2, harm=(2, 3, 4, 6), a0=rng.uniform(0, 3))
    out.append(f'<path d="{d}" fill="#2a0300" opacity="0.35" transform="translate(3,4)" filter="{s.blur(2.5)}"/>')
    g = s.rad(cx - R * 0.3, cy - R * 0.35, R * 1.4, [(0, "#C83A22"), (0.5, "#A8241A"), (1, "#7A1A10")])
    out.append(f'<path d="{d}" fill="{g}" opacity="0.92" filter="{s.blur(0.8)}"/>')
    cl = s.clip(d)
    out.append(f'<g clip-path="{cl}">')
    out.append(f'<path d="{d}" fill="none" stroke="#5e0c05" stroke-width="{f(R*0.35)}" opacity="0.45" transform="translate({f(R*0.15)},{f(R*0.18)})" filter="{s.blur(R*0.12)}"/>')
    chunks = []
    for _ in range(int(R * 0.7)):
        a = rng.uniform(0, 2 * math.pi); tt = math.sqrt(rng.random()) * R * 0.8
        x, y = cx + math.cos(a) * tt, cy + math.sin(a) * tt
        sz = rng.uniform(2.5, 5.5)
        dd = poly(x, y, sz, rng, 4, 6)
        col = ["#E0503A", "#C8301E", "#9C1C10"][rng.randrange(3)]
        chunks.append(f'<path d="{dd}" fill="{col}"/>')
    out.append("".join(chunks))
    bits = {("#F4EBDA", 0.9): [], ("#EAC27A", 0.8): [], ("#2E7A20", 0.85): [], ("#3a0602", 0.6): []}
    keys = list(bits.keys())
    for _ in range(int(R * 1.2)):
        a = rng.uniform(0, 2 * math.pi); tt = math.sqrt(rng.random()) * R * 0.85
        k = keys[min(3, int(rng.random() ** 1.3 * 4))]
        bits[k].append(poly(cx + math.cos(a) * tt, cy + math.sin(a) * tt, rng.uniform(1.0, 2.4), rng, 4, 6))
    out.append(specks(bits))
    hl = []
    for _ in range(5):
        a = rng.uniform(math.pi, 1.6 * math.pi); tt = R * rng.uniform(0.35, 0.65)
        x, y = cx + math.cos(a) * tt, cy + math.sin(a) * tt
        hl.append(f'M{f(x-4)},{f(y+1)}Q{f(x)},{f(y-3)} {f(x+5)},{f(y-2)}')
    out.append(f'<path d="{"".join(hl)}" stroke="#fff" stroke-width="1.8" fill="none" stroke-linecap="round" opacity="0.8"/>')
    out.append('</g>')
    return "".join(out)


def lime_wedge(s, cx, cy, R, ang, rng):
    """Lime wedge lying on its side, flesh up: half-moon with rind, pith and radiating segments."""
    a = math.radians(ang)
    out = []
    def P(u, v):
        p = rot((u, v), a)
        return (cx + p[0], cy + p[1])
    def half(kx, ky, n=28):
        pts = [P(math.cos(math.pi * i / n) * R * kx, -math.sin(math.pi * i / n) * R * ky) for i in range(n + 1)]
        return "M" + "L".join(f"{f(x)},{f(y)}" for x, y in pts) + "Z"
    d = half(1.0, 0.9)
    out.append(s.shadow(d, 14, 18, 6, 0.35, "#4a2c08"))
    rg = s.lin(*P(-R * 0.4, -R), *P(R * 0.3, R * 0.1), [(0, "#7DB33E"), (0.5, "#4E8C22"), (1, "#2F6614")])
    out.append(f'<path d="{d}" fill="{rg}"/>')
    pores = []
    for _ in range(40):
        tt = rng.uniform(0.05, math.pi - 0.05); q = P(math.cos(tt) * R * 0.96, -math.sin(tt) * R * 0.9 * 0.96)
        pores.append(poly(q[0], q[1], rng.uniform(0.6, 1.3), rng))
    out.append(f'<path d="{"".join(pores)}" fill="#C8E68A" opacity="0.6"/>')
    out.append(f'<path d="{half(0.93, 0.83)}" fill="#F3F5D6"/>')
    d3 = half(0.87, 0.77)
    fg = s.rad(*P(-R * 0.2, -R * 0.4), R * 1.0, [(0, "#F2FBB8"), (0.55, "#D7EC7A"), (1, "#B5D24C")])
    out.append(f'<path d="{d3}" fill="{fg}"/>')
    cl = s.clip(d3)
    seg = []
    for i in range(1, 7):
        tt = math.pi * i / 7
        q0 = P(0, -R * 0.02); q1 = P(math.cos(tt) * R, -math.sin(tt) * R)
        seg.append(f"M{f(q0[0])},{f(q0[1])}L{f(q1[0])},{f(q1[1])}")
    out.append(f'<g clip-path="{cl}"><path d="{"".join(seg)}" stroke="#F4FAD6" stroke-width="3" opacity="0.85"/>')
    ves = []
    for _ in range(80):
        tt = rng.uniform(0.05, math.pi - 0.05); rr = rng.uniform(0.15, 0.85)
        q = P(math.cos(tt) * R * rr, -math.sin(tt) * R * rr * 0.88)
        ves.append(f'<ellipse cx="{f(q[0])}" cy="{f(q[1])}" rx="{f(rng.uniform(2,4.5))}" ry="{f(rng.uniform(1,2))}" transform="rotate({f(math.degrees(-tt)+90+ang)} {f(q[0])} {f(q[1])})"/>')
    out.append(f'<g fill="#F9FFD8" opacity="0.5">{"".join(ves)}</g>')
    q = P(-R * 0.35, -R * 0.45)
    out.append(f'<ellipse cx="{f(q[0])}" cy="{f(q[1])}" rx="{f(R*0.25)}" ry="{f(R*0.09)}" fill="#fff" opacity="0.55" transform="rotate({f(ang-35)} {f(q[0])} {f(q[1])})"/>')
    # central pith core at the base
    q = P(0, -R * 0.03)
    out.append(f'<ellipse cx="{f(q[0])}" cy="{f(q[1])}" rx="{f(R*0.12)}" ry="{f(R*0.05)}" fill="#F5F7DE" opacity="0.9" transform="rotate({f(ang)} {f(q[0])} {f(q[1])})"/>')
    out.append('</g>')
    return "".join(out)


def dish_gt():
    s = Svg(); rng = random.Random(707)
    s.add('<rect width="1400" height="800" fill="#F6E7C8"/>')
    # warm light falloff on the background
    bgl = s.rad(380, 120, 1300, [(0, "#FFF5E0", 0.55), (1, "#E8D2A6", 0.0)])
    s.add(f'<rect width="1400" height="800" fill="{bgl}"/>')
    bgt = s.texture(freq=0.6, scale=0.7, seed=5, spec=0, gain=1.3, octaves=2, region='x="0" y="0" width="100%" height="100%"')
    s.add(f'<rect width="1400" height="800" fill="#F6E7C8" filter="{bgt}" opacity="0.35" style="mix-blend-mode:multiply"/>')
    # brush smears: hot pink left, lime right
    pl = [(250 - 150 * (i / 51) ** 1.3 + 30 * math.sin(i / 8), 50 + i * 12.5) for i in range(52)]
    s.add(brush_smear(s, pl, 78, "#E6246E", rng, 11))
    pr = [(1170 + 160 * (i / 51) ** 1.2 - 25 * math.sin(i / 9), 80 + i * 12.5) for i in range(52)]
    s.add(brush_smear(s, pr, 74, "#B5D334", rng, 23))
    # speckled stone plate
    s.add(stone_plate(s, 700, 405, 860, 650, -3, rng))
    # chili dust on the plate
    dust = []
    for _ in range(380):
        x = rng.gauss(700, 300); y = rng.gauss(405, 220)
        if 300 < x < 1100 and 110 < y < 700:
            dust.append(poly(x, y, rng.uniform(0.6, 1.8), rng))
    s.add(f'<path d="{"".join(dust)}" fill="#A8441C" opacity="0.6"/>')
    # three tacos
    R = 152
    tacos = [(548, 292), (858, 300), (700, 548)]
    for k in range(3):
        x, y = tacos[k]
        m, d = tortilla(s, x, y, R, rng, seed=31 + k * 7)
        s.add(m)
        bx, by = x + 3, y + 2
        s.add(beef(s, bx, by, R * 0.64, rng, k))
        def on_top(cx=bx, cy=by):
            a = rng.uniform(0, 2 * math.pi); t = math.sqrt(rng.random()) * R * 0.6
            return (cx + math.cos(a) * t, cy + math.sin(a) * t)
        s.add(food.onion_cubes(s, on_top, 30, rng, size=(7, 10)))
        # two spoonfuls of salsa
        sa = rng.uniform(0, 2 * math.pi)
        for j in range(2):
            aa = sa + j * math.pi * 0.9
            s.add(salsa(s, bx + math.cos(aa) * R * 0.28, by + math.sin(aa) * R * 0.28, R * 0.25, rng))
        s.add(cilantro(s, on_top, 24, rng))
    s.add(lime_wedge(s, 990, 598, 70, -28, rng))
    # a pinch of chili dust over the tacos, and a warm sunlit grade
    dust = []
    for _ in range(160):
        x, y = tacos[rng.randrange(3)]
        a = rng.uniform(0, 2 * math.pi); tt = rng.uniform(0.7, 1.15) * R
        dust.append(poly(x + math.cos(a) * tt, y + math.sin(a) * tt, rng.uniform(0.6, 1.6), rng))
    s.add(f'<path d="{"".join(dust)}" fill="#9C3A16" opacity="0.65"/>')
    s.add('<rect width="1400" height="800" fill="#FF9A3C" opacity="0.10" style="mix-blend-mode:soft-light"/>')
    s.finish(grain=0.05, vignette=0.14)
    return s


if __name__ == "__main__":
    os.makedirs(os.path.dirname(SVG), exist_ok=True)
    s = dish_gt()
    open(SVG, "w").write(s.render())
    q = sys.argv[sys.argv.index("--quality") + 1] if "--quality" in sys.argv else "80"
    subprocess.run(["python3", RENDER, SVG, OUT, "1400", "800", "--quality", q], check=True)
