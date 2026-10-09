"""Google listing data, built from shared/site.json and the menus:
- a JSON-LD block (schema.org FoodEstablishment: hours, cuisine, delivery area, menu with prices)
  in every restaurant page. Each restaurant stands on its own: no shared parent, no links between them
- sitemap.xml and robots.txt
Run after changing hours, areas, menus or the site address:   python3 build/seo.py
qa/check_site.py runs  python3 build/seo.py --check  and fails if the pages are out of date."""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
read = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read()
site = json.loads(read("shared/site.json"))
brands = [b["id"] for b in site["brands"] if b.get("status") != "hidden"]
# the site's public address, from the first restaurant page's og:url (…/dushi-wok/ -> …/)
BASE = re.search(r'<meta property="og:url" content="([^"]+)">', read(brands[0] + "/index.html")).group(1)[:-len(brands[0] + "/")]
menus = {b: json.loads(read(b + "/menu.json")) for b in brands}
DAYS = {"mon": "Monday", "tue": "Tuesday", "wed": "Wednesday", "thu": "Thursday", "fri": "Friday", "sat": "Saturday", "sun": "Sunday"}

def phone(b):
    n = next((x.get("whatsapp") for x in site["brands"] if x["id"] == b and x.get("whatsapp")), None) or site["whatsapp"]
    return "+" + n[:3] + " " + n[3:6] + " " + n[6:] if n.startswith("297") and len(n) == 10 else "+" + n

def hours():
    groups = {}
    for d, name in DAYS.items():
        h = site["hours"].get(d)
        if h: groups.setdefault(tuple(h), []).append("https://schema.org/" + name)
    return [{"@type": "OpeningHoursSpecification", "dayOfWeek": days, "opens": o, "closes": c} for (o, c), days in groups.items()]

def money(c): return "%.2f" % (c / 100)

def common(b):
    prices = [i["price"] for i in menus[b]["items"]]
    return {
        "telephone": phone(b),
        "priceRange": "ƒ%s–ƒ%s" % (money(min(prices)), money(max(prices))),
        "currenciesAccepted": "AWG, USD",
        "paymentAccepted": ", ".join(site.get("payWith") or ["Cash"]),
        "acceptsReservations": False,
        "address": {"@type": "PostalAddress", "addressCountry": "AW"},
        "areaServed": [{"@type": "Place", "name": a + ", Aruba"} for a in site["areas"]],
        "openingHoursSpecification": hours(),
    }

def brand_ld(b):
    m = menus[b]
    secs = []
    for s in m["sections"]:
        items = [i for i in m["items"] if i["section"] == s["id"]]
        if not items: continue
        secs.append({"@type": "MenuSection", "name": s["title"], "hasMenuItem": [dict(
            {"@type": "MenuItem", "name": i["name"], "description": i.get("desc", ""),
             "offers": {"@type": "Offer", "price": money(i["price"]), "priceCurrency": "AWG"}},
            **({"suitableForDiet": "https://schema.org/VegetarianDiet"} if "vegetarian" in (i.get("flags") or []) else {})) for i in items]})
    r = {"@context": "https://schema.org", "@type": "FoodEstablishment", "@id": BASE + b + "/#restaurant", "name": m["name"],
         "url": BASE + b + "/", "image": BASE + "shared/og/" + b + ".jpg", "description": m.get("intro") or m.get("tagline", ""),
         "servesCuisine": m["cuisine"]}
    r.update(common(b))
    r["hasMenu"] = {"@type": "Menu", "name": m["name"] + " menu", "hasMenuSection": secs}
    return r

def with_ld(html, data):
    block = '<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + "</script>"
    if re.search(r'<script type="application/ld\+json">.*?</script>', html, re.S):
        return re.sub(r'<script type="application/ld\+json">.*?</script>', lambda _: block, html, count=1, flags=re.S)
    return html.replace("</head>", block + "\n</head>", 1)

def outputs():
    out = {}
    for b in brands: out[b + "/index.html"] = with_ld(read(b + "/index.html"), brand_ld(b))
    urls = [BASE + b + "/" for b in brands]
    out["sitemap.xml"] = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + \
        "".join("  <url><loc>%s</loc></url>\n" % u for u in urls) + "</urlset>\n"
    out["robots.txt"] = "# Note: search engines only read robots.txt at the root of a domain. This file starts working\n" \
        "# once the site has its own domain; until then the sitemap is submitted in Google Search Console.\nUser-agent: *\nAllow: /\n\nSitemap: %ssitemap.xml\n" % BASE
    return out

if __name__ == "__main__":
    stale = []
    for p, text in outputs().items():
        f = os.path.join(ROOT, p)
        old = open(f, encoding="utf-8").read() if os.path.exists(f) else None
        if old != text:
            stale.append(p)
            if "--check" not in sys.argv: open(f, "w", encoding="utf-8").write(text)
    if "--check" in sys.argv:
        print("out of date: " + ", ".join(stale) if stale else "up to date"); sys.exit(1 if stale else 0)
    print("written: " + (", ".join(stale) if stale else "nothing changed"))
