# Demo course for local testing of the instructor analytics dashboard.
# Set up with:  python demo/setup_demo.py   (see demo/README.md)

cs_base_color = "#2E7D32"
cs_header = "DEMO.CALC"
cs_long_name = cs_content_header = "Calculus I (Demo)"
cs_title = "Calculus I (Demo)"

cs_top_menu = [
    {"link": "COURSE", "text": "Homepage"},
    {
        "text": "Assignments",
        "link": [
            {"text": "Problem Set 1", "link": "COURSE/ps1"},
            {"text": "Problem Set 2", "link": "COURSE/ps2"},
            {"text": "Midterm", "link": "COURSE/midterm"},
        ],
    },
]

# roles are assigned in __USERS__/<username>.py
cs_default_role = "Guest"
cs_permissions = {
    "Instructor": [
        "view_all",
        "submit_all",
        "impersonate",
        "admin",
        "whdw",
        "email",
        "grade",
    ],
    "TA": ["view_all", "submit_all", "impersonate", "whdw", "grade"],
    "Student": ["view", "submit"],
    "Guest": ["view"],
}


# how the analytics dashboard combines categories into an overall score
# (each page's category comes from cs_assignment_category in its preload.py)
cs_analytics_category_weights = {"Problem Set": 0.5, "Exam": 0.5}


# show an "Analytics" menu entry to staff only (runs after authentication)
def cs_post_load(context):
    perms = context.get("cs_user_info", {}).get("permissions", [])
    if "whdw" in perms and isinstance(context.get("cs_top_menu"), list):
        context["cs_top_menu"].append(
            {"text": "Analytics", "link": "COURSE?action=analytics"}
        )
