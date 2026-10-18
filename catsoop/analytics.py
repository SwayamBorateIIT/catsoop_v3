# This file is part of CAT-SOOP
# Copyright (c) 2011-2025 by The CAT-SOOP Developers <catsoop-dev@mit.edu>
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
Course-wide analytics: aggregate student performance across all pages of a
course, for use by the instructor analytics dashboard.

All scores are floats between 0 and 1, matching the values stored in the
`problemstate` and `problemgrades` logs.

Pages can be grouped into categories (e.g. homework, labs, exams) by setting
`cs_assignment_category` in their `preload.py` (setting it in a directory's
`preload.py` applies it to every page below that directory).  If the course
sets `cs_analytics_category_weights` (a dictionary mapping category names to
weights), each student's overall score is the weighted average of their
per-category averages, where a category's average gives each assignment in it
equal weight.  Otherwise, the overall score is points earned out of points
available.

Only assignments that are released and past their due date (or that have no
due date) count toward overall scores; assignments that are still open are
reported but not counted.
"""

import os
import traceback
from datetime import MAXYEAR

from . import user
from . import time
from . import cslog
from . import tutor
from . import loader
from . import dispatch

_nodoc = {"traceback", "MAXYEAR"}

DEFAULT_STUDENT_ROLES = ("Student", "SLA")
"""
Roles counted as students when `cs_analytics_student_roles` is not set
(matches the roles used by the existing `stats` / `whdw` pages).
"""

DEFAULT_AT_RISK_THRESHOLD = 0.6
"""
Overall score below which a student is flagged as at-risk when
`cs_analytics_at_risk_threshold` is not set.
"""

DEFAULT_CATEGORY = "Other"
"""
Category of pages that do not set `cs_assignment_category`.
"""

HARDEST_MIN_GRADED = 3
"""
Minimum number of graded attempts for a question to be listed among the
hardest questions (or every student, in courses with fewer students).
"""

MAX_DEPTH = 8
"""
Maximum directory depth searched when looking for pages with questions.
"""


def list_pages(context, course):
    """
    List all pages in a course that have a content file.

    **Parameters:**

    * `context`: the context associated with this request
    * `course`: the name of the course

    **Returns:** a list of paths (each a list of strings starting with the
    course name), in sorted directory order
    """
    out = []

    def _walk(path):
        if len(path) > MAX_DEPTH:
            return
        try:
            subdirs = sorted(loader.get_subdirs(context, course, path))
        except (FileNotFoundError, NotADirectoryError):
            return
        for d in subdirs:
            short = ".".join(d.split(".")[1:]) if "." in d else d
            newpath = path + [short]
            if dispatch.content_file_location(context, [course] + newpath):
                out.append([course] + newpath)
            _walk(newpath)

    _walk([])
    return out


def page_question_info(context, path, username):
    """
    Get information about the questions on a page.

    Uses the `_question_info` cache when it is up to date with the page's
    content file; otherwise, the page is loaded (as `username`) to compute the
    information, which also refreshes the cache.

    **Parameters:**

    * `context`: the context associated with this request
    * `path`: the path to the page, as a list of strings starting with the
        course name
    * `username`: the user as whom the page should be loaded if necessary

    **Returns:** a dictionary mapping question names to dictionaries with
    (at least) the keys `csq_name`, `csq_display_name`, `csq_npoints`,
    `qtype`, and `csq_grading_mode`, in page order
    """
    cfile = dispatch.content_file_location(context, path)
    if cfile is None:
        return {}
    cache = cslog.most_recent("_question_info", path, "question_info", None)
    if cache is not None and cache.get("timestamp", 0) >= os.stat(cfile).st_mtime:
        return cache["questions"]
    stats = tutor.compute_page_stats(
        context, username, path, ["context", "question_info"]
    )
    return stats["question_info"]


def page_metadata(context, path):
    """
    Get the title, category, and dates of a page by running its `preload.py`
    files.

    **Parameters:**

    * `context`: the context associated with this request
    * `path`: the path to the page, as a list of strings starting with the
        course name

    **Returns:** a dictionary with keys `title` (a string), `category` (the
    page's `cs_assignment_category`, or `DEFAULT_CATEGORY`), `release` and
    `due` (`datetime` objects, or `None` if they could not be determined),
    `released` (a Boolean; `True` if the release date is unknown), and
    `has_due` (a Boolean; `False` if the page has no due date)
    """
    ctx = loader.generate_context(path)
    title = ctx.get("cs_long_name", None) or ctx.get("cs_short_name", None)
    category = str(ctx.get("cs_assignment_category", None) or DEFAULT_CATEGORY)
    try:
        release = tutor.get_release_date(ctx)
    except Exception:
        release = None
    try:
        due = tutor.get_due_date(ctx)
    except Exception:
        due = None
    return {
        "title": title or path[-1],
        "category": category,
        "release": release,
        "due": due,
        "released": release is None or release <= time.now(),
        # cs_due_date = "NEVER" resolves to the last day of year MAXYEAR
        "has_due": due is not None and due.year < MAXYEAR,
    }


def list_assignments(context, course, username):
    """
    List all pages in a course that contain at least one question worth
    points.

    Pages that fail to load are skipped and reported in the result rather than
    raising an exception.

    **Parameters:**

    * `context`: the context associated with this request
    * `course`: the name of the course
    * `username`: the user as whom pages should be loaded if necessary

    **Returns:** a tuple `(assignments, errors)`.  `assignments` is a list of
    dictionaries with keys `path`, `key` (the path joined with `/`, not
    including the course), `title`, `category`, `release`, `due`, `released`,
    `has_due`, `counted` (whether the assignment counts toward overall scores:
    released, and past due or without a due date), `questions` (an ordered
    dictionary as returned by `page_question_info`, restricted to questions
    worth points), and `total_points`.  `errors` is a list of `(key, message)`
    tuples.
    """
    assignments = []
    errors = []
    now = time.now()
    for path in list_pages(context, course):
        key = "/".join(path[1:])
        try:
            qinfo = page_question_info(context, path, username)
            questions = {}
            for name, info in qinfo.items():
                try:
                    npoints = float(info.get("csq_npoints", 0) or 0)
                except (TypeError, ValueError):
                    npoints = 0.0
                if npoints > 0:
                    questions[name] = dict(info, csq_npoints=npoints)
            if not questions:
                continue
            meta = page_metadata(context, path)
        except Exception:
            errors.append((key, traceback.format_exc()))
            continue
        still_open = meta["has_due"] and meta["due"] > now
        assignments.append(
            dict(
                meta,
                path=path,
                key=key,
                counted=meta["released"] and not still_open,
                questions=questions,
                total_points=sum(q["csq_npoints"] for q in questions.values()),
            )
        )
    return assignments, errors


def list_students(context, course, section=None):
    """
    List the students in a course.

    The roles counted as students are given by `cs_analytics_student_roles` in
    the context (default `DEFAULT_STUDENT_ROLES`).

    **Parameters:**

    * `context`: the context associated with this request
    * `course`: the name of the course

    **Optional Parameters:**

    * `section` (default `None`): if given, only include students in this
        section (compared as strings; students without a section are in
        section `'default'`)

    **Returns:** a dictionary mapping usernames to dictionaries with keys
    `username`, `name`, and `section`, sorted by username
    """
    roles = set(context.get("cs_analytics_student_roles", DEFAULT_STUDENT_ROLES))
    try:
        infos = user.all_users_info(
            context, course, lambda u: u.get("role", None) in roles
        )
    except FileNotFoundError:
        return {}
    out = {}
    for uname in sorted(infos):
        uinfo = infos[uname]
        sec = str(uinfo.get("section", "default"))
        if section is not None and sec != str(section):
            continue
        name = uinfo.get("name", None)
        if not name:
            extra = cslog.most_recent("_extra_info", [], uname, None) or {}
            name = extra.get("name", None)
        out[uname] = {"username": uname, "name": name or uname, "section": sec}
    return out


def _parse_timestamp(stamp):
    try:
        return time.from_detailed_timestamp(stamp)
    except Exception:
        return None


def student_page_record(username, path, questions, due=None):
    """
    Get a student's results on each question on a page.

    For questions with `csq_grading_mode` set to `'manual'`, the most recent
    manual grade is used; otherwise the score from the `problemstate` log is
    used.

    **Parameters:**

    * `username`: the student's username
    * `path`: the path to the page, as a list of strings starting with the
        course name
    * `questions`: an ordered dictionary of question information, as in the
        `questions` key of an entry from `list_assignments`

    **Optional Parameters:**

    * `due` (default `None`): the page's due date, as a `datetime`; if given,
        submissions made after it are marked as late

    **Returns:** a dictionary mapping question names to dictionaries with keys
    `submitted` (Boolean), `score` (a float, or `None` if not submitted or not
    yet graded), `nsubmits` (an integer), and `late` (Boolean)
    """
    state = cslog.most_recent(username, path, "problemstate", {})
    scores = state.get("scores", {}) or {}
    submitted = set(state.get("last_submit", {}) or {}) | set(scores)
    nsubmits = state.get("nsubmits_used", {}) or {}
    times = state.get("last_submit_times", {}) or {}

    manual = {}
    if any(q.get("csq_grading_mode") == "manual" for q in questions.values()):
        for entry in cslog.read_log(username, path, "problemgrades"):
            manual[entry["qname"]] = entry["score"]

    out = {}
    for name, info in questions.items():
        if info.get("csq_grading_mode") == "manual":
            score = manual.get(name, None)
        else:
            score = scores.get(name, None)
        when = _parse_timestamp(times[name]) if name in times else None
        out[name] = {
            "submitted": name in submitted or name in manual,
            "score": None if score is None else float(score),
            "nsubmits": int(nsubmits.get(name, 0) or 0),
            "late": due is not None and when is not None and when > due,
        }
    return out


def _mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else None


def _median(xs):
    xs = sorted(xs)
    n = len(xs)
    if n == 0:
        return None
    mid = n // 2
    return xs[mid] if n % 2 else (xs[mid - 1] + xs[mid]) / 2


def histogram(values, nbins=10):
    """
    Count how many values fall into each of `nbins` equal-width bins covering
    [0, 1].  A value of exactly 1 is counted in the last bin.

    **Parameters:**

    * `values`: an iterable of floats between 0 and 1

    **Optional Parameters:**

    * `nbins` (default `10`): the number of bins

    **Returns:** a list of `nbins` integers
    """
    bins = [0] * nbins
    for v in values:
        ix = min(max(int(v * nbins), 0), nbins - 1)
        bins[ix] += 1
    return bins


def overall_score(category_scores, weights, earned, possible):
    """
    Combine a student's scores into an overall score.

    **Parameters:**

    * `category_scores`: a dictionary mapping category names to the student's
        average in that category (only categories with counted assignments)
    * `weights`: a dictionary mapping category names to weights, or `None`
    * `earned`: points earned across counted assignments
    * `possible`: points available across counted assignments

    **Returns:** with weights, the weighted average of `category_scores` over
    categories with a positive weight (renormalized over those categories);
    without weights, `earned / possible`.  `None` if there is nothing to
    average.
    """
    if weights:
        total = sum(weights.get(c, 0) for c in category_scores)
        if total <= 0:
            return None
        return sum(s * weights.get(c, 0) for c, s in category_scores.items()) / total
    return earned / possible if possible else None


def course_analytics(context, course, username, section=None):
    """
    Compute analytics for an entire course.

    **Parameters:**

    * `context`: the context associated with this request
    * `course`: the name of the course
    * `username`: the user as whom pages should be loaded if necessary
        (typically the instructor viewing the dashboard)

    **Optional Parameters:**

    * `section` (default `None`): if given, only include students in this
        section

    **Returns:** a dictionary with the following keys:

    * `'overview'`: a dictionary with keys `n_students`, `n_assignments`,
        `n_counted`, `course_avg` (mean overall score, or `None`),
        `completion_rate` (fraction of student/counted-assignment pairs
        completed, or `None`), and `late_rate` (fraction of started
        student/assignment pairs, over counted assignments with a due date,
        with at least one late submission, or `None`)
    * `'assignments'`: a list of dictionaries, one per assignment (see
        `list_assignments`), each additionally containing `counts` (keys
        `completed`, `in_progress`, `not_started`), `late` (number of students
        with a late submission), `avg` and `median` (over students who
        started), `histogram`, and `question_stats` (a list of per-question
        dictionaries)
    * `'categories'`: a list of dictionaries with keys `name`, `weight` (the
        normalized weight, or `None` if no weights are configured),
        `n_assignments`, `n_counted`, and `avg` (mean of students' category
        averages), in order of first appearance
    * `'weighted'`: whether `cs_analytics_category_weights` is in effect
    * `'students'`: a list of dictionaries with keys `username`, `name`,
        `section`, `scores` (mapping assignment keys to a float, or `None` if
        not started or nothing submitted has been graded yet; questions
        awaiting a grade are left out of the score until graded), `categories` (mapping category names to averages over
        counted assignments), `overall`, `n_not_started` and `n_late` (over
        counted assignments), and `at_risk`
    * `'hardest'`: up to 10 per-question dictionaries (from counted
        assignments, with at least `HARDEST_MIN_GRADED` graded attempts) with
        the lowest average score
    * `'sections'`: a sorted list of all section names in the course
    * `'errors'`: a list of `(page, message)` tuples for pages that failed
        to load
    * `'threshold'`: the at-risk threshold
    """
    threshold = float(
        context.get("cs_analytics_at_risk_threshold", DEFAULT_AT_RISK_THRESHOLD)
    )
    weights = context.get("cs_analytics_category_weights", None) or None
    if weights is not None:
        weights = {str(k): float(v) for k, v in weights.items()}
    assignments, errors = list_assignments(context, course, username)
    all_students = list_students(context, course)
    sections = sorted({s["section"] for s in all_students.values()})
    if section is None:
        students = all_students
    else:
        students = {
            k: v for k, v in all_students.items() if v["section"] == str(section)
        }

    category_names = []
    for a in assignments:
        if a["category"] not in category_names:
            category_names.append(a["category"])
    if weights is not None:
        # configured categories first, in configuration order
        category_names = [c for c in weights if c in category_names] + [
            c for c in category_names if c not in weights
        ]

    student_rows = {
        u: dict(
            info,
            scores={},
            earned=0.0,
            possible=0.0,
            n_not_started=0,
            n_late=0,
            cat_fractions={},
        )
        for u, info in students.items()
    }
    completed_pairs = counted_pairs = started_pairs = late_pairs = 0

    for a in assignments:
        questions = a["questions"]
        due = a["due"] if a["has_due"] else None
        counts = {"completed": 0, "in_progress": 0, "not_started": 0}
        n_late = 0
        started_scores = []
        per_q = {
            name: {"scores": [], "attempted": 0, "nsubmits": []} for name in questions
        }

        for uname in students:
            row = student_rows[uname]
            record = student_page_record(uname, a["path"], questions, due)
            n_submitted = sum(r["submitted"] for r in record.values())
            is_late = any(r["late"] for r in record.values())
            earned = sum(
                (r["score"] or 0.0) * questions[name]["csq_npoints"]
                for name, r in record.items()
            )
            # submitted but not yet graded (e.g. awaiting a manual grade):
            # left out until graded, rather than counted as zero
            pending = sum(
                questions[name]["csq_npoints"]
                for name, r in record.items()
                if r["submitted"] and r["score"] is None
            )
            possible = a["total_points"] - pending
            fraction = earned / possible if possible > 0 else None

            if n_submitted == 0:
                counts["not_started"] += 1
                row["scores"][a["key"]] = None
            else:
                counts[
                    "completed" if n_submitted == len(questions) else "in_progress"
                ] += 1
                if fraction is not None:
                    started_scores.append(fraction)
                row["scores"][a["key"]] = fraction
                n_late += is_late
                if a["counted"] and a["has_due"]:
                    started_pairs += 1
                    late_pairs += is_late

            if a["counted"]:
                counted_pairs += 1
                completed_pairs += n_submitted == len(questions)
                row["earned"] += earned
                row["possible"] += possible
                row["n_not_started"] += n_submitted == 0
                row["n_late"] += is_late
                if n_submitted == 0 or fraction is not None:
                    row["cat_fractions"].setdefault(a["category"], []).append(
                        fraction or 0.0
                    )

            for name, r in record.items():
                if r["submitted"]:
                    per_q[name]["attempted"] += 1
                    per_q[name]["nsubmits"].append(r["nsubmits"])
                    if r["score"] is not None:
                        per_q[name]["scores"].append(r["score"])

        n = len(students)
        a["counts"] = counts
        a["late"] = n_late
        a["avg"] = _mean(started_scores)
        a["median"] = _median(started_scores)
        a["histogram"] = histogram(started_scores)
        a["question_stats"] = [
            {
                "assignment": a["key"],
                "assignment_title": a["title"],
                "name": name,
                "display_name": info.get("csq_display_name") or name,
                "npoints": info["csq_npoints"],
                "attempted": per_q[name]["attempted"],
                "attempted_pct": per_q[name]["attempted"] / n if n else None,
                "avg_score": _mean(per_q[name]["scores"]),
                "n_graded": len(per_q[name]["scores"]),
                "perfect_pct": (
                    sum(s >= 1 for s in per_q[name]["scores"])
                    / len(per_q[name]["scores"])
                    if per_q[name]["scores"]
                    else None
                ),
                "avg_submissions": _mean(per_q[name]["nsubmits"]),
            }
            for name, info in questions.items()
        ]

    student_list = []
    for row in student_rows.values():
        possible = row.pop("possible")
        earned = row.pop("earned")
        cat_fractions = row.pop("cat_fractions")
        row["categories"] = {c: _mean(fs) for c, fs in cat_fractions.items()}
        row["overall"] = overall_score(row["categories"], weights, earned, possible)
        row["at_risk"] = row["overall"] is not None and row["overall"] < threshold
        student_list.append(row)

    weight_total = sum((weights or {}).get(c, 0) for c in category_names)
    categories = [
        {
            "name": c,
            "weight": (
                (weights.get(c, 0) / weight_total if weight_total else 0.0)
                if weights is not None
                else None
            ),
            "n_assignments": sum(a["category"] == c for a in assignments),
            "n_counted": sum(a["category"] == c and a["counted"] for a in assignments),
            "avg": _mean(
                s["categories"][c] for s in student_list if c in s["categories"]
            ),
        }
        for c in category_names
    ]

    # ignore questions with too few graded attempts to say anything
    min_graded = min(HARDEST_MIN_GRADED, len(students)) or 1
    hardest = sorted(
        (
            q
            for a in assignments
            if a["counted"]
            for q in a["question_stats"]
            if q["avg_score"] is not None and q["n_graded"] >= min_graded
        ),
        key=lambda q: q["avg_score"],
    )[:10]

    return {
        "overview": {
            "n_students": len(students),
            "n_assignments": len(assignments),
            "n_counted": sum(a["counted"] for a in assignments),
            "course_avg": _mean(
                s["overall"] for s in student_list if s["overall"] is not None
            ),
            "completion_rate": (
                completed_pairs / counted_pairs if counted_pairs else None
            ),
            "late_rate": late_pairs / started_pairs if started_pairs else None,
        },
        "assignments": assignments,
        "categories": categories,
        "weighted": weights is not None,
        "students": student_list,
        "hardest": hardest,
        "sections": sections,
        "errors": errors,
        "threshold": threshold,
    }
