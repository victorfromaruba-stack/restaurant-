"""Every check in one go, for the daily run and before any push: the four test suites (each serves the
repo itself and fakes every database call), then the live site and a read-only question to the live
order database. Never places an order and never changes anything live.
  python3 qa/check_all.py            all of it
  python3 qa/check_all.py --local    only the four suites (no internet)
Exit 0 only when everything passed."""
import json, os, re, subprocess, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE = "https://victorfromaruba-stack.github.io/restaurant-/"
SUITES = [("check_site.py", "pages, menus, languages"), ("check_api.py", "checkout and the order page"),
          ("check_kitchen.py", "chef app"), ("check_staff.py", "live orders, driver and admin screens")]
bad = 0

for name, what in SUITES:
    r = subprocess.run([sys.executable, os.path.join(ROOT, "qa", name)], cwd=ROOT, capture_output=True, text=True)
    lines = (r.stdout + r.stderr).strip().splitlines()
    passed = sum(1 for l in lines if l.startswith("PASS"))
    fails = [l for l in lines if l.startswith("FAIL")]
    ok = r.returncode == 0
    bad += not ok
    print(f"{'ok ' if ok else 'BAD'} {name:<17} {passed} passed, {len(fails)} failed  ({what})")
    for l in fails[:5]:
        print("      " + l[:200])

# check_site.py rewrites qa/wa-samples.json with new order numbers each run: keep it unless a ticket really changed
diff = subprocess.run(["git", "diff", "--unified=0", "--", "qa/wa-samples.json"], cwd=ROOT, capture_output=True, text=True).stdout
changed = [l for l in diff.splitlines() if l[:1] in "+-" and not l.startswith(("+++", "---"))]
if changed and all(re.sub(r"#\d{4}-[A-Z0-9]{2}", "", l[1:]) in {re.sub(r"#\d{4}-[A-Z0-9]{2}", "", x[1:]) for x in changed if x[0] != l[0]} for l in changed):
    subprocess.run(["git", "checkout", "--", "qa/wa-samples.json"], cwd=ROOT)
    print("    qa/wa-samples.json: only order numbers changed, put back")
elif changed:
    print("    qa/wa-samples.json: a ticket's words changed, commit it with your change")

if "--local" not in sys.argv:
    for path in ["", "taco-brava/", "checkout/", "order/", "ops/kitchen/", "driver/v2/"]:
        try:
            code = urllib.request.urlopen(LIVE + path, timeout=20).status
        except Exception as e:
            code = getattr(e, "code", str(e))
        ok = code == 200
        bad += not ok
        print(f"{'ok ' if ok else 'BAD'} live /{path:<14} {code}")
    js = open(os.path.join(ROOT, "shared/pidi.js"), encoding="utf-8").read()
    url = re.search(r"https://[a-z0-9]+\.supabase\.co", js).group(0)
    key = re.search(r"eyJ[A-Za-z0-9._-]+", js).group(0)
    req = urllib.request.Request(url + "/rest/v1/rpc/pidi_public_state", data=b"{}", method="POST",
                                 headers={"apikey": key, "Authorization": "Bearer " + key, "Content-Type": "application/json"})
    try:
        state = json.load(urllib.request.urlopen(req, timeout=20))
        ok = state.get("ok") is True
        note = f"delivery {state.get('eta_min')}–{state.get('eta_max')} min, busy +{state.get('busy_min')}"
    except Exception as e:
        ok, note = False, f"no answer ({e})"
    bad += not ok
    print(f"{'ok ' if ok else 'BAD'} order database     {note}")

print("all good" if not bad else f"{bad} thing(s) need fixing")
sys.exit(1 if bad else 0)
