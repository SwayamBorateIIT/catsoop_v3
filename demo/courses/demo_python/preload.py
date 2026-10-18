# Demo course for local testing of the instructor analytics dashboard.
# Set up with:  python demo/setup_demo.py   (see demo/README.md)

cs_base_color = "#1F5AA3"
cs_header = "DEMO.PY"
cs_long_name = cs_content_header = "Intro to Programming (Demo)"
cs_title = "Intro to Programming (Demo)"

cs_top_menu = [
    {"link": "COURSE", "text": "Homepage"},
    {
        "text": "Assignments",
        "link": [
            {"text": "Homework 1", "link": "COURSE/hw1"},
            {"text": "Homework 2", "link": "COURSE/hw2"},
            {"text": "Quiz 1", "link": "COURSE/quiz1"},
            {"text": "Homework 3", "link": "COURSE/hw3"},
            {"text": "Homework 4", "link": "COURSE/hw4"},
            "divider",
            {"text": "Lab 1", "link": "COURSE/labs/lab1"},
            {"text": "Lab 2", "link": "COURSE/labs/lab2"},
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
        "checkoff",
    ],
    "TA": ["view_all", "submit_all", "impersonate", "whdw", "grade", "checkoff"],
    "Student": ["view", "submit"],
    "Guest": ["view"],
}


# how the analytics dashboard combines categories into an overall score
# (each page's category comes from cs_assignment_category in its preload.py)
cs_analytics_category_weights = {"Homework": 0.4, "Lab": 0.25, "Quiz": 0.35}


# show an "Analytics" menu entry to staff only (runs after authentication)
def cs_post_load(context):
    perms = context.get("cs_user_info", {}).get("permissions", [])
    if "whdw" in perms and isinstance(context.get("cs_top_menu"), list):
        context["cs_top_menu"].append(
            {"text": "Analytics", "link": "COURSE?action=analytics"}
        )
