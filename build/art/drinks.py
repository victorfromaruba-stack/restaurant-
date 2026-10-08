"""Shared drink cans (transparent, 600x600). usage: python3 drinks.py [ck cz sp]"""
import math, random, os, sys, subprocess
from artlib import Svg, f, mix, poly

HERE = os.path.dirname(os.path.abspath(__file__))
SVG_DIR = os.path.join(HERE, "drinks")
OUT_DIR = "/home/claude/work/brand-hub/shared/drinks"
RENDER = "/home/claude/work/tools/render_svg.py"

CX = 300
TOP = 86        # lid rim centre line
SHOULDER = 140  # body reaches full width
BODY_BOT = 486  # body ends, silver base taper starts
BOT = 520       # bottom rim centre line
HW = 124        # body half width
LW = 100        # lid half width
BW = 104        # base half width


def silhouette():
    return (f"M{CX-LW},{TOP}"
            f"C{CX-LW-6},{TOP+24} {CX-HW},{SHOULDER-22} {CX-HW},{SHOULDER}"
            f"L{CX-HW},{BODY_BOT}"
            f"C{CX-HW},{BOT-14} {CX-BW-6},{BOT-6} {CX-BW},{BOT}"
            f"A{BW},14 0 0 0 {CX+BW},{BOT}"
            f"C{CX+BW+6},{BOT-6} {CX+HW},{BOT-14} {CX+HW},{BODY_BOT}"
            f"L{CX+HW},{SHOULDER}"
            f"C{CX+HW},{SHOULDER-22} {CX+LW+6},{TOP+24} {CX+LW},{TOP}"
            f"A{LW},16 0 0 0 {CX-LW},{TOP}Z")


def cyl_overlay(s):
    """White/black alpha bands that turn a flat colour into a lit cylinder (light from the left)."""
    return s.lin(CX - HW, 0, CX + HW, 0, [
        (0, "#000", 0.55), (0.05, "#000", 0.28), (0.11, "#fff", 0.04), (0.165, "#fff", 0.35), (0.19, "#fff", 0.82),
        (0.215, "#fff", 0.82), (0.24, "#fff", 0.32), (0.3, "#fff", 0.06), (0.45, "#000", 0.02), (0.6, "#000", 0.1), (0.7, "#fff", 0.1),
        (0.75, "#fff", 0.2), (0.8, "#fff", 0.06), (0.88, "#000", 0.22), (0.96, "#000", 0.45), (1, "#000", 0.6)])


def silver(s, x0, x1):
    return s.lin(x0, 0, x1, 0, [
        (0, "#6E7277"), (0.08, "#A9AEB3"), (0.18, "#F4F6F8"), (0.24, "#D5D9DD"), (0.4, "#B9BEC3"),
        (0.6, "#9BA0A6"), (0.74, "#DCE0E4"), (0.82, "#A5AAB0"), (0.94, "#6A6E73"), (1, "#53575B")])


def can(s, body, bands=(), splash=None, seed=1, mist_op=0.18):
    rng = random.Random(seed)
    sil = silhouette()
    out = []
    # soft ground shadow
    out.append(f'<ellipse cx="{CX+14}" cy="{BOT+6}" rx="{HW+26}" ry="20" fill="#000" opacity="0.32" filter="{s.blur(10)}"/>')
    out.append(f'<ellipse cx="{CX+4}" cy="{BOT+2}" rx="{BW+6}" ry="10" fill="#000" opacity="0.4" filter="{s.blur(4)}"/>')
    cid = s.uid("cc")
    s.d(f'<clipPath id="{cid}"><path d="{sil}"/></clipPath>')
    out.append(f'<g clip-path="url(#{cid})">')
    # painted body (incl. neck)
    if isinstance(body, tuple):
        g = s.lin(0, SHOULDER, 0, BODY_BOT, [(0, body[0]), (1, body[1])])
    else:
        g = body
    out.append(f'<rect x="{CX-HW-2}" y="{TOP-20}" width="{2*HW+4}" height="{BODY_BOT-TOP+22}" fill="{g}"/>')
    for (y, h, col) in bands:
        out.append(f'<rect x="{CX-HW-2}" y="{y}" width="{2*HW+4}" height="{h}" fill="{col}"/>')
    if splash:
        out.append(splash)
    # cylinder lighting
    out.append(f'<rect x="{CX-HW-2}" y="{TOP-20}" width="{2*HW+4}" height="{BODY_BOT-TOP+22}" fill="{cyl_overlay(s)}"/>')
    # neck shoulder: tapered band catches a horizontal glint, darker just above the body
    ng = s.lin(0, TOP, 0, SHOULDER + 6, [(0, "#000", 0.25), (0.35, "#fff", 0.22), (0.6, "#000", 0.18), (0.92, "#000", 0.3), (1, "#000", 0)])
    out.append(f'<rect x="{CX-HW-2}" y="{TOP}" width="{2*HW+4}" height="{SHOULDER-TOP+6}" fill="{ng}"/>')
    # silver base taper
    out.append(f'<rect x="{CX-HW-2}" y="{BODY_BOT}" width="{2*HW+4}" height="{BOT-BODY_BOT+20}" fill="{silver(s, CX-HW, CX+HW)}"/>')
    bg = s.lin(0, BODY_BOT, 0, BOT + 14, [(0, "#000", 0.35), (0.12, "#000", 0.0), (0.5, "#fff", 0.12), (1, "#000", 0.35)])
    out.append(f'<rect x="{CX-HW-2}" y="{BODY_BOT}" width="{2*HW+4}" height="{BOT-BODY_BOT+20}" fill="{bg}"/>')
    out.append(f'<path d="M{CX-HW},{BODY_BOT+1}H{CX+HW}" stroke="#000" stroke-opacity="0.35" stroke-width="2"/>')
    # condensation: fine mist + a few droplets
    mist = []
    for _ in range(420):
        x = rng.uniform(CX - HW + 4, CX + HW - 4); y = rng.uniform(SHOULDER + 10, BODY_BOT - 6)
        mist.append(f"M{f(x)},{f(y)}h1.2")
    out.append(f'<path d="{"".join(mist)}" stroke="#fff" stroke-width="1.2" stroke-linecap="round" opacity="{mist_op}"/>')
    drops = []
    for _ in range(18):
        x = rng.uniform(CX - HW + 18, CX + HW - 16); y = rng.uniform(SHOULDER + 30, BODY_BOT - 20)
        r = rng.uniform(3.0, 8.5) if rng.random() < 0.8 else rng.uniform(9, 11)
        ry = r * rng.uniform(1.05, 1.35)
        drops.append(
            f'<ellipse cx="{f(x+1)}" cy="{f(y+1.5)}" rx="{f(r)}" ry="{f(ry)}" fill="#000" opacity="0.22"/>'
            f'<ellipse cx="{f(x)}" cy="{f(y)}" rx="{f(r)}" ry="{f(ry)}" fill="#fff" opacity="0.14"/>'
            f'<path d="M{f(x-r*0.8)},{f(y+ry*0.2)}A{f(r)},{f(ry)} 0 0 1 {f(x+r*0.7)},{f(y-ry*0.5)}" stroke="#000" stroke-opacity="0.25" stroke-width="1" fill="none"/>'
            f'<path d="M{f(x-r*0.5)},{f(y+ry*0.75)}A{f(r)},{f(ry)} 0 0 0 {f(x+r*0.75)},{f(y+ry*0.3)}" stroke="#fff" stroke-opacity="0.7" stroke-width="1.2" fill="none"/>'
            f'<ellipse cx="{f(x-r*0.35)}" cy="{f(y-ry*0.4)}" rx="{f(r*0.28)}" ry="{f(ry*0.22)}" fill="#fff" opacity="0.95"/>')
    out.append("".join(drops))
    out.append('</g>')
    # lid: rim, recessed panel, tab
    out.append(f'<ellipse cx="{CX}" cy="{TOP}" rx="{LW}" ry="16" fill="{silver(s, CX-LW, CX+LW)}"/>')
    out.append(f'<ellipse cx="{CX}" cy="{TOP+1.5}" rx="{LW-9}" ry="12.5" fill="#8C9197"/>')
    pg = s.lin(CX - LW, TOP - 10, CX + LW, TOP + 12, [(0, "#B9BEC4"), (0.35, "#E9ECEF"), (0.7, "#A7ACB2"), (1, "#80858B")])
    out.append(f'<ellipse cx="{CX}" cy="{TOP+2.5}" rx="{LW-13}" ry="10.5" fill="{pg}"/>')
    out.append(f'<ellipse cx="{CX}" cy="{TOP}" rx="{LW-1}" ry="15.2" fill="none" stroke="#fff" stroke-opacity="0.75" stroke-width="1.6"/>')
    # opening score + ring-pull tab
    out.append(f'<path d="M{CX-16},{TOP+6}Q{CX},{TOP+12} {CX+16},{TOP+6}Q{CX+10},{TOP+1} {CX},{TOP+1}Q{CX-10},{TOP+1} {CX-16},{TOP+6}Z" fill="none" stroke="#6E7378" stroke-width="1.1" opacity="0.8"/>')
    out.append(f'<rect x="{CX-17}" y="{TOP-7}" width="34" height="11" rx="5.5" fill="#CDD1D6" stroke="#7A7F85" stroke-width="1"/>')
    out.append(f'<rect x="{CX-9}" y="{TOP-4.5}" width="18" height="5.5" rx="2.7" fill="#8E9399"/>')
    out.append(f'<ellipse cx="{CX}" cy="{TOP+3}" rx="3" ry="1.8" fill="#9DA2A8" stroke="#6E7378" stroke-width="0.8"/>')
    out.append(f'<path d="M{CX-LW+20},{TOP-7}Q{CX-30},{TOP-14} {CX+10},{TOP-13}" stroke="#fff" stroke-width="2" fill="none" opacity="0.7" stroke-linecap="round"/>')
    # grain clipped to the can
    gid = s.uid("gr")
    s.d(f'<filter id="{gid}" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" seed="4"/>'
        f'<feColorMatrix type="matrix" values="0.33 0.33 0.33 0 0 0.33 0.33 0.33 0 0 0.33 0.33 0.33 0 0 0 0 0 0 1"/></filter>')
    cid2 = s.uid("cg")
    s.d(f'<clipPath id="{cid2}"><path d="{sil}"/><ellipse cx="{CX}" cy="{TOP}" rx="{LW}" ry="16"/></clipPath>')
    out.append(f'<g clip-path="url(#{cid2})"><rect x="150" y="60" width="300" height="480" filter="url(#{gid})" opacity="0.05" style="mix-blend-mode:overlay"/></g>')
    return "".join(out)


def can_ck():
    s = Svg(600, 600)
    s.add(can(s, ("#EA2430", "#D61B27"), seed=3))
    return s


def can_cz():
    s = Svg(600, 600)
    s.add(can(s, ("#1A1A1A", "#121212"), bands=((SHOULDER + 8, 9, "#E41E2B"), (BODY_BOT - 22, 9, "#E41E2B")), seed=5, mist_op=0.1))
    return s


def can_sp():
    s = Svg(600, 600)
    # lime-yellow diagonal splash band with soft wavy edges
    pts_top, pts_bot = [], []
    n = 16
    for i in range(n + 1):
        t = i / n
        x = CX - HW - 6 + (2 * HW + 12) * t
        yc = 372 - 150 * t
        w = 34 + 8 * math.sin(t * 7.5) + 6 * math.sin(t * 13 + 1)
        pts_top.append((x, yc - w + 4 * math.sin(t * 19)))
        pts_bot.append((x, yc + w * 0.8 + 5 * math.sin(t * 15 + 2)))
    from artlib import smooth_closed
    band = smooth_closed(pts_top + pts_bot[::-1])
    bg = s.lin(CX - HW, 360, CX + HW, 230, [(0, "#C9D72E"), (0.5, "#D7E33B"), (1, "#E3EC6A")])
    splash = f'<path d="{band}" fill="{bg}"/>'
    s.add(can(s, ("#00A651", "#007A3D"), splash=splash, seed=7))
    return s


DRINKS = {"ck": can_ck, "cz": can_cz, "sp": can_sp}

if __name__ == "__main__":
    os.makedirs(SVG_DIR, exist_ok=True)
    ids = [a for a in sys.argv[1:] if a in DRINKS] or list(DRINKS)
    for i in ids:
        s = DRINKS[i]()
        p = os.path.join(SVG_DIR, f"{i}.svg")
        open(p, "w").write(s.render())
        subprocess.run(["python3", RENDER, p, os.path.join(OUT_DIR, f"{i}.webp"), "600", "600", "--alpha", "--quality", "82"], check=True)
