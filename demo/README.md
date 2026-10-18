# Local demo deployment

Two demo courses with users and simulated submissions, for testing this
checkout locally (in particular the instructor analytics dashboard,
`?action=analytics`).

The deployment uses its **own** config (`~/.config/catsoop-desktop/config.py`)
and data root (`~/.local/share/catsoop`), so any other CAT-SOOP configuration on
the machine is left alone.

## Setup (once)

```bash
python3 -m venv ~/.venvs/catsoop-desktop
~/.venvs/catsoop-desktop/bin/pip install -e .      # from the repo root
~/.venvs/catsoop-desktop/bin/python demo/setup_demo.py
demo/start.sh                                     # http://localhost:7667
```

`setup_demo.py` writes the config if missing, symlinks `demo/courses/*` into the
data root (so edits to course files take effect immediately), creates login
accounts, and writes simulated submissions.  It is safe to re-run; it resets the
simulated submissions each time.  `--clear` removes everything it added.

## Courses and accounts

All accounts use the password `demo1234`.

| Course | URL | Staff | Students |
|---|---|---|---|
| Intro to Programming | `/demo_python` | `prof_smith` (Instructor), `ta_lee` (TA) | 12, sections 1 and 2 |
| Calculus I | `/demo_math` | `prof_smith` (Instructor) | 8 (incl. `ta_lee`), sections A and B |

`ta_lee` is a TA in one course and a student in the other, showing that roles
are per course.  Student usernames: `aarav bella chen diego emma farah george
hana ivan julia kofi lina mia`.

## Assignment categories and weights

Each graded page sets `cs_assignment_category` in its `preload.py`.  In
`demo_python`, the `labs/` folder sets `cs_assignment_category = "Lab"` once
and both labs inherit it.  The course `preload.py` sets
`cs_analytics_category_weights`:

| Course | Categories and weights |
|---|---|
| `demo_python` | Homework 40%, Lab 25% (with staff checkoffs), Quiz 35% |
| `demo_math` | Problem Set 50%, Exam 50% |

On the dashboard each category average gives its assignments equal weight, and
the overall score is the weighted average of the categories.  Only *closed*
assignments (past their due date) count; Homework 3 is still open and Homework
4 is not released.  Remove `cs_analytics_category_weights` to fall back to
points earned out of points available.

The simulated data includes strong, average and struggling students, two who
stop partway through (`hana`, `julia`), one who never starts (`lina`), an
assignment still open (`hw3`), one not yet released (`hw4`), and a manually
graded question with some submissions still ungraded (`hw2`).

Log in as `prof_smith` or `ta_lee` and use the **Analytics** menu entry (shown
to staff only), or open `/demo_python?action=analytics`.
