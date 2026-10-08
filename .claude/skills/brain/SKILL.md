---
name: brain
description: Order Aruba's memory between Claude Code sessions, kept as short files in .claude/brain/ (lessons, Victor's decisions, open questions, the idea backlog, a journal). Use it before your final reply in every session that changed or learned something, whenever Victor decides, corrects or prefers something, whenever a gotcha costs you time, and whenever anyone says remember, don't forget, note this, learn from this, what did we do last time, what's still open, or what should we do next. Without it the next session starts from zero.
---

# Brain

Every Claude Code session on this repo starts fresh, and cloud containers are wiped
afterwards. The repo is the only memory that survives. Victor shouldn't have to
explain the same thing twice, and a mistake that cost an hour today shouldn't cost
an hour again next week. That's what these files are for.

## What's where

| File | Holds | Loaded |
|---|---|---|
| `.claude/brain/victor.md` | how Victor works, his decisions with dates | every session (CLAUDE.md imports it) |
| `.claude/brain/lessons.md` | gotchas: what happens, what to do instead | every session |
| `.claude/brain/questions.md` | things only Victor can answer or give | every session |
| `.claude/brain/ideas.md` | the improvement backlog, with impact and effort | read when planning work |
| `.claude/brain/journal.md` | one line per session: what shipped, what's waiting | read when planning work |

CLAUDE.md stays the place for settled rules and the file map. The brain is for what's
still moving. When something in the brain becomes a rule everyone must follow, move it
into CLAUDE.md and delete it from the brain.

## At the start of a session

The three always-loaded files are already in your context. If the task is open-ended
("improve something", "what's next"), also run
`python3 .claude/skills/brain/scripts/brain.py recent` for the last journal lines and
the open ideas. Check `questions.md` for anything you could ask Victor in passing,
one question at a time.

## Before your final reply: write back

Ask yourself what the next session would want to know, then use the helper so the
date and placement are right:

```
python3 .claude/skills/brain/scripts/brain.py add journal "claude (cloud) · <what shipped> (<commit>) · waiting: <what>"
python3 .claude/skills/brain/scripts/brain.py add lessons "<what happens>. <what to do instead>"
python3 .claude/skills/brain/scripts/brain.py add victor "<the decision>, his words: '<short quote>'"
python3 .claude/skills/brain/scripts/brain.py add question "<plain question, choice spelled out>"
python3 .claude/skills/brain/scripts/brain.py add idea "<H/M/L> · <S/M/L> · <idea> · done when: <check>"
python3 .claude/skills/brain/scripts/brain.py check
```

Then edit by hand what the helper can't do: tick a shipped idea `[x]` with date and
commit and move it under Shipped, delete an answered question (after writing the answer
into victor.md), merge two lessons that say the same thing. Commit the brain together
with the work it describes, so memory and code never disagree.

## What's worth remembering

- **Decisions and corrections from Victor**, dated, with a few of his own words. A
  correction is the most valuable thing to keep: it's a mistake not to repeat.
- **Gotchas you verified**: something that failed, why, and the fix. Not guesses, not
  "might be". If you didn't confirm it, it isn't a lesson yet.
- **Ideas you noticed but didn't do.** You are expected to come up with improvements
  yourself. Write them down with a "done when" check, so a later session can just do it.
- **What's waiting and on whom.** The journal line's "waiting:" part is how the next
  session knows not to redo or forget something.

Not worth it: what the code already says, what git log already says, step-by-step
narration of the session, anything you'd only need today.

## What never goes in

This repo is public and served on the web. Never write: keys or tokens, costs, buyer
prices, margins, business plans, customers' names, phones or addresses, Victor's private
contact details. `brain.py add` refuses the obvious ones and `brain.py check` scans
for them, but you're the real filter.

## Keep it small

Each file is read at the start of every session, so every line costs attention. Limits
(`brain.py check` enforces them): lessons 60 lines, victor 50, questions 30, ideas 60,
journal 110. When near a limit, merge and prune: a short, true file beats a long one
nobody reads. Fold an old month of the journal into one summary line.
