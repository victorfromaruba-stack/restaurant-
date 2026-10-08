"""Shared helpers for the dish illustrations (SVG generation).
Everything is generated in global (canvas) coordinates so the single top-left
light source stays consistent even for rotated items."""
import math, random

LIGHT = (-0.7071, -0.7071)  # direction TO the light (top-left)


def f(v):
    s = f"{v:.1f}"
    if s.endswith(".0"):
        s = s[:-2]
    return "0" if s == "-0" else s


def rot(p, a, c=(0, 0)):
    ca, sa = math.cos(a), math.sin(a)
    x, y = p[0] - c[0], p[1] - c[1]
    return (c[0] + x * ca - y * sa, c[1] + x * sa + y * ca)


def smooth_closed(pts, t=1.0):
    n = len(pts)
    d = [f"M{f(pts[0][0])},{f(pts[0][1])}"]
    for i in range(n):
        p0, p1, p2, p3 = pts[(i - 1) % n], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6 * t, p1[1] + (p2[1] - p0[1]) / 6 * t)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6 * t, p2[1] - (p3[1] - p1[1]) / 6 * t)
        d.append(f"C{f(c1[0])},{f(c1[1])} {f(c2[0])},{f(c2[1])} {f(p2[0])},{f(p2[1])}")
    return "".join(d) + "Z"


def smooth_open(pts, t=1.0):
    n = len(pts)
    d = [f"M{f(pts[0][0])},{f(pts[0][1])}"]
    for i in range(n - 1):
        p0 = pts[max(i - 1, 0)]; p1 = pts[i]; p2 = pts[i + 1]; p3 = pts[min(i + 2, n - 1)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6 * t, p1[1] + (p2[1] - p0[1]) / 6 * t)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6 * t, p2[1] - (p3[1] - p1[1]) / 6 * t)
        d.append(f"C{f(c1[0])},{f(c1[1])} {f(c2[0])},{f(c2[1])} {f(p2[0])},{f(p2[1])}")
    return "".join(d)


def blob_pts(cx, cy, rx, ry, rng, n=28, amp=0.05, harm=(2, 3, 5, 7), a0=0.0, jitter=0.0):
    ph = [rng.uniform(0, 2 * math.pi) for _ in harm]
    am = [amp * rng.uniform(0.4, 1.0) / math.sqrt(k / 2) for k in harm]
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        r = 1 + sum(A * math.sin(k * a + p) for A, k, p in zip(am, harm, ph))
        r += rng.uniform(-jitter, jitter)
        x, y = math.cos(a) * rx * r, math.sin(a) * ry * r
        pts.append(rot((x, y), a0, (0, 0)))
    return [(cx + x, cy + y) for x, y in pts]


def blob(cx, cy, rx, ry, rng, **kw):
    return smooth_closed(blob_pts(cx, cy, rx, ry, rng, **kw))


def poly(cx, cy, s, rng, nmin=3, nmax=6, stretch=1.0, ang=None):
    n = rng.randint(nmin, nmax)
    angs = sorted(rng.uniform(0, 2 * math.pi) for _ in range(n))
    a0 = rng.uniform(0, math.pi) if ang is None else ang
    pts = []
    for a in angs:
        r = s * rng.uniform(0.45, 1.0)
        p = (math.cos(a) * r * stretch, math.sin(a) * r)
        p = rot(p, a0)
        pts.append((cx + p[0], cy + p[1]))
    return "M" + "L".join(f"{f(x)},{f(y)}" for x, y in pts) + "Z"


def rrect_path(x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    return (f"M{f(x+r)},{f(y)}H{f(x+w-r)}A{f(r)},{f(r)} 0 0 1 {f(x+w)},{f(y+r)}V{f(y+h-r)}"
            f"A{f(r)},{f(r)} 0 0 1 {f(x+w-r)},{f(y+h)}H{f(x+r)}A{f(r)},{f(r)} 0 0 1 {f(x)},{f(y+h-r)}"
            f"V{f(y+r)}A{f(r)},{f(r)} 0 0 1 {f(x+r)},{f(y)}Z")


def stadium_pts(cx, cy, length, dia, ang, rng=None, n_side=10, n_cap=10, amp=0.0, flat_end=None):
    """Points of a capsule (rounded log) centred at cx,cy, long axis at angle ang.
    flat_end: None, 'left' or 'right' -> that end is cut square (slightly rounded)."""
    r = dia / 2
    hl = length / 2 - r
    pts = []
    # top side left->right
    for i in range(n_side + 1):
        x = -hl + 2 * hl * i / n_side
        pts.append((x, -r))
    # right cap
    if flat_end == 'cutright':
        pts += [(hl + r * 0.5, -r), (hl + r, -r), (hl + r, 0), (hl + r, r), (hl + r * 0.5, r)]
    elif flat_end == 'right':
        pts += [(hl + r * 0.55, -r * 0.92), (hl + r * 0.68, -r * 0.4), (hl + r * 0.7, 0), (hl + r * 0.68, r * 0.4), (hl + r * 0.55, r * 0.92)]
    else:
        for i in range(1, n_cap):
            a = -math.pi / 2 + math.pi * i / n_cap
            pts.append((hl + math.cos(a) * r, math.sin(a) * r))
    for i in range(n_side + 1):
        x = hl - 2 * hl * i / n_side
        pts.append((x, r))
    if flat_end == 'left':
        pts += [(-hl - r * 0.55, r * 0.92), (-hl - r * 0.68, r * 0.4), (-hl - r * 0.7, 0), (-hl - r * 0.68, -r * 0.4), (-hl - r * 0.55, -r * 0.92)]
    elif flat_end == 'cutleft':
        pts += [(-hl - r * 0.5, r), (-hl - r, r), (-hl - r, 0), (-hl - r, -r), (-hl - r * 0.5, -r)]
    else:
        for i in range(1, n_cap):
            a = math.pi / 2 + math.pi * i / n_cap
            pts.append((-hl + math.cos(a) * r, math.sin(a) * r))
    out = []
    for (x, y) in pts:
        if rng is not None and amp:
            x += rng.uniform(-amp, amp); y += rng.uniform(-amp, amp)
        p = rot((x, y), ang)
        out.append((cx + p[0], cy + p[1]))
    return out


class Svg:
    def __init__(self, w=1400, h=800):
        self.w, self.h = w, h
        self.defs, self.body = [], []
        self.n = 0
        self.filters = {}

    def uid(self, p="i"):
        self.n += 1
        return f"{p}{self.n}"

    def add(self, s):
        self.body.append(s)

    def d(self, s):
        self.defs.append(s)

    # ---------- gradients ----------
    def lin(self, x1, y1, x2, y2, stops, user=True):
        gid = self.uid("g")
        units = ' gradientUnits="userSpaceOnUse"' if user else ""
        st = "".join(f'<stop offset="{o}" stop-color="{c}"' + (f' stop-opacity="{a}"' if a is not None else "") + "/>" for o, c, a in _norm(stops))
        self.d(f'<linearGradient id="{gid}"{units} x1="{f(x1)}" y1="{f(y1)}" x2="{f(x2)}" y2="{f(y2)}">{st}</linearGradient>')
        return f"url(#{gid})"

    def rad(self, cx, cy, r, stops, fx=None, fy=None, user=True, transform=None):
        gid = self.uid("g")
        units = ' gradientUnits="userSpaceOnUse"' if user else ""
        fxy = f' fx="{f(fx)}" fy="{f(fy)}"' if fx is not None else ""
        tr = f' gradientTransform="{transform}"' if transform else ""
        st = "".join(f'<stop offset="{o}" stop-color="{c}"' + (f' stop-opacity="{a}"' if a is not None else "") + "/>" for o, c, a in _norm(stops))
        self.d(f'<radialGradient id="{gid}"{units} cx="{f(cx)}" cy="{f(cy)}" r="{f(r)}"{fxy}{tr}>{st}</radialGradient>')
        return f"url(#{gid})"

    def clip(self, d):
        cid = self.uid("c")
        self.d(f'<clipPath id="{cid}"><path d="{d}"/></clipPath>')
        return f"url(#{cid})"

    # ---------- filters ----------
    def blur(self, sd):
        key = ("blur", sd)
        if key not in self.filters:
            fid = self.uid("fb")
            self.d(f'<filter id="{fid}" filterUnits="userSpaceOnUse" x="-200" y="-200" width="{self.w+400}" height="{self.h+400}"><feGaussianBlur stdDeviation="{sd}"/></filter>')
            self.filters[key] = f"url(#{fid})"
        return self.filters[key]

    def texture(self, freq=0.22, scale=5.0, seed=3, spec=0.35, spec_exp=18, blot=0.0, blot_freq=0.035,
                blot_col=(0.36, 0.17, 0.05), elev=48, gain=1.3, octaves=3, region=None, table=None, spec_elev=32):
        """Bump-mapped surface lighting (crumb / meat / paper texture), light from top-left."""
        key = ("tex", freq, scale, seed, spec, spec_exp, blot, blot_freq, blot_col, elev, gain, octaves, region, table, spec_elev)
        if key in self.filters:
            return self.filters[key]
        fid = self.uid("ft")
        reg = 'x="-15%" y="-15%" width="130%" height="130%"' if region is None else region
        parts = [f'<filter id="{fid}" {reg} color-interpolation-filters="sRGB">',
                 f'<feTurbulence type="fractalNoise" baseFrequency="{freq}" numOctaves="{octaves}" seed="{seed}" result="n0"/>',
                 (f'<feComponentTransfer in="n0" result="n1"><feFuncA type="table" tableValues="{table}"/></feComponentTransfer>' if table else '<feOffset in="n0" result="n1"/>'),
                 f'<feDiffuseLighting in="n1" surfaceScale="{scale}" diffuseConstant="1" lighting-color="#fff" result="dif"><feDistantLight azimuth="225" elevation="{elev}"/></feDiffuseLighting>']
        src = "SourceGraphic"
        if blot > 0:
            r, g, b = blot_col
            parts.append(f'<feTurbulence type="fractalNoise" baseFrequency="{blot_freq}" numOctaves="2" seed="{seed+17}" result="n2"/>')
            parts.append(f'<feColorMatrix in="n2" type="matrix" values="0 0 0 0 {r} 0 0 0 0 {g} 0 0 0 0 {b} {-2.4*blot} 0 0 0 {1.45*blot}" result="bl"/>')
            parts.append('<feComposite in="bl" in2="SourceGraphic" operator="atop" result="base"/>')
            src = "base"
        parts.append(f'<feComposite in="dif" in2="{src}" operator="arithmetic" k1="{gain}" k2="0" k3="0" k4="0" result="lit"/>')
        if spec > 0:
            parts.append(f'<feSpecularLighting in="n1" surfaceScale="{scale}" specularConstant="1" specularExponent="{spec_exp}" lighting-color="#fff4dc" result="sp"><feDistantLight azimuth="225" elevation="{spec_elev}"/></feSpecularLighting>')
            parts.append(f'<feComposite in="sp" in2="SourceAlpha" operator="in" result="sp2"/>')
            parts.append(f'<feComposite in="sp2" in2="lit" operator="arithmetic" k1="0" k2="{spec}" k3="1" k4="0" result="lit"/>')
        parts.append('<feComposite in="lit" in2="SourceAlpha" operator="in"/>')
        parts.append('</filter>')
        self.d("".join(parts))
        self.filters[key] = f"url(#{fid})"
        return self.filters[key]

    def shadow(self, shapes_d, dx, dy, sd, op, color="#000"):
        """Blurred shadow of a list of path d strings, offset by dx,dy."""
        if isinstance(shapes_d, str):
            shapes_d = [shapes_d]
        dd = "".join(shapes_d)
        return f'<g filter="{self.blur(sd)}" opacity="{op}"><path transform="translate({f(dx)},{f(dy)})" d="{dd}" fill="{color}"/></g>'

    # ---------- finishing ----------
    def finish(self, grain=0.06, vignette=0.16, grain_clip=None):
        gid = self.uid("fg")
        self.d(f'<filter id="{gid}" filterUnits="userSpaceOnUse" x="0" y="0" width="{self.w}" height="{self.h}" color-interpolation-filters="sRGB">'
               '<feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" seed="9" stitchTiles="stitch"/>'
               '<feColorMatrix type="matrix" values="0.33 0.33 0.33 0 0 0.33 0.33 0.33 0 0 0.33 0.33 0.33 0 0 0 0 0 0 1"/></filter>')
        cl = f' clip-path="{grain_clip}"' if grain_clip else ""
        self.add(f'<g{cl}><rect width="{self.w}" height="{self.h}" filter="url(#{gid})" opacity="{grain}" style="mix-blend-mode:overlay"/></g>')
        if vignette:
            v = self.rad(self.w / 2, self.h / 2, math.hypot(self.w, self.h) / 2,
                         [(0, "#000", 0), (0.55, "#000", 0), (1, "#000", vignette)])
            self.add(f'<rect width="{self.w}" height="{self.h}" fill="{v}"/>')

    def render(self):
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" width="{self.w}" height="{self.h}">'
                f'<defs>{"".join(self.defs)}</defs>{"".join(self.body)}</svg>')


def _norm(stops):
    out = []
    for s in stops:
        if len(s) == 2:
            out.append((s[0], s[1], None))
        else:
            out.append(s)
    return out


def mix(c1, c2, t):
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{int(round(a[i] + (b[i] - a[i]) * t)):02x}" for i in range(3))


def specks(groups):
    """groups: dict (color, opacity) -> list of path d. Returns markup with one path per group."""
    out = []
    for (col, op), ds in groups.items():
        if ds:
            out.append(f'<path d="{"".join(ds)}" fill="{col}" opacity="{op}"/>')
    return "".join(out)


def goo_filter(s, color, blur=8, thresh=(30, -6), spec=1.1, spec_exp=36, scale=16, hi_gain=1.15, elev=50, spec_elev=52):
    """Gooey liquid filter: merges soft blobs into one liquid shape and lights the blurred
    alpha as a height field, so the sauce gets glossy rims and bulges where blobs stack."""
    key = ("goo", color, blur, thresh, spec, spec_exp, scale, hi_gain, elev, spec_elev)
    if key in s.filters:
        return s.filters[key]
    fid = s.uid("goo")
    a, b = thresh
    s.d(f'<filter id="{fid}" filterUnits="userSpaceOnUse" x="0" y="0" width="{s.w}" height="{s.h}" color-interpolation-filters="sRGB">'
        f'<feGaussianBlur in="SourceAlpha" stdDeviation="{blur}" result="b"/>'
        f'<feColorMatrix in="b" type="matrix" values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 {a} {b}" result="shape"/>'
        f'<feGaussianBlur in="SourceAlpha" stdDeviation="{blur*1.3}" result="h"/>'
        f'<feDiffuseLighting in="h" surfaceScale="{scale}" diffuseConstant="1" lighting-color="#fff" result="dif0"><feDistantLight azimuth="225" elevation="{elev}"/></feDiffuseLighting>'
        f'<feGaussianBlur in="dif0" stdDeviation="1.4" result="dif"/>'
        f'<feSpecularLighting in="h" surfaceScale="{scale}" specularConstant="{spec}" specularExponent="{spec_exp}" lighting-color="#fff6e6" result="sp0"><feDistantLight azimuth="225" elevation="{spec_elev}"/></feSpecularLighting>'
        f'<feGaussianBlur in="sp0" stdDeviation="1.2" result="sp"/>'
        f'<feFlood flood-color="{color}" result="c"/>'
        f'<feComposite in="dif" in2="c" operator="arithmetic" k1="{hi_gain}" k2="0" k3="0" k4="0" result="lit"/>'
        f'<feComposite in="sp" in2="lit" operator="arithmetic" k1="0" k2="1" k3="1" k4="0" result="lit2"/>'
        f'<feComposite in="lit2" in2="shape" operator="in"/>'
        f'</filter>')
    s.filters[key] = f"url(#{fid})"
    return s.filters[key]
