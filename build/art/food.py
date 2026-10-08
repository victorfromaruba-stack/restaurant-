"""Reusable food pieces for the Oranje Snack illustrations."""
import math, random
from artlib import f, rot, smooth_closed, smooth_open, blob, blob_pts, poly, mix, specks, stadium_pts

CRUMB_LIGHT = "#F7D58E"
CRUMB_MID = "#C47D2C"
CRUMB_DARK = "#6E3810"


CRUMB = dict(freq=0.4, scale=1.25, seed=11, spec=0.22, spec_exp=14, blot=0.35, blot_freq=0.06,
             blot_col=(0.62, 0.30, 0.07), gain=1.3, octaves=2, table="0 0 0 0.6 1 1")


def crumb_tex(s):
    return s.texture(**CRUMB)


def fried_ball(s, cx, cy, r, rng, sd_layer=None):
    """Breaded deep-fried ball (bitterbal). Returns (body markup, shadow path d)."""
    out = []
    pts = blob_pts(cx, cy, r, r, rng, n=44, amp=0.03, jitter=0.006)
    d = smooth_closed(pts)
    g = s.rad(cx - r * 0.34, cy - r * 0.38, r * 1.5,
              [(0, "#F7C873"), (0.2, "#E9A64A"), (0.46, "#C9792A"), (0.72, "#954C17"), (0.9, "#62300C"), (1, "#4A230A")])
    tex = crumb_tex(s)
    # crumb bits sticking out of the silhouette
    bits = []
    for _ in range(26):
        a = rng.uniform(0, 2 * math.pi)
        rr_ = r * rng.uniform(0.95, 1.02)
        bits.append(poly(cx + math.cos(a) * rr_, cy + math.sin(a) * rr_, rng.uniform(2.0, 4.0), rng, 4, 6))
    out.append(f'<g filter="{tex}"><path d="{d}{"".join(bits)}" fill="{g}"/></g>')
    cl = s.clip(d)
    # limb darkening: the texture rolls away into shade at the bottom-right edge
    lg = s.rad(cx - r * 0.22, cy - r * 0.26, r * 1.28, [(0, "#2a1203", 0), (0.58, "#2a1203", 0), (0.82, "#2a1203", 0.32), (1, "#2a1203", 0.72)])
    out.append(f'<g clip-path="{cl}"><path d="{d}" fill="{lg}"/>')
    # specks: a few light crumbs on the lit side, dark ones in the shade
    grp = {(CRUMB_LIGHT, 0.55): [], ("#FFF0C8", 0.5): [], (CRUMB_DARK, 0.35): [], ("#3E1D07", 0.3): []}
    for _ in range(int(r * 0.7)):
        a = rng.uniform(0, 2 * math.pi); t = math.sqrt(rng.random()) * r * 0.95
        x, y = cx + math.cos(a) * t, cy + math.sin(a) * t
        lit = ((x - cx) * -0.707 + (y - cy) * -0.707) / r  # +1 toward light
        if rng.random() < 0.5 + 0.4 * lit:
            key = (CRUMB_LIGHT, 0.55) if rng.random() < 0.75 else ("#FFF0C8", 0.5)
        else:
            key = (CRUMB_DARK, 0.35) if rng.random() < 0.7 else ("#3E1D07", 0.3)
        grp[key].append(poly(x, y, rng.uniform(0.9, 2.2), rng))
    out.append(specks(grp))
    # broad soft light on the lit shoulder + tiny oil glints
    hx, hy = cx - r * 0.36, cy - r * 0.4
    hg = s.rad(hx, hy, r * 0.55, [(0, "#FFEFC8", 0.3), (1, "#FFEFC8", 0)])
    out.append(f'<circle cx="{f(hx)}" cy="{f(hy)}" r="{f(r*0.55)}" fill="{hg}"/>')
    gl = []
    for _ in range(14):
        a = rng.uniform(0, 2 * math.pi); t = math.sqrt(rng.random()) * r * 0.3
        gl.append(poly(hx + math.cos(a) * t, hy + math.sin(a) * t, rng.uniform(0.7, 1.5), rng))
    out.append(f'<path d="{"".join(gl)}" fill="#ffffff" opacity="0.75"/>')
    # warm bounce light from the white tray on the lower-right rim
    out.append(f'<path d="M{f(cx+r*0.98)},{f(cy+r*0.05)}A{f(r)},{f(r)} 0 0 1 {f(cx+r*0.05)},{f(cy+r*0.98)}A{f(r*1.12)},{f(r*1.12)} 0 0 0 {f(cx+r*0.98)},{f(cy+r*0.05)}Z" fill="#FFD9A0" opacity="0.22" filter="{s.blur(2)}"/>')
    out.append('</g>')
    return "".join(out), d


def ball_shadows(s, items):
    """items: list of (cx, cy, r, d). Contact + cast shadows for round fried items."""
    cast, contact = [], []
    for cx, cy, r, d in items:
        cast.append(f'<ellipse cx="{f(cx+r*0.32)}" cy="{f(cy+r*0.36)}" rx="{f(r*0.98)}" ry="{f(r*0.94)}"/>')
        contact.append(f'<ellipse cx="{f(cx+r*0.12)}" cy="{f(cy+r*0.14)}" rx="{f(r*0.9)}" ry="{f(r*0.88)}"/>')
    return (f'<g filter="{s.blur(13)}" opacity="0.38">{"".join(cast)}</g>'
            f'<g filter="{s.blur(4)}" opacity="0.55">{"".join(contact)}</g>')


def log_shadow(s, cx, cy, length, dia, ang_deg):
    ang = math.radians(ang_deg)
    pts = stadium_pts(cx + dia * 0.22, cy + dia * 0.28, length, dia, ang)
    pts2 = stadium_pts(cx + dia * 0.07, cy + dia * 0.09, length * 0.97, dia * 0.88, ang)
    d = "M" + "L".join(f"{f(x)},{f(y)}" for x, y in pts) + "Z"
    d2 = "M" + "L".join(f"{f(x)},{f(y)}" for x, y in pts2) + "Z"
    return (f'<g filter="{s.blur(12)}" opacity="0.4"><path d="{d}"/></g>'
            f'<g filter="{s.blur(4)}" opacity="0.55"><path d="{d2}"/></g>')


def fried_log(s, cx, cy, length, dia, ang_deg, rng, flat_end=None):
    """Breaded croquette lying on its side. Returns (markup, outline d)."""
    a = math.radians(ang_deg)
    pts = stadium_pts(cx, cy, length, dia, a, rng, n_side=14, n_cap=12, amp=dia * 0.012, flat_end=flat_end)
    d = smooth_closed(pts)
    r = dia / 2
    # across-the-log shading (light side faces top-left)
    nx, ny = rot((0, -1), a)
    if nx * -0.707 + ny * -0.707 < 0:
        nx, ny = -nx, -ny
    A = (cx + nx * r * 1.05, cy + ny * r * 1.05); B = (cx - nx * r * 1.05, cy - ny * r * 1.05)
    g = s.lin(A[0], A[1], B[0], B[1], [(0, "#B5671F"), (0.12, "#F2B65C"), (0.28, "#E59C3E"), (0.55, "#BD6C22"), (0.8, "#8A4413"), (1, "#4A2005")])
    tex = crumb_tex(s)
    bits = []
    for i in range(int(length / 9)):
        p = pts[rng.randrange(len(pts))]
        bits.append(poly(p[0], p[1], rng.uniform(2.5, 5.0), rng, 4, 6))
    out = [f'<g filter="{tex}"><path d="{d}{"".join(bits)}" fill="{g}"/></g>']
    cl = s.clip(d)
    # end caps darker (along the axis): overlay
    ex, ey = math.cos(a), math.sin(a)
    hl = length / 2
    E0 = (cx - ex * hl, cy - ey * hl); E1 = (cx + ex * hl, cy + ey * hl)
    eg = s.lin(E0[0], E0[1], E1[0], E1[1], [(0, "#4a2208", 0.38), (0.12, "#4a2208", 0.0), (0.88, "#4a2208", 0.0), (1, "#4a2208", 0.5)])
    out.append(f'<g clip-path="{cl}"><path d="{d}" fill="{eg}"/>')
    grp = {(CRUMB_LIGHT, 0.5): [], ("#FBE7B5", 0.4): [], (CRUMB_MID, 0.4): [], (CRUMB_DARK, 0.35): [], ("#3E1D07", 0.3): []}
    area = length * dia
    sgn = 1 if (rot((0, -1), a)[0] * -0.707 + rot((0, -1), a)[1] * -0.707) >= 0 else -1
    for _ in range(int(area / 110)):
        u = rng.uniform(-hl, hl); v = rng.uniform(-r, r)
        p = rot((u, v), a)
        x, y = cx + p[0], cy + p[1]
        lit = -(v * sgn) / r
        q = rng.random()
        if q < 0.42 + 0.3 * lit:
            key = (CRUMB_LIGHT, 0.5) if rng.random() < 0.7 else ("#FBE7B5", 0.4)
        elif q < 0.75:
            key = (CRUMB_MID, 0.4)
        else:
            key = (CRUMB_DARK, 0.35) if rng.random() < 0.7 else ("#3E1D07", 0.3)
        grp[key].append(poly(x, y, rng.uniform(1.0, 2.6), rng))
    out.append(specks(grp))
    # long soft sheen along the lit side
    S0 = (cx - ex * hl * 0.7 + nx * r * 0.45, cy - ey * hl * 0.7 + ny * r * 0.45)
    S1 = (cx + ex * hl * 0.55 + nx * r * 0.45, cy + ey * hl * 0.55 + ny * r * 0.45)
    out.append(f'<path d="M{f(S0[0])},{f(S0[1])}L{f(S1[0])},{f(S1[1])}" stroke="#FFF3D6" stroke-width="{f(r*0.32)}" stroke-linecap="round" opacity="0.22" filter="{s.blur(5)}"/>')
    out.append('</g>')
    return "".join(out), d


def ragout_face(s, cx, cy, rx, ry, ang_deg, rng):
    """The cut face of a croquette: thin crumb crust ring around creamy beef ragout."""
    out = []
    a = math.radians(ang_deg)
    d = blob(cx, cy, rx, ry, rng, n=36, amp=0.025, a0=a)
    # crust ring
    cg = s.rad(cx - rx * 0.3, cy - ry * 0.3, max(rx, ry) * 1.3, [(0, "#E2A552"), (0.7, "#B26C27"), (1, "#7A4216")])
    tex = crumb_tex(s)
    out.append(f'<g filter="{tex}"><path d="{d}" fill="{cg}"/></g>')
    k = 0.86
    di = blob(cx, cy, rx * k, ry * k, rng, n=36, amp=0.02, a0=a)
    ig = s.rad(cx - rx * 0.25, cy - ry * 0.3, max(rx, ry) * 1.0, [(0, "#F0D4A0"), (0.45, "#DDB477"), (0.85, "#C4935A"), (1, "#A2723C")])
    mtex = s.texture(freq=0.06, scale=1.6, seed=5, spec=0.6, spec_exp=20, gain=1.3, elev=55, octaves=2)
    out.append(f'<g filter="{mtex}"><path d="{di}" fill="{ig}"/></g>')
    cl = s.clip(di)
    # beef shreds: short curved fibres in browns
    fib = {("#6E3E1C", 0.7): [], ("#94592B", 0.6): [], ("#FBEBCB", 0.45): []}
    for _ in range(int(rx * ry / 48)):
        t = math.sqrt(rng.random()) * 0.9; th = rng.uniform(0, 2 * math.pi)
        px, py = cx + math.cos(th) * rx * k * t, cy + math.sin(th) * ry * k * t
        L = rng.uniform(4, 9); fa = rng.uniform(0, math.pi)
        q = rng.random()
        key = list(fib.keys())[0 if q < 0.45 else (1 if q < 0.8 else 2)]
        fib[key].append(poly(px, py, L * 0.5, rng, 4, 6, stretch=2.2, ang=fa))
    out.append(f'<g clip-path="{cl}">{specks(fib)}')
    # darker rim inside crust
    out.append(f'<path d="{di}" fill="none" stroke="#9C7040" stroke-width="5" opacity="0.35" filter="{s.blur(2)}"/>')
    # gloss
    out.append(f'<ellipse cx="{f(cx-rx*0.3)}" cy="{f(cy-ry*0.32)}" rx="{f(rx*0.28)}" ry="{f(ry*0.14)}" fill="#ffffff" opacity="0.35" transform="rotate({f(ang_deg-30)} {f(cx-rx*0.3)} {f(cy-ry*0.32)})" filter="{s.blur(3)}"/>')
    out.append('</g>')
    return "".join(out), d


def sauce_dot(s, cx, cy, r, col, hi, lo, rng, shadow=True, peak=True):
    """A small piped dot of creamy sauce: flat top, thick rounded edge, soft satin sheen."""
    out = []
    d = blob(cx, cy, r, r * rng.uniform(0.9, 1.0), rng, n=18, amp=0.05, a0=rng.uniform(0, 3))
    if shadow:
        out.append(f'<path d="{d}" fill="#3a2200" opacity="0.32" transform="translate({f(r*0.16)},{f(r*0.2)})" filter="{s.blur(max(1.2, r*0.15))}"/>')
    out.append(f'<path d="{d}" fill="{col}"/>')
    cl = s.clip(d)
    out.append(f'<g clip-path="{cl}">')
    # thickness: darker lower-right inner edge, light upper-left edge
    out.append(f'<path d="{d}" fill="none" stroke="{lo}" stroke-width="{f(r*0.55)}" opacity="0.75" transform="translate({f(r*0.2)},{f(r*0.24)})" filter="{s.blur(r*0.18)}"/>')
    out.append(f'<path d="{d}" fill="none" stroke="{hi}" stroke-width="{f(r*0.4)}" opacity="0.9" transform="translate({f(-r*0.16)},{f(-r*0.2)})" filter="{s.blur(r*0.14)}"/>')
    if peak:
        # the little piped peak, offset toward the light
        px, py = cx + r * 0.05, cy - r * 0.02
        out.append(f'<circle cx="{f(px+r*0.08)}" cy="{f(py+r*0.1)}" r="{f(r*0.3)}" fill="{lo}" opacity="0.45" filter="{s.blur(r*0.1)}"/>')
        out.append(f'<circle cx="{f(px)}" cy="{f(py)}" r="{f(r*0.26)}" fill="{hi}" opacity="0.95"/>')
    out.append(f'<ellipse cx="{f(cx-r*0.35)}" cy="{f(cy-r*0.38)}" rx="{f(r*0.24)}" ry="{f(r*0.12)}" fill="#ffffff" opacity="0.55" transform="rotate(-35 {f(cx-r*0.35)} {f(cy-r*0.38)})" filter="{s.blur(max(0.5, r*0.05))}"/>')
    out.append('</g>')
    return "".join(out)


def parsley(s, pts_fn, n, rng, size=(1.8, 4.6)):
    """Finely chopped parsley flecks. pts_fn() -> (x, y) sample location."""
    grp = {("#3A7F22", 0.95): [], ("#55A82E", 0.95): [], ("#86C84E", 0.9): [], ("#24561A", 0.9): []}
    keys = list(grp.keys())
    sh = []
    for _ in range(n):
        x, y = pts_fn()
        sz = rng.uniform(*size)
        k = keys[min(3, int(rng.random() ** 1.3 * 4))]
        p = poly(x, y, sz, rng, 4, 7, stretch=rng.uniform(1.0, 1.8))
        grp[k].append(p)
        sh.append(p)
    return (f'<path d="{"".join(sh)}" fill="#000" opacity="0.25" transform="translate(1.2,1.6)"/>' + specks(grp))


def onion_cubes(s, pts_fn, n, rng, size=(6, 10)):
    """Small diced raw white onion cubes."""
    top, side, shade, hi, layer = [], [], [], [], []
    for _ in range(n):
        x, y = pts_fn()
        sz = rng.uniform(*size) * (1 if rng.random() < 0.7 else 0.7)
        a = rng.uniform(0, math.pi / 2)
        sq = [rot((dx * sz / 2 + rng.uniform(-0.8, 0.8), dy * sz / 2 + rng.uniform(-0.8, 0.8)), a) for dx, dy in [(-1, -1), (1, -1), (1, 1), (-1, 1)]]
        P = [(x + px, y + py) for px, py in sq]
        dd = "M" + "L".join(f"{f(px)},{f(py)}" for px, py in P) + "Z"
        shade.append(dd)
        top.append(dd)
        # visible side faces toward bottom-right (a sliver)
        k = sz * 0.22
        side.append("M" + "L".join(f"{f(px)},{f(py)}" for px, py in [P[1], P[2], (P[2][0] + k, P[2][1] + k), (P[1][0] + k, P[1][1] + k)]) + "Z")
        side.append("M" + "L".join(f"{f(px)},{f(py)}" for px, py in [P[2], P[3], (P[3][0] + k, P[3][1] + k), (P[2][0] + k, P[2][1] + k)]) + "Z")
        hi.append(f"M{f(P[0][0]+1)},{f(P[0][1]+1)}L{f(P[1][0])},{f(P[1][1]+1)}")
        if rng.random() < 0.6:
            m0 = ((P[0][0] + P[3][0]) / 2, (P[0][1] + P[3][1]) / 2); m1 = ((P[1][0] + P[2][0]) / 2, (P[1][1] + P[2][1]) / 2)
            cx_, cy_ = (m0[0] + m1[0]) / 2 + rng.uniform(-2, 2), (m0[1] + m1[1]) / 2 + rng.uniform(-2, 2)
            layer.append(f"M{f(m0[0])},{f(m0[1])}Q{f(cx_)},{f(cy_)} {f(m1[0])},{f(m1[1])}")
    return (f'<path d="{"".join(shade)}" fill="#000" opacity="0.28" transform="translate(2.5,3)" filter="{s.blur(1.5)}"/>'
            f'<path d="{"".join(side)}" fill="#D9D6CF"/>'
            f'<path d="{"".join(top)}" fill="#F6F5EC" opacity="0.95"/>'
            f'<path d="{"".join(top)}" fill="#E2E6CF" opacity="0.5" transform="translate(1.5,1.5) scale(1)"/>'
            f'<path d="{"".join(layer)}" stroke="#D6D9C2" stroke-width="1" fill="none" opacity="0.9"/>'
            f'<path d="{"".join(hi)}" stroke="#ffffff" stroke-width="1.4" fill="none" opacity="0.9"/>')


def stroke_band(cpts, widths, rng, wob=0.0):
    """Polygon around a centreline polyline with per-point half widths. Returns path d."""
    left, right = [], []
    n = len(cpts)
    for i, (x, y) in enumerate(cpts):
        x0, y0 = cpts[max(i - 1, 0)]; x1, y1 = cpts[min(i + 1, n - 1)]
        tx, ty = x1 - x0, y1 - y0
        L = math.hypot(tx, ty) or 1
        nx, ny = -ty / L, tx / L
        w = widths[i] * (1 + rng.uniform(-wob, wob))
        left.append((x + nx * w, y + ny * w)); right.append((x - nx * w, y - ny * w))
    pts = left + right[::-1]
    return smooth_closed(pts)


def mustard_smear(s, p0, p1, p2, width, rng, col="#D6A02A", hi="#F0C95C", lo="#A8761A", floor="#EFE7DA"):
    """A spoon-dragged swoosh of mustard: thick rounded head at p0, thinning tail to p2,
    with the groove the spoon leaves through the middle."""
    out = []
    N = 48
    c = []
    for i in range(N):
        t = i / (N - 1)
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]
        c.append((x, y))
    ph1, ph2 = rng.uniform(0, 6), rng.uniform(0, 6)
    left, right = [], []
    for i in range(N):
        t = i / (N - 1)
        w = width * (1 - 0.8 * t ** 1.3)
        if t < 0.08:
            w *= math.sqrt(max(0.05, 1 - ((0.08 - t) / 0.08) ** 2))
        x, y = c[i]
        x0, y0 = c[max(i - 1, 0)]; x1, y1 = c[min(i + 1, N - 1)]
        tx, ty = x1 - x0, y1 - y0; L = math.hypot(tx, ty) or 1
        nx, ny = -ty / L, tx / L
        wl = w * (1 + 0.07 * math.sin(t * 17 + ph1)); wr = w * (1 + 0.07 * math.sin(t * 13 + ph2))
        left.append((x + nx * wl, y + ny * wl)); right.append((x - nx * wr, y - ny * wr))
    d = smooth_closed(left + right[::-1])
    out.append(f'<path d="{d}" fill="#2e1d00" opacity="0.28" transform="translate(3,5)" filter="{s.blur(3.5)}"/>')
    g = s.lin(c[0][0], c[0][1], c[-1][0], c[-1][1], [(0, col), (0.7, col), (1, mix(col, floor, 0.35))])
    out.append(f'<path d="{d}" fill="{g}"/>')
    cl = s.clip(d)
    edge = smooth_open(c)
    sk = [f'<g clip-path="{cl}">']
    sk.append(f'<path d="{d}" fill="none" stroke="{lo}" stroke-width="{f(width*0.42)}" transform="translate({f(width*0.16)},{f(width*0.22)})" opacity="0.65" filter="{s.blur(width*0.12)}"/>')
    sk.append(f'<path d="{d}" fill="none" stroke="{hi}" stroke-width="{f(width*0.26)}" transform="translate({f(-width*0.12)},{f(-width*0.16)})" opacity="0.85" filter="{s.blur(width*0.08)}"/>')
    # the spoon groove: thinner, paler layer along the middle of the swoosh
    gi0, gi1 = 5, N - 6
    groove = []
    for i in range(gi0, gi1):
        t = i / (N - 1)
        groove.append(c[i])
    gw = [width * 0.55 * (1 - 0.85 * (i / (N - 1)) ** 1.2) for i in range(gi0, gi1)]
    gd = stroke_band(groove, gw, rng, wob=0.0)
    sk.append(f'<path d="{gd}" fill="{mix(col, hi, 0.35)}" opacity="0.85" filter="{s.blur(2.2)}"/>')
    sk.append(f'<path d="{gd}" fill="none" stroke="{lo}" stroke-width="2.4" opacity="0.35" transform="translate(-1.5,-2)" filter="{s.blur(1)}"/>')
    # drag ridges
    for k in range(5):
        off = rng.uniform(-0.45, 0.45)
        i0 = rng.randint(6, N // 3); i1 = rng.randint(N // 2, N - 6)
        seg = []
        for i in range(i0, i1):
            x, y = c[i]
            x0, y0 = c[max(i - 1, 0)]; x1, y1 = c[min(i + 1, N - 1)]
            tx, ty = x1 - x0, y1 - y0; L = math.hypot(tx, ty) or 1
            w = width * (1 - 0.8 * (i / (N - 1)) ** 1.3)
            seg.append((x - ty / L * w * off, y + tx / L * w * off))
        sw = rng.uniform(1.4, 2.4)
        sk.append(f'<path d="{smooth_open(seg)}" stroke="{hi}" stroke-width="{f(sw)}" fill="none" opacity="0.6" stroke-linecap="round"/>')
    # wet gloss on the head and along the upper rim
    hx, hy = c[4][0] - width * 0.3, c[4][1] - width * 0.45
    sk.append(f'<ellipse cx="{f(hx)}" cy="{f(hy)}" rx="{f(width*0.34)}" ry="{f(width*0.12)}" fill="#ffffff" opacity="0.75" transform="rotate(-25 {f(hx)} {f(hy)})"/>')
    gl = []
    i = 10
    while i < N - 14:
        ln = rng.randint(2, 6)
        seg = []
        for j in range(i, i + ln):
            w = width * (1 - 0.8 * (j / (N - 1)) ** 1.3)
            seg.append((c[j][0], c[j][1] - w * 0.6))
        gl.append(f'<path d="{smooth_open(seg)}" stroke="#ffffff" stroke-width="{f(rng.uniform(1.6,3.0))}" stroke-linecap="round" opacity="{rng.uniform(0.35,0.7):.2f}" fill="none"/>')
        i += ln + rng.randint(3, 7)
    sk.append("".join(gl))
    sk.append('</g>')
    out.append("".join(sk))
    return "".join(out)


def fry(s, cx, cy, L, W, ang, shade_id, tip_id, extra=""):
    """One thick-cut fry as a rotated rounded rect using shared bbox gradients."""
    return (f'<g transform="translate({f(cx)},{f(cy)}) rotate({f(ang)})">'
            f'<rect x="{f(-L/2)}" y="{f(-W/2)}" width="{f(L)}" height="{f(W)}" rx="{f(W*0.22)}" fill="url(#{shade_id})"/>'
            f'<rect x="{f(-L/2)}" y="{f(-W/2)}" width="{f(L)}" height="{f(W)}" rx="{f(W*0.22)}" fill="url(#{tip_id})"/>{extra}</g>')


def fry_defs(s):
    """Shared gradients for fries (several tones)."""
    ids = []
    tones = [("#F9D579", "#EEB441", "#D8922C", "#A86616"),
             ("#F6CF6C", "#E8A938", "#CD8626", "#985A12"),
             ("#FCDD8A", "#F2C052", "#DEA03A", "#B37422"),
             ("#F2C766", "#E19E33", "#C47D22", "#8C5010")]
    for i, (a, b, c, d) in enumerate(tones):
        gid = s.uid("fry")
        # across width: lit top face, darker side sliver at the bottom
        s.d(f'<linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{c}"/><stop offset="0.12" stop-color="{a}"/>'
            f'<stop offset="0.3" stop-color="{a}"/><stop offset="0.62" stop-color="{b}"/><stop offset="0.74" stop-color="{c}"/><stop offset="0.78" stop-color="{d}"/><stop offset="1" stop-color="{mix(d,"#000000",0.2)}"/></linearGradient>')
        ids.append(gid)
    tip = s.uid("frt")
    s.d(f'<linearGradient id="{tip}" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#8A4E16" stop-opacity="0.55"/><stop offset="0.07" stop-color="#8A4E16" stop-opacity="0.12"/>'
        f'<stop offset="0.2" stop-color="#8A4E16" stop-opacity="0"/><stop offset="0.8" stop-color="#8A4E16" stop-opacity="0"/><stop offset="0.93" stop-color="#8A4E16" stop-opacity="0.15"/><stop offset="1" stop-color="#8A4E16" stop-opacity="0.6"/></linearGradient>')
    return ids, tip


def fry_angle(a):
    """Normalise a fry angle so its lit (local -y) edge faces the top-left light."""
    r = math.radians(a)
    nx, ny = math.sin(r), -math.cos(r)
    if nx * -0.707 + ny * -0.707 < 0:
        a += 180
    return a


def fries_pile(s, region_fn, layers, rng, L=(110, 190), W=(22, 28), tex=None):
    """Pile of fries drawn in layers; each layer casts a soft shadow on the one below.
    region_fn(layer_idx) -> (x, y, angle) sample."""
    ids, tip = fry_defs(s)
    out = []
    shapes_all = []
    for li, count in enumerate(layers):
        items = []
        for _ in range(count):
            x, y, a = region_fn(li)
            a = fry_angle(a)
            l = rng.uniform(*L); w = rng.uniform(*W)
            items.append((x, y, l, w, a))
        # shadow of this layer onto what is below
        sh = []
        for x, y, l, w, a in items:
            sh.append(f'<rect x="{f(-l/2)}" y="{f(-w/2)}" width="{f(l)}" height="{f(w)}" rx="{f(w*0.3)}" transform="translate({f(x+7)},{f(y+9)}) rotate({f(a)})"/>')
        out.append(f'<g filter="{s.blur(6)}" opacity="{0.42 if li else 0.5}">{"".join(sh)}</g>')
        body = []
        for x, y, l, w, a in items:
            # crisp spots / potato texture specks in local coords
            ex = []
            for _ in range(rng.randint(0, 3)):
                ux = rng.uniform(-l / 2 + 6, l / 2 - 6); uy = rng.uniform(-w / 2 + 3, w * 0.15)
                ex.append(f'<ellipse cx="{f(ux)}" cy="{f(uy)}" rx="{f(rng.uniform(1.5,4.0))}" ry="{f(rng.uniform(1,2.0))}" fill="#B5701E" opacity="{rng.uniform(0.12,0.28):.2f}"/>')
            if rng.random() < 0.6:
                ux = rng.uniform(-l / 3, l / 3)
                ex.append(f'<rect x="{f(ux)}" y="{f(-w/2+w*0.12)}" width="{f(rng.uniform(15,40))}" height="{f(w*0.12)}" rx="2" fill="#FFF6D8" opacity="0.55"/>')
            body.append(fry(s, x, y, l, w, a, ids[rng.randrange(len(ids))], tip, "".join(ex)))
        layer = "".join(body)
        if tex:
            out.append(f'<g filter="{tex}">{layer}</g>')
        else:
            out.append(layer)
    return "".join(out)


def mayo_swirl(s, cx, cy, R, rng, turns=1.6, w0=46, w1=30, col="#FBF5E2", shade="#E3D7B8"):
    """A piped spiral of mayo seen from above (outer coil first, inner coil on top)."""
    out = []
    N = 120
    pts = []
    for i in range(N + 1):
        t = i / N
        th = -2 * math.pi * turns * t + 0.4
        r = R * (1 - t) ** 0.9 + 3
        wob = 1 + 0.04 * math.sin(t * 23)
        pts.append((cx + math.cos(th) * r * wob, cy + math.sin(th) * r * wob, w0 + (w1 - w0) * t))
    pd = blob(cx, cy, R + w0 * 0.42, R * 0.97 + w0 * 0.42, rng, n=24, amp=0.03)
    out.append(f'<path d="{pd}" fill="#2a1d05" opacity="0.38" transform="translate(10,13)" filter="{s.blur(9)}"/>')
    out.append(f'<path d="{pd}" fill="{mix(shade, col, 0.4)}"/>')
    seg = 22
    i = 0
    while i < N:
        chunk = pts[i:i + seg + 1]
        if len(chunk) < 2:
            break
        d = smooth_open([(x, y) for x, y, _ in chunk])
        w = sum(c[2] for c in chunk) / len(chunk)
        out.append(f'<g>'
                   f'<path d="{d}" stroke="#5c4a24" stroke-opacity="0.28" stroke-width="{f(w*0.95)}" stroke-linecap="round" fill="none" transform="translate({f(w*0.16)},{f(w*0.2)})" filter="{s.blur(w*0.12)}"/>'
                   f'<path d="{d}" stroke="{shade}" stroke-width="{f(w)}" stroke-linecap="round" fill="none"/>'
                   f'<path d="{d}" stroke="{col}" stroke-width="{f(w*0.74)}" stroke-linecap="round" fill="none" transform="translate({f(-w*0.08)},{f(-w*0.1)})" filter="{s.blur(w*0.05)}"/>'
                   f'<path d="{d}" stroke="#ffffff" stroke-width="{f(w*0.2)}" stroke-linecap="butt" fill="none" opacity="0.85" transform="translate({f(-w*0.2)},{f(-w*0.24)})" filter="{s.blur(w*0.04)}"/>'
                   f'</g>')
        i += seg - 2
    x, y, w = pts[-1]
    out.append(f'<circle cx="{f(x-2)}" cy="{f(y-3)}" r="{f(w*0.42)}" fill="{col}" filter="{s.blur(1.5)}"/><ellipse cx="{f(x-6)}" cy="{f(y-8)}" rx="{f(w*0.18)}" ry="{f(w*0.1)}" fill="#fff" transform="rotate(-35 {f(x-6)} {f(y-8)})"/>')
    return "".join(out)


def pepper(pts_fn, n, rng, size=(1.4, 3.4)):
    dk, gr = [], []
    for _ in range(n):
        x, y = pts_fn()
        p = poly(x, y, rng.uniform(*size), rng, 3, 6)
        (dk if rng.random() < 0.75 else gr).append(p)
    return f'<path d="{"".join(dk)}" fill="#1a1612" opacity="0.92"/><path d="{"".join(gr)}" fill="#5b5148" opacity="0.9"/>'


def axis_frame(cx, cy, ang_deg):
    a = math.radians(ang_deg)
    ex, ey = math.cos(a), math.sin(a)
    nx, ny = -ey, ex  # local +y
    def P(u, v):
        return (cx + ex * u + nx * v, cy + ey * u + ny * v)
    return P, (ex, ey), (nx, ny)


def frikandel(s, cx, cy, length, dia, ang_deg, rng, split=True, half=None):
    """Skinless smooth frikandel, optionally split open lengthwise.
    half: None or 'right'/'left' -> that end is a flat cut end (for half a frikandel).
    Returns (markup, outline d, P local->global mapper)."""
    out = []
    a = math.radians(ang_deg)
    pts = stadium_pts(cx, cy, length, dia, a, rng, n_side=16, n_cap=12, amp=dia * 0.006, flat_end=half)
    d = smooth_closed(pts)
    P, (ex, ey), (nx, ny) = axis_frame(cx, cy, ang_deg)
    r = dia / 2
    lnx, lny = nx, ny
    if lnx * -0.707 + lny * -0.707 > 0:
        lit_sign = 1   # local +y faces the light
    else:
        lit_sign = -1
    A = P(0, lit_sign * r * 1.02); B = P(0, -lit_sign * r * 1.02)
    g = s.lin(A[0], A[1], B[0], B[1], [(0, "#5A2E12"), (0.1, "#8E5530"), (0.26, "#7C4524"), (0.55, "#5E3016"), (0.82, "#3E1D0A"), (1, "#2A1105")])
    tex = s.texture(freq=0.035, scale=0.7, seed=21, spec=0.35, spec_exp=30, gain=1.31, octaves=2, elev=58)
    out.append(f'<g filter="{tex}"><path d="{d}" fill="{g}"/></g>')
    cl = s.clip(d)
    out.append(f'<g clip-path="{cl}">')
    # fine wrinkles running along the sausage
    wr = []
    for i in range(int(length / 12)):
        u0 = rng.uniform(-length / 2, length / 2 - 40); L = rng.uniform(18, 50)
        v = rng.uniform(-r * 0.9, r * 0.9)
        pp = [P(u0 + L * k / 6, v + rng.uniform(-1.5, 1.5)) for k in range(7)]
        wr.append(smooth_open(pp))
    out.append(f'<path d="{"".join(wr)}" stroke="#2c1406" stroke-width="1.6" fill="none" opacity="0.1" filter="{s.blur(0.8)}"/>')
    # specular streak along the lit side
    S0 = P(-length * 0.42, lit_sign * r * 0.55); S1 = P(length * 0.4, lit_sign * r * 0.55)
    out.append(f'<path d="M{f(S0[0])},{f(S0[1])}L{f(S1[0])},{f(S1[1])}" stroke="#FFE7C8" stroke-width="{f(r*0.16)}" stroke-linecap="round" opacity="0.4" filter="{s.blur(3)}"/>')
    # ends darker
    E0 = P(-length / 2, 0); E1 = P(length / 2, 0)
    eg = s.lin(E0[0], E0[1], E1[0], E1[1], [(0, "#1d0c03", 0.35), (0.08, "#1d0c03", 0), (0.92, "#1d0c03", 0), (1, "#1d0c03", 0.45)])
    out.append(f'<path d="{d}" fill="{eg}"/>')
    if half:
        # squared cut end shows a sliver of the paler, finely ground inside
        u = length / 2 if half == 'cutright' else -length / 2
        sgn = 1 if half == 'cutright' else -1
        cpts = [P(u - sgn * 9, -r * 0.98), P(u, -r * 0.98), P(u + sgn * 1, 0), P(u, r * 0.98), P(u - sgn * 9, r * 0.98), P(u - sgn * 11, 0)]
        out.append(f'<path d="{smooth_closed(cpts)}" fill="#A87150" opacity="0.95"/>')
        out.append(f'<path d="{smooth_closed(cpts)}" fill="#3a1a08" opacity="0.25" transform="translate(2,2)"/>')
    out.append('</g>')
    return "".join(out), d, P


def frik_split_fill(s, P, length, dia, rng):
    """The opened slit of a frikandel speciaal: meat inside, curry ketchup, mayo and onion on top."""
    out = []
    r = dia / 2
    L = length / 2 - dia * 0.55
    # opened slit (lens shape) showing paler interior
    N = 24
    top = [P(-L + 2 * L * i / N, -r * 0.34 * math.sin(math.pi * i / N) ** 0.5) for i in range(N + 1)]
    bot = [P(L - 2 * L * i / N, r * 0.34 * math.sin(math.pi * i / N) ** 0.5) for i in range(N + 1)]
    sd = smooth_closed(top + bot)
    out.append(f'<path d="{sd}" fill="#1e0b02" opacity="0.6" transform="translate(1,2)" filter="{s.blur(2)}"/>')
    mg = s.lin(*P(0, -r * 0.34), *P(0, r * 0.34), [(0, "#6B3A20"), (0.5, "#A06A48"), (1, "#7A4428")])
    mtex = s.texture(freq=0.5, scale=1.0, seed=7, spec=0.2, gain=1.3, octaves=2)
    out.append(f'<g filter="{mtex}"><path d="{sd}" fill="{mg}"/></g>')
    return "".join(out)


def sauce_line(s, P, u0, u1, v, w, rng, col, hi, lo, wave=3.0, waves=5, shadow=0.35):
    """A piped line of sauce along the local u axis at offset v."""
    N = 40
    c = []
    ph = rng.uniform(0, 6)
    for i in range(N):
        t = i / (N - 1)
        u = u0 + (u1 - u0) * t
        c.append(P(u, v + wave * math.sin(t * waves * 2 * math.pi + ph)))
    ws = []
    for i in range(N):
        t = i / (N - 1)
        taper = min(1.0, (min(t, 1 - t) * 14) ** 0.5)
        ws.append(w * (0.88 + 0.12 * math.sin(i * 0.9 + ph)) * max(0.35, taper))
    d = stroke_band(c, ws, rng, wob=0.04)
    out = [f'<path d="{d}" fill="#000" opacity="{shadow}" transform="translate(3,4)" filter="{s.blur(2.5)}"/>']
    A = c[N // 2]
    g = s.rad(A[0] - w, A[1] - w, (abs(u1 - u0)) * 0.6, [(0, hi), (0.6, col), (1, lo)])
    out.append(f'<path d="{d}" fill="{col}"/>')
    # cross-section shading: darker lower-right edge, lit top-left ridge
    cl = s.clip(d)
    edge = smooth_open(c)
    out.append(f'<g clip-path="{cl}"><path d="{edge}" stroke="{lo}" stroke-width="{f(w*1.6)}" fill="none" transform="translate({f(w*0.55)},{f(w*0.6)})" opacity="0.7" filter="{s.blur(w*0.3)}"/>'
               f'<path d="{edge}" stroke="{hi}" stroke-width="{f(w*0.7)}" fill="none" transform="translate({f(-w*0.3)},{f(-w*0.35)})" opacity="0.8" filter="{s.blur(w*0.15)}"/></g>')
    # glossy specular dashes
    sp = []
    for i in range(3, N - 4, 4):
        if rng.random() < 0.75:
            p0 = c[i]; p1 = c[i + 2]
            sp.append(f"M{f(p0[0]-w*0.35)},{f(p0[1]-w*0.4)}L{f(p1[0]-w*0.35)},{f(p1[1]-w*0.4)}")
    out.append(f'<path d="{"".join(sp)}" stroke="#ffffff" stroke-width="{f(max(1.5, w*0.18))}" stroke-linecap="round" opacity="0.75" fill="none"/>')
    return "".join(out)


# ------------------------------------------------------------------ saté
def skewer_stick(s, P, u0, u1, w=8):
    A = P(u0, 0); B = P(u1, 0)
    T = P(u1 + 22, 0)
    out = [f'<path d="M{f(A[0]+8)},{f(A[1]+11)}L{f(T[0]+8)},{f(T[1]+11)}" stroke="#000" stroke-width="{w}" stroke-linecap="round" opacity="0.3" filter="{s.blur(3)}"/>']
    L1 = P(u0, -w / 2); L2 = P(u0, w / 2)
    g = s.lin(L1[0], L1[1], L2[0], L2[1], [(0, "#F3DDB0"), (0.45, "#DDBB86"), (1, "#9C7442")])
    # flat end + pointed tip
    pts = [P(u0, -w / 2), P(u1, -w / 2), P(u1 + 22, 0), P(u1, w / 2), P(u0, w / 2)]
    d = "M" + "L".join(f"{f(x)},{f(y)}" for x, y in pts) + "Z"
    out.append(f'<path d="{d}" fill="{g}"/>')
    # scorched near the meat
    C0 = P(u0, 0); C1 = P(u1 + 22, 0)
    sg = s.lin(C0[0], C0[1], C1[0], C1[1], [(0, "#3a1d08", 0), (0.25, "#3a1d08", 0), (0.36, "#3a1d08", 0.55), (1, "#3a1d08", 0.6)])
    out.append(f'<path d="{d}" fill="{sg}"/>')
    return "".join(out)


def sate_chunk(s, cx, cy, w, h, ang_deg, rng):
    out = []
    d = blob(cx, cy, w / 2, h / 2, rng, n=26, amp=0.09, a0=math.radians(ang_deg + rng.uniform(-12, 12)))
    g = s.rad(cx - w * 0.2, cy - h * 0.25, max(w, h) * 0.78, [(0, "#EBB766"), (0.35, "#CF8A3C"), (0.7, "#A05A24"), (1, "#5E2A0E")])
    tex = s.texture(freq=0.06, scale=2.2, seed=31, spec=0.6, spec_exp=20, blot=0.6, blot_freq=0.045,
                    blot_col=(0.35, 0.15, 0.04), gain=1.3, octaves=2, elev=50)
    out.append(f'<g filter="{tex}"><path d="{d}" fill="{g}"/></g>')
    cl = s.clip(d)
    out.append(f'<g clip-path="{cl}">')
    # grill bars: dark diagonal char marks
    a = math.radians(ang_deg + 58)
    ux, uy = math.cos(a), math.sin(a)
    vx, vy = -uy, ux
    marks = []
    off0 = rng.uniform(-6, 6)
    for k in (-0.5, 0.5):
        o = off0 + k * 34
        p1 = (cx + vx * o - ux * w, cy + vy * o - uy * w)
        p2 = (cx + vx * o + ux * w, cy + vy * o + uy * w)
        marks.append(f"M{f(p1[0])},{f(p1[1])}L{f(p2[0])},{f(p2[1])}")
    out.append(f'<path d="{"".join(marks)}" stroke="#2a1006" stroke-width="11" opacity="0.6" filter="{s.blur(2.5)}"/>')
    out.append(f'<path d="{"".join(marks)}" stroke="#1a0803" stroke-width="4" opacity="0.5" filter="{s.blur(0.8)}"/>')
    # charred rim (edges catch the flame)
    out.append(f'<path d="{d}" fill="none" stroke="#2a1006" stroke-width="10" opacity="0.5" filter="{s.blur(3.5)}"/>')
    # burnt crumbs/spots
    sp = []
    for _ in range(9):
        th = rng.uniform(0, 2 * math.pi); t = rng.uniform(0.55, 0.95)
        sp.append(poly(cx + math.cos(th) * w / 2 * t, cy + math.sin(th) * h / 2 * t, rng.uniform(2, 5), rng))
    out.append(f'<path d="{"".join(sp)}" fill="#160803" opacity="0.7"/>')
    # glossy marinade highlights
    hx, hy = cx - w * 0.18, cy - h * 0.22
    out.append(f'<path d="M{f(hx-w*0.16)},{f(hy+h*0.1)}Q{f(hx-w*0.05)},{f(hy-h*0.12)} {f(hx+w*0.18)},{f(hy-h*0.1)}" stroke="#FFF1D8" stroke-width="3.2" stroke-linecap="round" fill="none" opacity="0.7"/>')
    out.append(f'<circle cx="{f(hx+w*0.24)}" cy="{f(hy+h*0.02)}" r="2" fill="#fff" opacity="0.6"/>')
    out.append('</g>')
    sh = d
    return "".join(out), sh


def peanut_sauce(s, pts, rng, bumps=()):
    """Glossy peanut sauce pour; pts = outline points (smoothed). bumps = (x, y, r) of things under it."""
    out = []
    d = smooth_closed(pts)
    out.append(f'<path d="{d}" fill="#1c0c02" opacity="0.4" transform="translate(6,8)" filter="{s.blur(6)}"/>')
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    g = s.lin(x0, y0, x1, y1, [(0, "#9E642E"), (0.5, "#83501F"), (1, "#653815")])
    tex = s.texture(freq=0.014, scale=7.0, seed=41, spec=0.8, spec_exp=40, gain=1.28, octaves=1, elev=55, spec_elev=42,
                    region='x="-5%" y="-5%" width="110%" height="110%"')
    out.append(f'<g filter="{tex}"><path d="{d}" fill="{g}"/></g>')
    cl = s.clip(d)
    out.append(f'<g clip-path="{cl}">')
    # draped over items: lighter rounded bulges with a shaded lower-right side
    for (bx, by, br) in bumps:
        hg = s.rad(bx - br * 0.25, by - br * 0.3, br * 1.1, [(0, "#C68A4C", 0.75), (0.6, "#A86C34", 0.3), (1, "#A86C34", 0)])
        out.append(f'<ellipse cx="{f(bx+br*0.18)}" cy="{f(by+br*0.22)}" rx="{f(br*1.05)}" ry="{f(br*0.9)}" fill="#4a250c" opacity="0.35" filter="{s.blur(br*0.25)}"/>')
        out.append(f'<ellipse cx="{f(bx)}" cy="{f(by)}" rx="{f(br)}" ry="{f(br*0.85)}" fill="{hg}"/>')
        out.append(f'<path d="M{f(bx-br*0.6)},{f(by-br*0.05)}Q{f(bx-br*0.45)},{f(by-br*0.55)} {f(bx+br*0.1)},{f(by-br*0.6)}" stroke="#FFF0D8" stroke-width="3.5" fill="none" stroke-linecap="round" opacity="0.75"/>')
    out.append(f'<path d="{d}" fill="none" stroke="#3E1E08" stroke-width="14" opacity="0.45" transform="translate(6,7)" filter="{s.blur(5)}"/>')
    out.append(f'<path d="{d}" fill="none" stroke="#D9A56A" stroke-width="5" opacity="0.65" transform="translate(-3,-3)" filter="{s.blur(2)}"/>')
    # ground peanut bits
    grp = {("#D7A469", 0.65): [], ("#5A2E10", 0.45): []}
    for _ in range(int((x1 - x0) * (y1 - y0) / 320)):
        x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
        grp[("#D7A469", 0.65) if rng.random() < 0.6 else ("#5A2E10", 0.45)].append(poly(x, y, rng.uniform(1.2, 2.6), rng))
    out.append(specks(grp))
    out.append('</g>')
    return "".join(out), d


def cucumber_slice(s, cx, cy, r, rng):
    out = []
    d = blob(cx, cy, r, r, rng, n=24, amp=0.015)
    out.append(f'<path d="{d}" fill="#000" opacity="0.3" transform="translate(3,4)" filter="{s.blur(3)}"/>')
    sg = s.lin(cx - r, cy - r, cx + r, cy + r, [(0, "#5E8A35"), (1, "#2A4F17")])
    out.append(f'<path d="{d}" fill="{sg}"/>')
    di = blob(cx, cy, r * 0.94, r * 0.94, rng, n=24, amp=0.012)
    g = s.rad(cx - r * 0.25, cy - r * 0.3, r * 1.1, [(0, "#F1F7DE"), (0.55, "#DCEBB6"), (0.9, "#BCD88A"), (1, "#8DB55A")])
    out.append(f'<path d="{di}" fill="{g}"/>')
    # seed area: three lobes
    lobes = []
    a0 = rng.uniform(0, 2 * math.pi)
    for k in range(3):
        a = a0 + k * 2 * math.pi / 3
        lx, ly = cx + math.cos(a) * r * 0.3, cy + math.sin(a) * r * 0.3
        lobes.append(f'<ellipse cx="{f(lx)}" cy="{f(ly)}" rx="{f(r*0.26)}" ry="{f(r*0.17)}" transform="rotate({f(math.degrees(a))} {f(lx)} {f(ly)})"/>')
    out.append(f'<g fill="#C6DE98" opacity="0.7" filter="{s.blur(1.5)}">{"".join(lobes)}</g>')
    seeds = []
    for k in range(3):
        a = a0 + k * 2 * math.pi / 3
        for j in range(3):
            t = 0.2 + 0.12 * j
            lx, ly = cx + math.cos(a + (j - 1) * 0.25) * r * t, cy + math.sin(a + (j - 1) * 0.25) * r * t
            seeds.append(f'<ellipse cx="{f(lx)}" cy="{f(ly)}" rx="{f(r*0.07)}" ry="{f(r*0.04)}" transform="rotate({f(math.degrees(a))} {f(lx)} {f(ly)})"/>')
    out.append(f'<g fill="#F7FBEA" opacity="0.8">{"".join(seeds)}</g>')
    out.append(f'<path d="M{f(cx-r*0.6)},{f(cy-r*0.2)}A{f(r*0.65)},{f(r*0.65)} 0 0 1 {f(cx-r*0.1)},{f(cy-r*0.64)}" stroke="#fff" stroke-width="3" fill="none" opacity="0.6" stroke-linecap="round"/>')
    return "".join(out)


def shallot_ring(s, cx, cy, rx, ry, ang, rng, arc=None, layers=2):
    """Thin raw red-shallot slice: concentric rings with magenta edges (or part of one)."""
    out = []
    for li in range(layers):
        k = 1 - li * 0.34
        a0, a1 = (0, 360) if (arc is None or li > 0) else arc
        if li > 0 and arc is not None:
            a0, a1 = arc
        pts = []
        n = 30
        for i in range(n + 1):
            t = math.radians(a0 + (a1 - a0) * i / n)
            pts.append(rot((math.cos(t) * rx * k, math.sin(t) * ry * k), math.radians(ang)))
        pts = [(cx + x, cy + y) for x, y in pts]
        dd = smooth_open(pts)
        out.append(f'<path d="{dd}" stroke="#000" stroke-width="6" fill="none" opacity="0.22" transform="translate(2,3)" filter="{s.blur(1.6)}"/>')
        out.append(f'<path d="{dd}" stroke="#F4E2EA" stroke-width="6.5" fill="none" stroke-linecap="round" opacity="0.93"/>')
        out.append(f'<path d="{dd}" stroke="#A3306A" stroke-width="2.4" fill="none" stroke-linecap="round" transform="translate({f(1.6*k)},{f(1.6*k)})" opacity="0.95"/>')
        out.append(f'<path d="{dd}" stroke="#C04C86" stroke-width="1.2" fill="none" stroke-linecap="round" transform="translate(-2,-2)" opacity="0.6"/>')
        out.append(f'<path d="{dd}" stroke="#ffffff" stroke-width="1.2" fill="none" stroke-linecap="round" opacity="0.85" transform="translate(-0.6,-0.8)"/>')
    return "".join(out)


def goo_line(s, P, u0, u1, v, w, rng, color, wave=3.0, waves=5, shadow=0.4, **kw):
    """A thick piped line of sauce (mayo / curry) rendered with the lit goo filter."""
    from artlib import goo_filter
    circ = []
    ph = rng.uniform(0, 6)
    n = int(abs(u1 - u0) / (w * 0.45))
    for i in range(n + 1):
        t = i / n
        u = u0 + (u1 - u0) * t
        taper = min(1.0, (min(t, 1 - t) * 10) ** 0.5)
        vv = v + wave * math.sin(t * waves * 2 * math.pi + ph)
        r = w * (0.85 + 0.25 * rng.random()) * max(0.45, taper)
        p = P(u, vv)
        circ.append((p[0], p[1], r, 0.3))
        p = P(u + rng.uniform(-3, 3), vv + rng.uniform(-w * 0.2, w * 0.2))
        circ.append((p[0], p[1], r * 0.7, 0.28))
    body = "".join(f'<circle cx="{f(x)}" cy="{f(y)}" r="{f(r)}" fill="#000" fill-opacity="{o}"/>' for x, y, r, o in circ)
    flt = goo_filter(s, color, **kw)
    return (f'<g filter="{s.blur(3.5)}" opacity="{shadow}" transform="translate(4,6)">{body}</g>'
            f'<g filter="{flt}">{body}</g>')


def mayo_goo(s, cx, cy, R, rng, turns=1.9, w0=23, w1=15, color="#F3ECD6"):
    """Piped mayo spiral as lit goo: coils stack higher toward the centre."""
    from artlib import goo_filter
    circ = []
    # spiral length estimate, place circles every ~6px
    steps = 260
    prev = None
    for i in range(steps + 1):
        t = i / steps
        th = -2 * math.pi * turns * t + 0.5
        r = R * (1 - t) + 2
        x, y = cx + math.cos(th) * r, cy + math.sin(th) * r
        if prev and math.hypot(x - prev[0], y - prev[1]) < 6:
            continue
        prev = (x, y)
        w = w0 + (w1 - w0) * t
        circ.append((x, y, w, 0.26 + 0.14 * t))
    circ.append((cx + 1, cy - 1, w1 * 0.9, 0.4))
    body = "".join(f'<circle cx="{f(x)}" cy="{f(y)}" r="{f(r)}" fill="#000" fill-opacity="{o:.2f}"/>' for x, y, r, o in circ)
    flt = goo_filter(s, color, blur=3.5, scale=9, spec=0.75, spec_exp=34, hi_gain=1.2, thresh=(30, -6))
    return (f'<g filter="{s.blur(8)}" opacity="0.55" transform="translate(9,12)">{body}</g>'
            f'<g filter="{flt}">{body}</g>')


def mustard_goo(s, p0, p1, p2, width, rng, color="#D9A62C"):
    """Spoon-smeared mustard: a soft dollop dragged into a thin, streaky, feathered smear."""
    from artlib import goo_filter
    circ = []
    N = 110
    cpts = []
    for i in range(N + 1):
        t = i / N
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]
        cpts.append((x, y))
    streaks = [rng.uniform(-0.9, 0.9) for _ in range(9)]
    for i, (x, y) in enumerate(cpts):
        t = i / N
        x0, y0 = cpts[max(i - 1, 0)]; x1, y1 = cpts[min(i + 1, N)]
        tx, ty = x1 - x0, y1 - y0; L = math.hypot(tx, ty) or 1
        nx, ny = -ty / L, tx / L
        w = width * (1 - 0.55 * t)
        core = max(0.0, 1 - t / 0.55)  # solid body fades out, leaving streaks
        if t < 0.06:
            w *= 0.7 + 0.3 * t / 0.06
        if core > 0:
            circ.append((x, y, w * (0.55 + 0.35 * core), 0.16 + 0.12 * core))
        for k, o in enumerate(streaks):
            end_t = 0.6 + 0.4 * ((k * 37) % 9) / 9
            if t < end_t:
                circ.append((x + nx * o * w, y + ny * o * w, w * 0.16 * (1 - 0.5 * t / end_t), 0.32))
    body = "".join(f'<circle cx="{f(x)}" cy="{f(y)}" r="{f(r)}" fill="#000" fill-opacity="{o:.2f}"/>' for x, y, r, o in circ)
    flt = goo_filter(s, color, blur=2.2, scale=2.2, spec=0.7, spec_exp=26, hi_gain=1.16, thresh=(30, -6))
    return (f'<g filter="{s.blur(2.5)}" opacity="0.25" transform="translate(3,4)">{body}</g>'
            f'<g filter="{flt}">{body}</g>')


def goo_dots(s, dots, color, rng, **kw):
    """Piped dots of sauce (list of (x, y, r)) as glossy lit goo with a small peak."""
    from artlib import goo_filter
    circ = []
    for (x, y, r) in dots:
        circ.append((x, y, r * 1.05, 0.34))
        circ.append((x + r * 0.05, y - r * 0.05, r * 0.35, 0.3))
    body = "".join(f'<circle cx="{f(x)}" cy="{f(y)}" r="{f(r)}" fill="#000" fill-opacity="{o}"/>' for x, y, r, o in circ)
    params = dict(blur=2.6, scale=2.6, spec=0.7, spec_exp=30, hi_gain=1.2, thresh=(30, -4))
    params.update(kw)
    flt = goo_filter(s, color, **params)
    return (f'<g filter="{s.blur(2.5)}" opacity="0.45" transform="translate(3,4)">{body}</g>'
            f'<g filter="{flt}">{body}</g>')


def loose_crumbs(s, pts_fn, n, rng):
    """Loose fried breadcrumbs fallen on the tray."""
    grp = {("#C9822F", 0.9): [], ("#E3A957", 0.9): [], ("#8E4F1A", 0.85): []}
    keys = list(grp.keys())
    sh = []
    for _ in range(n):
        x, y = pts_fn()
        p = poly(x, y, rng.uniform(1.4, 3.6), rng, 4, 6)
        grp[keys[rng.randrange(3)]].append(p)
        sh.append(p)
    return f'<path d="{"".join(sh)}" fill="#3a2200" opacity="0.3" transform="translate(1.2,1.6)"/>' + specks(grp)
