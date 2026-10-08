"""Surfaces and containers: Delft tile countertop, white cardboard snack trays,
orange napkin, pleated paper dip cup, white ceramic plate."""
import math, random
from artlib import f, rot, rrect_path, smooth_closed, smooth_open, blob, blob_pts, poly, mix, specks


def delft_bg(s, seed=1, ox=-60, oy=0):
    rng = random.Random(seed)
    W, H, T = s.w, s.h, 200
    s.add(f'<rect width="{W}" height="{H}" fill="#1B2A4A"/>')
    # tiles: pillowed glaze, slight per-tile tone variation
    tg = s.lin(0, 0, 1, 1, [(0, "#ffffff", 0.07), (0.45, "#ffffff", 0.0), (1, "#000000", 0.16)], user=False)
    xs = list(range(ox, W + T, T)); ys = list(range(oy, H + T, T))
    tiles = []
    for x in xs:
        for y in ys:
            tone = rng.uniform(-0.03, 0.03)
            col = "#ffffff" if tone > 0 else "#000000"
            tiles.append(f'<rect x="{x+3}" y="{y+3}" width="{T-6}" height="{T-6}" rx="9" fill="{tg}"/>')
            tiles.append(f'<rect x="{x+3}" y="{y+3}" width="{T-6}" height="{T-6}" rx="9" fill="{col}" opacity="{abs(tone):.3f}"/>')
    s.add("".join(tiles))
    # corner ornaments (quarter motifs meeting at each grout crossing) + faint centre rosette
    petal = "M9,0C18,-10 34,-9 44,0C34,9 18,10 9,0Z"
    curl = "M18,-5C21,-15 31,-19 37,-14C33,-14 29,-12 27,-8"
    curl2 = "M18,5C21,15 31,19 37,14C33,14 29,12 27,8"
    motif = []
    for a in (45, 135, 225, 315):
        motif.append(f'<path d="{petal}" transform="rotate({a})"/>')
        motif.append(f'<path d="{curl}{curl2}" transform="rotate({a})" fill="none" stroke="#2E4673" stroke-width="3" stroke-linecap="round"/>')
        motif.append(f'<circle cx="52" cy="0" r="3.5" transform="rotate({a})"/>')
    for a in (0, 90, 180, 270):
        motif.append(f'<path d="M14,0C20,-4 26,-4 30,0C26,4 20,4 14,0Z" transform="rotate({a})"/>')
    motif.append('<circle r="7"/>')
    mid = s.uid("m")
    s.d(f'<g id="{mid}" fill="#2E4673">{"".join(motif)}</g>')
    ros = []
    for a in range(0, 360, 45):
        ros.append(f'<path d="M7,0C12,-6 22,-6 26,0C22,6 12,6 7,0Z" transform="rotate({a})"/>')
    ros.append('<circle r="5"/>')
    ros.append('<circle r="38" fill="none" stroke="#2E4673" stroke-width="2.5"/>')
    rid = s.uid("r")
    s.d(f'<g id="{rid}" fill="#2E4673">{"".join(ros)}</g>')
    uses = []
    for x in xs:
        for y in ys:
            uses.append(f'<use href="#{mid}" x="{x}" y="{y}"/>')
            uses.append(f'<use href="#{rid}" x="{x+T//2}" y="{y+T//2}" opacity="0.55"/>')
    s.add(f'<g opacity="0.55">{"".join(uses)}</g>')
    # grout
    gl = []
    for x in xs:
        gl.append(f'M{x},0V{H}')
    for y in ys:
        gl.append(f'M0,{y}H{W}')
    s.add(f'<path d="{"".join(gl)}" stroke="#24365C" stroke-width="5" fill="none"/>')
    s.add(f'<path d="{"".join(gl)}" stroke="#16223D" stroke-width="1.5" fill="none" transform="translate(1.5,1.5)" opacity="0.8"/>')
    # broad glaze sheen from top-left light
    sh = s.rad(260, 60, 900, [(0, "#9fb4e0", 0.13), (0.5, "#9fb4e0", 0.04), (1, "#9fb4e0", 0)])
    s.add(f'<rect width="{W}" height="{H}" fill="{sh}"/>')


def tray(s, cx, cy, w, h, ang=0.0, wall=34, r=18, lip=5, seed=2):
    """White cardboard snack tray, top-down. Returns (markup, floor_path_d)."""
    rng = random.Random(seed)
    a = math.radians(ang)
    out = []

    def P(x, y):
        p = rot((x, y), a)
        return (cx + p[0], cy + p[1])

    def path(pts):
        return "M" + "L".join(f"{f(x)},{f(y)}" for x, y in pts) + "Z"

    def rr(x0, y0, x1, y1, rad, n=6):
        pts = []
        corners = [(x1 - rad, y0 + rad, -90), (x1 - rad, y1 - rad, 0), (x0 + rad, y1 - rad, 90), (x0 + rad, y0 + rad, 180)]
        for (ccx, ccy, st) in corners:
            for i in range(n + 1):
                t = math.radians(st + 90 * i / n)
                pts.append(P(ccx + math.cos(t) * rad, ccy + math.sin(t) * rad))
        return pts

    hw, hh = w / 2, h / 2
    outer = rr(-hw, -hh, hw, hh, r)
    outer_d = path(outer)
    # shadows: broad + contact
    out.append(s.shadow(outer_d, 16, 18, 16, 0.42))
    out.append(s.shadow(outer_d, 4, 5, 4, 0.35))
    out.append(f'<path d="{outer_d}" fill="#FBF8F2"/>')
    # walls (trapezoids) inside the lip
    o0, o1 = -hw + lip, hw - lip
    p0, p1 = -hh + lip, hh - lip
    i0, i1 = -hw + wall, hw - wall
    j0, j1 = -hh + wall, hh - wall
    clip = s.clip(path(rr(o0, p0, o1, p1, r - lip)))
    # wall shading: top & left in shade, right & bottom face the light
    walls = [
        ([(o0, p0), (o1, p0), (i1, j0), (i0, j0)], (0, p0), (0, j0), "#E4DACA", "#EDE5D8"),  # top
        ([(o0, p0), (i0, j0), (i0, j1), (o0, p1)], (o0, 0), (i0, 0), "#DCD1BF", "#E8DFD1"),  # left
        ([(o1, p0), (o1, p1), (i1, j1), (i1, j0)], (o1, 0), (i1, 0), "#FFFDF9", "#F6F1E8"),  # right
        ([(o0, p1), (i0, j1), (i1, j1), (o1, p1)], (0, p1), (0, j1), "#FFFDF8", "#F4EEE4"),  # bottom
    ]
    wl = []
    for pts, g0, g1, c0, c1 in walls:
        A, B = P(*g0), P(*g1)
        g = s.lin(A[0], A[1], B[0], B[1], [(0, c0), (1, c1)])
        wl.append(f'<path d="{path([P(*q) for q in pts])}" fill="{g}"/>')
    out.append(f'<g clip-path="{clip}">{"".join(wl)}</g>')
    # folded corner gussets: a triangle flap lying on one wall + crease lines
    fl = []
    cr = []
    for (ox_, oy_, ix_, iy_, sx, sy) in [(o0, p0, i0, j0, 1, 0), (o1, p0, i1, j0, 0, 1), (o1, p1, i1, j1, -1, 0), (o0, p1, i0, j1, 0, -1)]:
        k = (wall - lip) * 1.25
        tip = (ox_ + sx * k, oy_ + sy * k)
        tri = [P(ox_, oy_), P(*tip), P(ix_, iy_)]
        fl.append(f'<path d="{path(tri)}" fill="#ffffff" opacity="0.28"/>')
        A, B = P(*tip), P(ix_, iy_)
        cr.append(f"M{f(A[0])},{f(A[1])}L{f(B[0])},{f(B[1])}")
        A, B = P(ox_, oy_), P(ix_, iy_)
        cr.append(f"M{f(A[0])},{f(A[1])}L{f(B[0])},{f(B[1])}")
    out.append(f'<g clip-path="{clip}">{"".join(fl)}<path d="{"".join(cr)}" stroke="#B9AC96" stroke-width="1.6" opacity="0.55" fill="none"/></g>')
    # floor
    floor = rr(i0, j0, i1, j1, max(r - wall * 0.45, 6))
    floor_d = path(floor)
    A, B = P(i0, j0), P(i1, j1)
    fg = s.lin(A[0], A[1], B[0], B[1], [(0, "#E9E0D1"), (0.5, "#EFE7DA"), (1, "#F2EBDF")])
    out.append(f'<path d="{floor_d}" fill="{fg}"/>')
    # inner shadow cast by the top & left walls onto the floor
    fclip = s.clip(floor_d)
    TL = [P(i1 + 20, j0 - 30), P(i1 + 20, j0), P(i0, j0), P(i0, j1 + 20), P(i0 - 30, j1 + 20), P(i0 - 30, j0 - 30)]
    out.append(f'<g clip-path="{fclip}"><g filter="{s.blur(9)}" opacity="0.22"><path d="{path(TL)}" fill="#5a4a30" transform="translate(6,7)"/></g></g>')
    # subtle cardboard fibre noise
    tex = s.texture(freq=0.9, scale=0.8, seed=seed + 40, spec=0, gain=1.32, octaves=2, elev=50, region='x="-2%" y="-2%" width="104%" height="104%"')
    out.append(f'<path d="{outer_d}" fill="#F7F2EA" filter="{tex}" opacity="0.22" style="mix-blend-mode:multiply"/>')
    return "".join(out), floor_d, outer_d


def napkin(s, cx, cy, size, ang, seed=5, col="#E86A17"):
    """Orange paper napkin (folded square) with embossed border."""
    rng = random.Random(seed)
    a = math.radians(ang)
    hs = size / 2
    pts = [rot((x, y), a) for x, y in [(-hs, -hs), (hs, -hs), (hs, hs), (-hs, hs)]]
    pts = [(cx + x + rng.uniform(-3, 3), cy + y + rng.uniform(-3, 3)) for x, y in pts]
    d = "M" + "L".join(f"{f(x)},{f(y)}" for x, y in pts) + "Z"
    out = [s.shadow(d, 10, 12, 10, 0.4)]
    g = s.lin(cx - hs, cy - hs, cx + hs, cy + hs, [(0, mix(col, "#ffffff", 0.12)), (0.6, col), (1, mix(col, "#000000", 0.12))])
    out.append(f'<path d="{d}" fill="{g}"/>')
    # fold crease and embossed border
    inset = 18
    ip = [rot((x, y), a) for x, y in [(-hs + inset, -hs + inset), (hs - inset, -hs + inset), (hs - inset, hs - inset), (-hs + inset, hs - inset)]]
    idd = "M" + "L".join(f"{f(cx+x)},{f(cy+y)}" for x, y in ip) + "Z"
    out.append(f'<path d="{idd}" fill="none" stroke="#ffffff" stroke-opacity="0.22" stroke-width="2" stroke-dasharray="2 5" transform="translate(-1,-1)"/>')
    out.append(f'<path d="{idd}" fill="none" stroke="#7a3205" stroke-opacity="0.2" stroke-width="2" stroke-dasharray="2 5" transform="translate(1,1)"/>')
    m1 = rot((0, -hs), a); m2 = rot((0, hs), a)
    out.append(f'<path d="M{f(cx+m1[0])},{f(cy+m1[1])}L{f(cx+m2[0])},{f(cy+m2[1])}" stroke="#ffffff" stroke-opacity="0.25" stroke-width="2"/>')
    out.append(f'<path d="M{f(cx+m1[0]+2)},{f(cy+m1[1])}L{f(cx+m2[0]+2)},{f(cy+m2[1])}" stroke="#6a2b04" stroke-opacity="0.22" stroke-width="2"/>')
    tex = s.texture(freq=0.6, scale=1.2, seed=seed + 3, spec=0, gain=1.3, octaves=2, region='x="-2%" y="-2%" width="104%" height="104%"')
    out.append(f'<path d="{d}" fill="#ffffff" filter="{tex}" opacity="0.18" style="mix-blend-mode:multiply"/>')
    return "".join(out)


def paper_cup(s, cx, cy, r, sauce_col, sauce_hi, sauce_lo, seed=7, fill=0.72, gloss=0.65):
    """Pleated white paper dip cup seen from above, filled with a sauce."""
    rng = random.Random(seed)
    out = []
    circ = f"M{f(cx-r)},{f(cy)}a{f(r)},{f(r)} 0 1 0 {f(2*r)},0a{f(r)},{f(r)} 0 1 0 {f(-2*r)},0Z"
    out.append(s.shadow(circ, 10, 12, 9, 0.45))
    out.append(s.shadow(circ, 3, 4, 3, 0.35))
    g = s.rad(cx - r * 0.3, cy - r * 0.3, r * 1.4, [(0, "#ffffff"), (0.7, "#F3EEE6"), (1, "#E2D9CA")])
    out.append(f'<path d="{circ}" fill="{g}"/>')
    # pleats: thin radial wedges alternating light/dark across the sloped wall
    n = 44
    pl_d, pl_l = [], []
    ri = r * fill
    for i in range(n):
        a0 = 2 * math.pi * i / n
        a1 = a0 + 2 * math.pi / n * 0.5
        pts = [(cx + math.cos(a0) * ri, cy + math.sin(a0) * ri), (cx + math.cos(a0) * r, cy + math.sin(a0) * r),
               (cx + math.cos(a1) * r, cy + math.sin(a1) * r), (cx + math.cos(a1) * ri, cy + math.sin(a1) * ri)]
        dd = "M" + "L".join(f"{f(x)},{f(y)}" for x, y in pts) + "Z"
        (pl_d if i % 2 else pl_l).append(dd)
    out.append(f'<path d="{"".join(pl_d)}" fill="#b5a68c" opacity="0.18"/>')
    out.append(f'<path d="{"".join(pl_l)}" fill="#ffffff" opacity="0.5"/>')
    # wall shading (top-left inner wall in shade)
    wg = s.lin(cx - r, cy - r, cx + r, cy + r, [(0, "#000000", 0.16), (0.5, "#000000", 0.0), (1, "#ffffff", 0.2)])
    ring = f"M{f(cx-r)},{f(cy)}a{f(r)},{f(r)} 0 1 0 {f(2*r)},0a{f(r)},{f(r)} 0 1 0 {f(-2*r)},0ZM{f(cx-ri)},{f(cy)}a{f(ri)},{f(ri)} 0 1 1 {f(2*ri)},0a{f(ri)},{f(ri)} 0 1 1 {f(-2*ri)},0Z"
    out.append(f'<path d="{ring}" fill="{wg}" fill-rule="evenodd"/>')
    # rim lip
    out.append(f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r-2)}" fill="none" stroke="#ffffff" stroke-width="3" opacity="0.8"/>')
    # sauce surface
    sd = blob(cx, cy, ri * 1.0, ri * 1.0, rng, n=30, amp=0.015)
    sg = s.rad(cx - ri * 0.35, cy - ri * 0.4, ri * 1.6, [(0, sauce_hi), (0.5, sauce_col), (1, mix(sauce_col, sauce_lo, 0.6))])
    out.append(f'<path d="{sd}" fill="{sg}"/>')
    # inner shade where wall meets sauce (top-left)
    sc = s.clip(sd)
    out.append(f'<g clip-path="{sc}"><circle cx="{f(cx+ri*0.2)}" cy="{f(cy+ri*0.2)}" r="{f(ri*1.05)}" fill="none" stroke="#000" stroke-opacity="0.18" stroke-width="{f(ri*0.35)}" filter="{s.blur(6)}"/></g>')
    # soft satin swirl where the sauce was squeezed in
    sw = []
    for i in range(36):
        tt = i / 35
        th = 2 * math.pi * 1.2 * tt + 0.8
        rr_ = ri * (0.62 - 0.5 * tt)
        sw.append((cx + math.cos(th) * rr_, cy + math.sin(th) * rr_))
    swd = smooth_open(sw[::2])
    out.append(f'<path d="{swd}" stroke="{sauce_lo}" stroke-width="{f(ri*0.1)}" fill="none" opacity="0.22" stroke-linecap="round" transform="translate(3,4)" filter="{s.blur(3)}"/>')
    out.append(f'<path d="{swd}" stroke="{sauce_hi}" stroke-width="{f(ri*0.08)}" fill="none" opacity="0.4" stroke-linecap="round" filter="{s.blur(2)}"/>')
    # glossy highlight
    hx, hy = cx - ri * 0.38, cy - ri * 0.42
    out.append(f'<path d="M{f(hx-ri*0.25)},{f(hy+ri*0.18)}Q{f(hx)},{f(hy-ri*0.12)} {f(hx+ri*0.34)},{f(hy-ri*0.02)}" stroke="#ffffff" stroke-width="{f(ri*0.09)}" stroke-linecap="round" fill="none" opacity="{gloss}"/>')
    out.append(f'<ellipse cx="{f(cx+ri*0.35)}" cy="{f(cy+ri*0.32)}" rx="{f(ri*0.1)}" ry="{f(ri*0.06)}" fill="#ffffff" opacity="0.35" transform="rotate(-35 {f(cx+ri*0.35)} {f(cy+ri*0.32)})"/>')
    return "".join(out)


def plate_white(s, cx, cy, w, h, r=60, rim=46):
    """White ceramic rectangular plate with soft rim."""
    out = []
    d = rrect_path(cx - w / 2, cy - h / 2, w, h, r)
    out.append(s.shadow(d, 16, 18, 16, 0.42))
    out.append(s.shadow(d, 4, 5, 4, 0.35))
    g = s.lin(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2, [(0, "#ffffff"), (0.6, "#F6F4F0"), (1, "#E3DED6")])
    out.append(f'<path d="{d}" fill="{g}"/>')
    di = rrect_path(cx - w / 2 + rim, cy - h / 2 + rim, w - 2 * rim, h - 2 * rim, max(r - rim * 0.6, 10))
    # well: slightly darker, with soft shade at top-left inner edge
    g2 = s.lin(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2, [(0, "#EEEAE3"), (1, "#F8F6F2")])
    out.append(f'<path d="{di}" fill="{g2}" filter="{s.blur(3)}"/>')
    cl = s.clip(di)
    out.append(f'<g clip-path="{cl}"><path d="{di}" fill="none" stroke="#7c705c" stroke-opacity="0.2" stroke-width="16" transform="translate(7,8)" filter="{s.blur(7)}"/></g>')
    # rim highlight (bottom-right inner edge catches light)
    out.append(f'<path d="{di}" fill="none" stroke="#ffffff" stroke-width="3" opacity="0.8" transform="translate(1.5,1.5)" filter="{s.blur(1.2)}"/>')
    # glaze sheen
    sh = s.rad(cx - w * 0.3, cy - h * 0.35, w * 0.6, [(0, "#ffffff", 0.6), (1, "#ffffff", 0)])
    out.append(f'<path d="{d}" fill="{sh}"/>')
    return "".join(out), di
