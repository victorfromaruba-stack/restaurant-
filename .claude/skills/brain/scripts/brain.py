#!/usr/bin/env python3
"""Order Aruba's memory between sessions: small helpers for .claude/brain/.

    python3 .claude/skills/brain/scripts/brain.py check
        Sizes, dates, and anything that must never be in a public repo. Exit 1 on a problem.
    python3 .claude/skills/brain/scripts/brain.py add lessons "What happens, and what to do"
    python3 .claude/skills/brain/scripts/brain.py add victor "He decided X (his words: '...')"
    python3 .claude/skills/brain/scripts/brain.py add journal "claude (cloud) · shipped X (abc1234) · waiting: Y"
    python3 .claude/skills/brain/scripts/brain.py add idea "H · S · <idea> · done when: <check>"
    python3 .claude/skills/brain/scripts/brain.py add question "Plain question with the choice spelled out"
    python3 .claude/skills/brain/scripts/brain.py recent
        The last journal lines and the open ideas, for planning.

`add` puts today's date on the entry and inserts it where that file keeps its newest lines.
"""
import datetime
import re
import sys
from pathlib import Path

BRAIN = Path(__file__).resolve().parents[3] / "brain"
FILES = {"lessons": "lessons.md", "victor": "victor.md", "journal": "journal.md", "idea": "ideas.md",
         "ideas": "ideas.md", "question": "questions.md", "questions": "questions.md"}
LIMITS = {"lessons.md": 60, "victor.md": 50, "questions.md": 30, "ideas.md": 60, "journal.md": 110}
# Public repo. These must never be written down here.
NEVER = [
    (r"github_pat_\w{10,}|ghp_\w{10,}|sk-ant-\w{10,}|AIza[\w-]{20,}|bk_live_[\w-]{20,}|eyJhbGci\w{10,}", "a key or token"),
    (r"\b(food cost|cost price|buyer price|margin|markup|profit per|supplier price)\b", "costs or margins (public repo)"),
    (r"\b[\w.+-]+@[\w-]+\.[\w.]+\b", "an email address"),
    (r"\+?297[\s-]?\d{3}[\s-]?\d{4}(?![\d])", "a phone number (the shop's own WhatsApp is in site.json; customers' never go here)"),
    (r"\bpassword\b\s*[:=]", "a password"),
]


def today():
    return datetime.date.today().isoformat()


def add(kind, text):
    name = FILES.get(kind)
    if not name:
        sys.exit(f"Unknown file '{kind}'. Use one of: lessons, victor, journal, idea, question.")
    for pat, what in NEVER:
        if re.search(pat, text, flags=re.I):
            sys.exit(f"Not written: this looks like {what}. The brain lives in a public repo.")
    path = BRAIN / name
    lines = path.read_text(encoding="utf-8").splitlines()
    if name == "ideas.md":
        entry = "- [ ] " + text
        at = next(i for i, l in enumerate(lines) if l.strip() == "## Open") + 1
    elif name == "victor.md":
        entry = f"- {today()}: {text}"
        at = next(i for i, l in enumerate(lines) if l.startswith("## Decisions")) + 1
    elif name == "questions.md":
        entry = "- " + text
        at = max(i for i, l in enumerate(lines) if l.startswith("- ")) + 1 if any(l.startswith("- ") for l in lines) else len(lines)
    else:
        entry = f"- {today()} · {text}"
        at = next((i for i, l in enumerate(lines) if l.startswith("- ")), len(lines))
    if any(entry.split("· ", 1)[-1].strip().lower() == l.split("· ", 1)[-1].strip().lower() for l in lines):
        sys.exit("Already there, not added twice.")
    lines.insert(at, entry)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Added to {name}: {entry}")


def check():
    problems = []
    for name, limit in LIMITS.items():
        path = BRAIN / name
        if not path.exists():
            problems.append(f"{name} is missing")
            continue
        text = path.read_text(encoding="utf-8")
        n = len(text.splitlines())
        if n > limit:
            problems.append(f"{name} has {n} lines (limit {limit}): merge, prune, or move settled rules into CLAUDE.md")
        for pat, what in NEVER:
            for m in re.finditer(pat, text, flags=re.I):
                if what.startswith("a phone") and "site.json" in text[max(0, m.start() - 80):m.end() + 80]:
                    continue
                problems.append(f"{name}:{text.count(chr(10), 0, m.start()) + 1} looks like {what}: remove it")
        if name in ("lessons.md", "journal.md"):
            undated = [l for l in text.splitlines() if l.startswith("- ") and not re.match(r"- \d{4}-\d\d-\d\d", l)]
            if undated:
                problems.append(f"{name}: {len(undated)} entries without a date (start each with YYYY-MM-DD)")
    for p in problems:
        print("PROBLEM  " + p)
    print("brain ok" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


def recent():
    j = [l for l in (BRAIN / "journal.md").read_text(encoding="utf-8").splitlines() if l.startswith("- ")]
    print("Last journal lines:")
    print("\n".join("  " + l for l in j[:10]))
    ideas = (BRAIN / "ideas.md").read_text(encoding="utf-8").split("## Shipped")[0]
    print("\nOpen ideas:")
    print("\n".join("  " + l for l in ideas.splitlines() if l.startswith("- [ ]")))


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["check"]:
        sys.exit(check())
    if a[:1] == ["recent"]:
        sys.exit(recent())
    if a[:1] == ["add"] and len(a) >= 3:
        sys.exit(add(a[1], " ".join(a[2:])))
    print(__doc__)
    sys.exit(2)
