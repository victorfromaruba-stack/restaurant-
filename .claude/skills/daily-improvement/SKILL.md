---
name: daily-improvement
description: The once-a-day improvement run for Order Aruba (site and chef app). Check the site is healthy, pick one safe improvement from .claude/brain/ideas.md or find one with the human-touch audit, build it, prove it, ship it to main, write it into the brain, and tell Victor in three plain lines. Use it when the daily routine fires, and whenever Victor asks to "improve something", "do today's improvement", "keep making it better", "what can you improve", or "make it better" without naming a specific change.
---

# Daily improvement

Victor asked for a site that gets better every day and a Claude that comes up with the
improvements itself. One real improvement a day adds up to a different site in a month.
Ten half-finished ones add up to a broken one. So: **one thing, finished, proven, live.**

This run often happens with nobody watching. Nobody can answer a question halfway, and a
mistake goes live to real customers that night. Be more careful than in a chat with
Victor, not less.

## The run

1. **Catch up.** Pull `main`. Read `.claude/brain/` (victor, lessons and questions are
   already loaded through CLAUDE.md), then `python3 .claude/skills/brain/scripts/brain.py recent`.
   Look at `git log --oneline -15`: if a person changed something since the last journal
   line, read it before touching anything near it.
2. **Health first.** In a fresh cloud container first run `python3 -m pip install -q
   playwright==1.56.0 pillow` (the plain `pip` can belong to another Python). Then
   `python3 qa/check_site.py`; it serves the repo itself, no server to start. If anything
   fails, fixing that *is* today's improvement. Also open the live home page and one
   restaurant page and make sure they load. (Since 9 Oct 2026 Order Aruba is a delivery
   app like Uber Eats and each restaurant is its own business: see the rule in CLAUDE.md.
   Never build anything that hints at a shared kitchen.)
3. **Pick one thing.** Take the open idea in `ideas.md` with the best impact for its
   effort that you're allowed to do alone (rules below). No good idea left? Run the
   human-touch audit (`shoot.py` + `check.py`, then look), add what you find to
   `ideas.md`, and take the best one. Coming up with ideas is part of the job.
4. **Build it** the way the skill for that area says. For anything customers see, follow
   the human-touch skill. Keep the change small: one idea, roughly under 300 changed
   lines, something one `git revert` would cleanly undo.
5. **Prove it.**
   - `qa/check_site.py`: 0 problems. Run it on its own and check the exit code.
   - `.claude/skills/human-touch/scripts/check.py`: no new FAIL.
   - Screenshots before and after (`shoot.py --out /tmp/before` before you start,
     `--out /tmp/after` at the end). Look at both. Better, or just different? Only
     better ships.
   - Re-read your own diff as a reviewer who wants to reject it.
6. **Ship it.** Commit to `main` with a message that says what a customer would notice.
   `git pull --rebase origin main` (someone may have pushed while you worked), run QA
   again if anything came in, then `git push -u origin main`. Wait for GitHub Pages
   (about a minute) and check the change is on https://victorfromaruba-stack.github.io/restaurant-/
   or the restaurant page it touched.
   The scheduled run happens in the "Order Aruba daily worker" session, which was started
   with this repo attached, so the push works. If a push is ever refused (403, "not in this
   session's authorized repository set"), this session has no repo access: try
   `mcp__claude-code-remote__add_repo` (owner victorfromaruba-stack, repo restaurant-,
   access push) if you have it, and otherwise stop and say so plainly in the three lines.
7. **Remember it.** Tick the idea `[x]` with date and commit, move it under Shipped,
   add the journal line, add any lesson you learned, and add new ideas you spotted.
   Run `brain.py check`. Commit and push the brain update.
8. **Tell Victor.** Your final message is what reaches his phone. Three short lines, no
   code words:
   ```
   Today: <what changed, as a customer would see it>.
   Why: <the one-line reason>.
   You could: <one thing only he can do, from questions.md>, or nothing needed.
   ```
   Then the live link. In the scheduled run, also send the same text with the
   PushNotification tool (status proactive): the worker session's reply alone doesn't
   reach his phone.

If nothing safe is worth doing (everything left needs Victor), don't make busywork.
Say so in the three lines, ask the most useful question from `questions.md`, and stop.

## What you may do alone, and what you may not

**Yes:** layout, spacing, type, which picture goes where and how it's cropped, section
names and UI words (in all four languages), dish description wording that keeps the same
ingredients, speed, accessibility, offline, bugs, checks and tests, the chef app's
screens, the brain and the skills themselves.

**No, not even if an idea in the list says so:** prices, adding or removing dishes,
hours, delivery areas or fee, payment methods, the WhatsApp number, restaurant status,
restaurant names or logos, new food pictures, anything claimed as fact about the
business, removing a feature, the private kitchen files, Book Keeper, new third-party
scripts or trackers, anything that costs money (Gemini, paid APIs). If the best idea
needs one of these, put the question in `questions.md` and pick the next idea.

**Stop and don't push** if QA isn't 0 problems after your change and you can't fix it
within the run, or if you're unsure the change is better. Leave the work on a branch
named `daily/<date>`, push that branch, and say in the three lines that it's waiting.

## Improving the skills too

If a run shows a skill gave bad advice or missed something, fix the skill in the same
run (it's part of the repo), and note it in the journal. That's how the next run gets
smarter, not just the site.
