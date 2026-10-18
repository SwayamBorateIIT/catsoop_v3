import html

cs_auth_required = True
cs_view_without_auth = False
cs_skip_auth_rendering = True
cs_long_name = cs_content_header = "User Settings"
_course = cs_form.get("course", None)
_ctx = csm_loader.generate_context([_course] if _course is not None else [])

cs_breadcrumbs_skip = False

cs_title = "User Settings | %s" % cs_title


def cs_post_load(context):
    if str(context.get("cs_username", None)) == "None":
        context["cs_content"] = "You must be logged in to view this page."
        context["cs_problem_spec"] = [context["cs_content"]]
        context["cs_top_menu"] = []
