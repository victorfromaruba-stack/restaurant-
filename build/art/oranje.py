"""Oranje Snack dish illustrations. usage: python3 oranje.py [ids...]"""
import math, random, sys, os, subprocess
from artlib import Svg, f, rot, smooth_closed, smooth_open, blob, blob_pts, poly, mix, specks, stadium_pts, goo_filter
from scenes import delft_bg, tray, napkin, paper_cup, plate_white
import food

HERE = os.path.dirname(os.path.abspath(__file__))
SVG_DIR = os.path.join(HERE, "oranje-snack")
OUT_DIR = "/home/claude/work/brand-hub/oranje-snack/assets/art"
RENDER = "/home/claude/work/tools/render_svg.py"

CURRY = ("#F1A253", "#FBC88C", "#C97A33")  # col, hi, lo  (pale orange curry mayo)
MAYO = ("#F6F0DC", "#FFFFFF", "#D8CBA8")
MUSTARD = ("#D6A02A", "#F0C95C", "#A8761A")


def in_floor(rng, x0, y0, x1, y1):
    return lambda: (rng.uniform(x0, x1), rng.uniform(y0, y1))


# ---------------------------------------------------------------- bitterballen
def dish_bb():
    s = Svg(); rng = random.Random(101)
    delft_bg(s, seed=3)
    s.add(napkin(s, 60, 790, 280, 24, seed=4))
    s.add(paper_cup(s, 1180, 585, 78, *CURRY, seed=8))
    cx, cy = 700, 400
    t, floor_d, _ = tray(s, cx, cy, 580, 500, ang=-2.0, wall=34, seed=3)
    s.add(t)
    # 3-2-3 packing, slightly loose and organic
    R = 63
    sp = 134
    rows = [(-sp * 0.866, [-sp, 0, sp]), (0, [-sp / 2, sp / 2]), (sp * 0.866, [-sp, 0, sp])]
    balls = []
    for ry, xs in rows:
        for x in xs:
            balls.append((cx + x + rng.uniform(-7, 7), cy + ry + rng.uniform(-6, 6), R * rng.uniform(0.95, 1.04)))
    # curry mayo dots on the tray floor in the gaps (drawn before the balls)
    fl = []
    gaps = [(cx - sp * 1.02, cy - 4, 14), (cx + sp * 1.03, cy + 6, 13), (cx - sp * 0.9, cy + 36, 8),
            (cx + 2, cy - sp * 0.43 - 2, 9), (cx - 4, cy + sp * 0.45, 10), (cx + sp * 0.92, cy - 30, 8),
            (cx - sp * 1.42, cy - sp * 1.12, 8), (cx + sp * 1.45, cy + sp * 1.1, 9)]
    s.add("".join(food.sauce_dot(s, x, y, r * 1.15, *CURRY, rng) for x, y, r in gaps))
    # parsley on the floor
    s.add(food.parsley(s, lambda: (rng.uniform(cx - 240, cx + 240), rng.uniform(cy - 200, cy + 200)), 55, rng))
    def near_balls():
        x, y, r = balls[rng.randrange(len(balls))]
        a = rng.uniform(0, 2 * math.pi); t_ = r * rng.uniform(1.0, 1.5)
        return (x + math.cos(a) * t_, y + math.sin(a) * t_)
    s.add(food.loose_crumbs(s, near_balls, 70, rng))
    # balls
    bodies, sh = [], []
    for (x, y, r) in balls:
        b, d = food.fried_ball(s, x, y, r, rng)
        bodies.append(b); sh.append((x, y, r, d))
    s.add(food.ball_shadows(s, sh))
    s.add("".join(bodies))
    # small dots of curry mayo on top of some balls
    tops = []
    for i in (0, 2, 4, 6):
        x, y, r = balls[i]
        tops.append((x - r * 0.08 + rng.uniform(-6, 6), y - r * 0.12 + rng.uniform(-6, 6), 12.5))
    s.add("".join(food.sauce_dot(s, x, y, r, *CURRY, rng) for x, y, r in tops))
    # parsley over the balls
    def on_balls():
        x, y, r = balls[rng.randrange(len(balls))]
        a = rng.uniform(0, 2 * math.pi); t = math.sqrt(rng.random()) * r * 0.8
        return (x + math.cos(a) * t, y + math.sin(a) * t)
    s.add(food.parsley(s, on_balls, 48, rng, size=(1.6, 3.6)))
    # two cocktail picks
    for i, ang in ((0, -128), (7, -40)):
        x, y, r = balls[i]
        s.add(pick(s, x, y, r, ang))
    s.finish()
    return s


def pick(s, x, y, r, ang_deg, length=95):
    a = math.radians(ang_deg)
    ux, uy = math.cos(a), math.sin(a)
    x0, y0 = x + ux * r * 0.15, y + uy * r * 0.15
    x1, y1 = x + ux * (r * 0.15 + length), y + uy * (r * 0.15 + length)
    out = []
    out.append(f'<path d="M{f(x0+10)},{f(y0+14)}L{f(x1+22)},{f(y1+26)}" stroke="#000" stroke-width="7" stroke-linecap="round" opacity="0.35" filter="{s.blur(3.5)}"/>')
    nx, ny = -uy, ux
    if nx * -0.707 + ny * -0.707 < 0:
        nx, ny = -nx, -ny
    g = s.lin(x0 + nx * 3.5, y0 + ny * 3.5, x0 - nx * 3.5, y0 - ny * 3.5, [(0, "#F6E3BC"), (0.4, "#E2C08A"), (1, "#A5804A")])
    out.append(f'<path d="M{f(x0)},{f(y0)}L{f(x1)},{f(y1)}" stroke="{g}" stroke-width="7" stroke-linecap="round"/>')
    # rounded end
    out.append(f'<circle cx="{f(x1)}" cy="{f(y1)}" r="3.4" fill="#D7B47E"/>')
    # crumbs pushed up around the entry point
    return "".join(out)



# ---------------------------------------------------------------- kroket
def dish_kr():
    s = Svg(); rng = random.Random(202)
    delft_bg(s, seed=5, ox=-110, oy=-60)
    s.add(napkin(s, 1330, 30, 280, -16, seed=6))
    cx, cy = 700, 405
    t, floor_d, _ = tray(s, cx, cy, 690, 480, ang=1.5, wall=34, seed=4)
    s.add(t)
    D = 106
    # mustard smear on the tray floor (under the croquettes)
    s.add(food.mustard_goo(s, (520, 560), (720, 615), (965, 552), 36, rng))
    # whole croquette
    k1 = (705, 288, 330, D, -5)
    # cut croquette: left half (hidden face) and right half showing the bias-cut ragout face
    k2 = (606, 452, 170, D, 6)
    k3c = (766, 462)  # face centre of the right half (just cut, pieces still close)
    k3_ang = 3
    P, (ex, ey), _ = food.axis_frame(k3c[0], k3c[1], k3_ang)
    body_len = 150
    bc = P(body_len / 2, 0)
    def near_logs():
        q = [(705, 288, 175, 62), (606, 452, 95, 60), (830, 462, 120, 60)][rng.randrange(3)]
        return (q[0] + rng.uniform(-q[2], q[2]), q[1] + rng.choice([-1, 1]) * q[3] * rng.uniform(0.95, 1.4))
    s.add(food.loose_crumbs(s, near_logs, 55, rng))
    s.add(food.log_shadow(s, *k1))
    s.add(food.log_shadow(s, *k2))
    s.add(food.log_shadow(s, bc[0] - 30 * ex, bc[1] - 30 * ey, body_len + 60, D, k3_ang))
    m, _ = food.fried_log(s, *k1, rng)
    s.add(m)
    m, _ = food.fried_log(s, *k2, rng)
    s.add(m)
    m, _ = food.fried_log(s, bc[0], bc[1], body_len, D, k3_ang, rng, flat_end='cutleft')
    s.add(m)
    # face: ellipse elongated along the axis (bias cut tilted toward the light)
    m, _ = food.ragout_face(s, k3c[0], k3c[1], D * 0.62, D * 0.5, k3_ang, rng)
    s.add(m)
    s.finish()
    return s


# ---------------------------------------------------------------- frikandel speciaal
def dish_fk():
    s = Svg(); rng = random.Random(303)
    delft_bg(s, seed=7, ox=-30, oy=-90)
    s.add(napkin(s, 70, 40, 280, 20, seed=8))
    cx, cy, ang = 700, 405, -17
    t, floor_d, _ = tray(s, cx, cy, 820, 252, ang=ang, wall=32, r=18, seed=6)
    s.add(t)
    L, D = 728, 108
    s.add(food.log_shadow(s, cx, cy, L, D * 0.95, ang))
    m, d, P = food.frikandel(s, cx, cy, L, D, ang, rng)
    s.add(m)
    s.add(food.frik_split_fill(s, P, L, D, rng))
    u0, u1 = -L / 2 + 58, L / 2 - 58
    # curry ketchup along the split, mayo alongside, then raw onion on top
    s.add(food.goo_line(s, P, u0, u1, 13, 21, rng, "#7A170D", wave=3, waves=6, blur=6, scale=9, spec=1.0, spec_exp=40, hi_gain=1.2))
    s.add(food.goo_line(s, P, u0 + 10, u1 - 8, -20, 16, rng, "#ECE4CE", wave=4, waves=8, shadow=0.35, blur=6, scale=9, spec=0.7, spec_exp=30, hi_gain=1.22))
    def onion_pt():
        u = rng.uniform(u0 + 6, u1 - 6); v = rng.gauss(-2, D * 0.17)
        return P(u, v)
    s.add(food.onion_cubes(s, onion_pt, 85, rng, size=(7, 12)))
    s.finish()
    return s


# ---------------------------------------------------------------- mixed snack box
def dish_mx():
    s = Svg(); rng = random.Random(404)
    delft_bg(s, seed=9, ox=-150, oy=-30)
    s.add(napkin(s, 1340, 760, 290, 30, seed=10))
    cx, cy = 700, 400
    t, floor_d, _ = tray(s, cx, cy, 730, 570, ang=0.8, wall=34, seed=8)
    s.add(t)
    # fries pile on the left
    def reg(li):
        spread = [1.0, 0.85, 0.65][li]
        x = 492 + rng.gauss(0, 46 * spread); y = 400 + rng.uniform(-190, 190) * spread
        return (x, y, 90 + rng.gauss(0, 40))
    fx = s.texture(freq=0.06, scale=0.8, seed=61, spec=0.35, spec_exp=16, gain=1.3, octaves=2, region='x="-5%" y="-5%" width="110%" height="110%"')
    s.add(food.fries_pile(s, reg, [24, 18, 12], rng, L=(130, 190), W=(24, 28), tex=fx))
    # kroket top right
    k = (812, 228, 300, 98, -3)
    s.add(food.log_shadow(s, *k))
    m, _ = food.fried_log(s, *k, rng)
    s.add(m)
    # half frikandel at the bottom
    fk = (790, 588, 320, 72, -4)
    s.add(food.log_shadow(s, *fk))
    m, d, P = food.frikandel(s, *fk, rng, half='cutleft')
    s.add(m)
    # 4 bitterballen
    R = 52
    balls = [(684, 352, R), (794, 345, R * 1.02), (690, 466, R * 0.98), (800, 460, R)]
    bodies, sh = [], []
    for (x, y, r) in balls:
        b, dd = food.fried_ball(s, x, y, r, rng)
        bodies.append(b); sh.append((x, y, r, dd))
    s.add(food.ball_shadows(s, sh))
    s.add("".join(bodies))
    # sauce cups: mayo and mustard
    s.add(paper_cup(s, 955, 362, 56, *MAYO, seed=12))
    s.add(paper_cup(s, 955, 488, 56, "#DCA628", "#E8BC42", "#C8921E", seed=13, gloss=0.35))
    s.finish()
    return s


# ---------------------------------------------------------------- chicken saté
def dish_st():
    s = Svg(); rng = random.Random(505)
    delft_bg(s, seed=11, ox=-80, oy=-120)
    s.add(napkin(s, 60, 60, 280, -22, seed=12))
    cx, cy = 700, 400
    pl, well = plate_white(s, cx, cy, 740, 540, r=70, rim=40)
    s.add(pl)
    ang = -10
    sk = []
    centers = [(655, 262), (672, 398), (689, 534)]
    chunks = []  # per skewer list of (x, y, w, h)
    Ps = []
    for (x, y) in centers:
        P, _, _ = food.axis_frame(x, y, ang)
        Ps.append(P)
        sk.append(food.skewer_stick(s, P, -300, 215))
        row = []
        for i in range(4):
            u = -165 + i * 104 + rng.uniform(-4, 4)
            p = P(u, rng.uniform(-4, 4))
            row.append((p[0], p[1], rng.uniform(98, 108), rng.uniform(80, 88)))
        chunks.append(row)
    s.add("".join(sk))
    flat = [c for row in chunks for c in row]
    s.add(f'<g filter="{s.blur(10)}" opacity="0.4">' + "".join(f'<ellipse cx="{f(x+12)}" cy="{f(y+15)}" rx="{f(w/2)}" ry="{f(h/2)}"/>' for x, y, w, h in flat) + '</g>')
    s.add(f'<g filter="{s.blur(3.5)}" opacity="0.5">' + "".join(f'<ellipse cx="{f(x+4)}" cy="{f(y+5)}" rx="{f(w/2-3)}" ry="{f(h/2-3)}"/>' for x, y, w, h in flat) + '</g>')
    for (x, y, w, h) in flat:
        m, _ = food.sate_chunk(s, x, y, w, h, ang, rng)
        s.add(m)
    # peanut sauce ladled over the middle of each skewer, running down onto the plate
    circ = []
    for si, row in enumerate(chunks):
        P = Ps[si]
        for i in (1, 2):
            x, y, w, h = row[i]
            for _ in range(4):
                circ.append((x + rng.uniform(-22, 22), y + rng.uniform(-16, 16), rng.uniform(26, 36), 0.3))
        m1 = row[1]; m2 = row[2]
        circ.append(((m1[0] + m2[0]) / 2, (m1[1] + m2[1]) / 2 + 6, 34, 0.3))
        circ.append(((m1[0] + m2[0]) / 2, (m1[1] + m2[1]) / 2 + 20, 28, 0.3))
        # drips / pooling below the skewer
        for k in range(6):
            u = rng.uniform(-70, 120)
            q = P(u, rng.uniform(36, 62))
            circ.append((q[0], q[1], rng.uniform(16, 26), 0.26))
            circ.append((q[0] + 4, q[1] + 3, rng.uniform(12, 18), 0.22))

    body = "".join(f'<circle cx="{f(x)}" cy="{f(y)}" r="{f(r)}" fill="#000" fill-opacity="{o}"/>' for x, y, r, o in circ)
    s.add(f'<g filter="{s.blur(6)}" opacity="0.45" transform="translate(5,7)">{body}</g>')
    flt = goo_filter(s, "#6C3B14", blur=9, scale=11, spec=0.95, spec_exp=38, hi_gain=1.12)
    s.add(f'<g filter="{flt}">{body}</g>')
    # ground peanut bits on the sauce
    grp = {("#D7A469", 0.75): [], ("#4a2408", 0.5): []}
    for (x, y, r, o) in circ:
        if r > 28:
            for _ in range(3):
                a = rng.uniform(0, 2 * math.pi); tt = math.sqrt(rng.random()) * r * 0.75
                grp[("#D7A469", 0.75) if rng.random() < 0.6 else ("#4a2408", 0.5)].append(poly(x + math.cos(a) * tt, y + math.sin(a) * tt, rng.uniform(1.2, 2.6), rng))
    s.add(specks(grp))
    # cucumber and shallot on the right
    cuc = [(988, 250, 38), (1006, 318, 37), (986, 386, 38)]
    for (x, y, r) in cuc:
        s.add(food.cucumber_slice(s, x, y, r, rng))
    rings = [(972, 470, 30, 24, 20, None), (1010, 528, 24, 18, -30, None), (958, 560, 20, 15, 10, (20, 290)),
             (1018, 296, 18, 14, 40, None)]
    for (x, y, rx, ry, a, arc) in rings:
        s.add(food.shallot_ring(s, x, y, rx, ry, a, rng, arc))
    s.finish()
    return s


# ---------------------------------------------------------------- fries with mayo
def dish_fs():
    s = Svg(); rng = random.Random(606)
    delft_bg(s, seed=13, ox=-20, oy=-50)
    s.add(napkin(s, 1350, 60, 280, 14, seed=14))
    cx, cy = 700, 405
    t, floor_d, _ = tray(s, cx, cy, 600, 540, ang=-3, wall=32, seed=10)
    s.add(t)
    def reg(li):
        spread = [1.0, 0.82, 0.6, 0.42][li]
        a = rng.uniform(0, 2 * math.pi); r = math.sqrt(rng.random())
        return (cx + math.cos(a) * r * 235 * spread, cy + math.sin(a) * r * 215 * spread, rng.uniform(0, 180))
    fx = s.texture(freq=0.06, scale=0.8, seed=61, spec=0.35, spec_exp=16, gain=1.3, octaves=2, region='x="-5%" y="-5%" width="110%" height="110%"')
    s.add(food.fries_pile(s, reg, [44, 36, 26, 14], rng, L=(130, 205), W=(25, 30), tex=fx))
    mx_, my_ = 728, 380
    s.add(food.mayo_goo(s, mx_, my_, 74, rng))
    def pep():
        if rng.random() < 0.55:
            a = rng.uniform(0, 2 * math.pi); r = math.sqrt(rng.random()) * 110
            return (mx_ + math.cos(a) * r, my_ + math.sin(a) * r)
        return (rng.uniform(cx - 230, cx + 230), rng.uniform(cy - 210, cy + 210))
    s.add(food.pepper(pep, 140, rng))
    s.finish()
    return s

# ---------------------------------------------------------------- build
DISHES = {"bb": dish_bb, "kr": dish_kr, "fk": dish_fk, "mx": dish_mx, "st": dish_st, "fs": dish_fs}


def build(ids):
    os.makedirs(SVG_DIR, exist_ok=True)
    for i in ids:
        s = DISHES[i]()
        p = os.path.join(SVG_DIR, f"{i}.svg")
        open(p, "w").write(s.render())
        q = sys.argv[sys.argv.index("--quality") + 1] if "--quality" in sys.argv else "80"
        subprocess.run(["python3", RENDER, p, os.path.join(OUT_DIR, f"{i}.webp"), "1400", "800", "--quality", q], check=True)


if __name__ == "__main__":
    ids = [a for a in sys.argv[1:] if a in DISHES] or list(DISHES)
    build(ids)
