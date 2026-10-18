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
Tests for course analytics (catsoop.analytics and the default handler's
analytics action)
"""

import unittest
from datetime import datetime, timedelta

from .. import time as csm_time
from .. import tutor
from .. import cslog
from .. import loader
from .. import analytics
from ..test import CATSOOPTest
from ..dispatch import content_file_location

COURSE = "test_course"
PAGE = [COURSE, "questions"]

# -----------------------------------------------------------------------------


class Test_Analytics(CATSOOPTest):
    def setUp(self):
        CATSOOPTest.setUp(self)
        # "student" is the only user in __TEST_COURSE__/__USERS__
        cslog.overwrite_log(
            "student",
            PAGE,
            "problemstate",
            {
                "scores": {"q000000": 1.0, "q000001": 0.5},
                "last_submit": {"q000000": "x", "q000001": "y"},
                "nsubmits_used": {"q000000": 1, "q000001": 3},
            },
        )

    def tearDown(self):
        cslog.delete_log("student", PAGE, "problemstate")

    def _handler_context(self, form, permissions):
        context = loader.generate_context(PAGE)
        context["cs_user_info"] = {"username": "prof", "permissions": permissions}
        cfile = content_file_location(context, PAGE)
        loader.load_content(context, PAGE[0], PAGE[1:], context, cfile)
        context["cs_session_data"] = {}
        context["cs_form"] = form
        handler = tutor.handler(context, "default", False)
        handler["pre_handle"](context)
        return context, handler

    def test_histogram_and_median(self):
        self.assertEqual(
            analytics.histogram([0, 0.05, 0.5, 0.99, 1.0]),
            [2, 0, 0, 0, 0, 1, 0, 0, 0, 2],
        )
        self.assertEqual(analytics._median([3, 1, 2]), 2)
        self.assertEqual(analytics._median([1, 2, 3, 4]), 2.5)
        self.assertIsNone(analytics._median([]))

    def test_list_pages(self):
        context = loader.generate_context([COURSE])
        pages = analytics.list_pages(context, COURSE)
        self.assertIn(PAGE, pages)
        self.assertIn(PAGE + ["linregress"], pages)

    def test_course_analytics(self):
        context = loader.generate_context([COURSE])
        data = analytics.course_analytics(context, COURSE, "prof")
        self.assertEqual(data["errors"], [])
        self.assertEqual(data["overview"]["n_students"], 1)

        page = {a["key"]: a for a in data["assignments"]}["questions"]
        self.assertEqual(
            page["counts"], {"completed": 0, "in_progress": 1, "not_started": 0}
        )
        earned = 1.0 * page["questions"]["q000000"]["csq_npoints"]
        earned += 0.5 * page["questions"]["q000001"]["csq_npoints"]
        self.assertAlmostEqual(page["avg"], earned / page["total_points"])

        qstats = {q["name"]: q for q in page["question_stats"]}
        self.assertEqual(qstats["q000001"]["attempted"], 1)
        self.assertEqual(qstats["q000001"]["avg_score"], 0.5)
        self.assertEqual(qstats["q000001"]["avg_submissions"], 3)
        self.assertEqual(qstats["q000002"]["attempted"], 0)
        self.assertIsNone(qstats["q000002"]["avg_score"])

        (student,) = data["students"]
        possible = sum(a["total_points"] for a in data["assignments"])
        self.assertAlmostEqual(student["overall"], earned / possible)
        self.assertTrue(student["at_risk"])
        self.assertEqual(data["hardest"][0]["name"], "q000001")

    def test_default_category_and_counting(self):
        # test course pages set no category and no due dates
        context = loader.generate_context([COURSE])
        data = analytics.course_analytics(context, COURSE, "prof")
        self.assertFalse(data["weighted"])
        self.assertEqual([c["name"] for c in data["categories"]], ["Other"])
        self.assertIsNone(data["categories"][0]["weight"])
        for a in data["assignments"]:
            self.assertEqual(a["category"], analytics.DEFAULT_CATEGORY)
            self.assertFalse(a["has_due"])
            self.assertTrue(a["counted"])

    def test_overall_score(self):
        weights = {"Homework": 1, "Exam": 3}
        self.assertAlmostEqual(
            analytics.overall_score({"Homework": 0.5, "Exam": 1.0}, weights, 0, 0),
            0.875,
        )
        # categories without counted assignments are left out and the
        # remaining weights are rescaled
        self.assertAlmostEqual(
            analytics.overall_score({"Homework": 0.5}, weights, 0, 0), 0.5
        )
        self.assertIsNone(analytics.overall_score({"Lab": 0.5}, weights, 0, 0))
        self.assertAlmostEqual(analytics.overall_score({}, None, 3, 4), 0.75)
        self.assertIsNone(analytics.overall_score({}, None, 0, 0))

    def test_weighted_categories(self):
        context = loader.generate_context([COURSE])
        context["cs_analytics_category_weights"] = {"Other": 1}
        data = analytics.course_analytics(context, COURSE, "prof")
        self.assertTrue(data["weighted"])
        self.assertEqual(data["categories"][0]["weight"], 1.0)
        # with weights, assignments count equally within a category
        (student,) = data["students"]
        fractions = [student["scores"][a["key"]] or 0.0 for a in data["assignments"]]
        self.assertAlmostEqual(student["categories"]["Other"], sum(fractions) / 3)
        self.assertAlmostEqual(student["overall"], sum(fractions) / 3)

    def test_late_submissions(self):
        questions = {
            "q000000": {"csq_npoints": 1.0},
            "q000001": {"csq_npoints": 1.0},
        }
        due = datetime(2026, 9, 15, 23, 59)
        cslog.overwrite_log(
            "student",
            PAGE,
            "problemstate",
            {
                "scores": {"q000000": 1.0, "q000001": 1.0},
                "last_submit_times": {
                    "q000000": csm_time.detailed_timestamp(due - timedelta(hours=1)),
                    "q000001": csm_time.detailed_timestamp(due + timedelta(hours=1)),
                },
            },
        )
        record = analytics.student_page_record("student", PAGE, questions, due)
        self.assertFalse(record["q000000"]["late"])
        self.assertTrue(record["q000001"]["late"])
        record = analytics.student_page_record("student", PAGE, questions)
        self.assertFalse(record["q000001"]["late"])

    def test_ungraded_work_left_out(self):
        # q000002 is submitted but has no score yet (e.g. awaiting a grade)
        cslog.overwrite_log(
            "student",
            PAGE,
            "problemstate",
            {
                "scores": {"q000000": 1.0},
                "last_submit": {"q000000": "x", "q000002": "z"},
            },
        )
        context = loader.generate_context([COURSE])
        data = analytics.course_analytics(context, COURSE, "prof")
        page = {a["key"]: a for a in data["assignments"]}["questions"]
        qs = page["questions"]
        expected = qs["q000000"]["csq_npoints"] / (
            page["total_points"] - qs["q000002"]["csq_npoints"]
        )
        self.assertAlmostEqual(page["avg"], expected)
        (student,) = data["students"]
        self.assertAlmostEqual(student["scores"]["questions"], expected)
        qstats = {q["name"]: q for q in page["question_stats"]}
        self.assertEqual(qstats["q000002"]["attempted"], 1)
        self.assertEqual(qstats["q000002"]["n_graded"], 0)

    def test_whdw_all_sections(self):
        for section, expected in (("nonexistent", []), ("all", ["student"])):
            context, handler = self._handler_context(
                {"action": "whdw", "section": section}, ["whdw"]
            )
            scores = handler["_get_scores"](context)
            self.assertEqual(sorted(scores["q000001"]), expected)

    def test_section_filter(self):
        context = loader.generate_context([COURSE])
        data = analytics.course_analytics(context, COURSE, "prof", "nonexistent")
        self.assertEqual(data["overview"]["n_students"], 0)
        self.assertEqual(data["sections"], ["default"])

    def test_requires_whdw_permission(self):
        context, handler = self._handler_context(
            {"action": "analytics"}, ["view", "submit"]
        )
        out = handler["handle_analytics"](context)
        self.assertEqual(out, "You are not allowed to view this page.")

    def test_dashboard_html(self):
        context, handler = self._handler_context(
            {"action": "analytics"}, ["view", "view_all", "whdw"]
        )
        out = handler["handle_analytics"](context)
        self.assertIn("cs-analytics", out)
        self.assertIn("COURSE/questions?action=whdw&amp;question=q000001", out)
        self.assertEqual(context["cs_content_header"], "Course Analytics")

    def test_dashboard_csv(self):
        context, handler = self._handler_context(
            {"action": "analytics", "format": "csv"}, ["whdw"]
        )
        status, headers, body = handler["handle_analytics"](context)
        self.assertEqual(status, ("200", "OK"))
        self.assertTrue(headers["Content-type"].startswith("text/csv"))
        lines = body.strip().splitlines()
        self.assertTrue(lines[0].startswith("username,name,section,"))
        self.assertTrue(lines[1].startswith("student,"))


if __name__ == "__main__":
    unittest.main()
