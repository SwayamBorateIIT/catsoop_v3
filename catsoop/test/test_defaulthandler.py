import pytest

from .. import loader
from .. import tutor
from .. import cslog
from ..dispatch import content_file_location
from catsoop.__HANDLERS__.default import default

import json
from bs4 import BeautifulSoup
import shutil

TEST_PAGE_PATH = ["test_course", "questions"]


def generate_test_context(test_form):
    """
    Generates a test context based on test_form.

    **Parameters:**

    * `test_form`: a dictionary containing, at the minimum, a proposed action and other data regarding the proposed
                   action.

        Examples:

            test_form = {"action": "view"}  # to view a page
            test_form = {
                            "names": '["q000008"]',
                            "data": '{"q000008": "5"}',
                            "action": "submit",
                        }  # to submit a specific value to a specific question

    **Returns:** a processed context that is ready for handling
    """
    context = loader.generate_context(TEST_PAGE_PATH)
    context["cs_user_info"] = {
        "username": "test_user",
        "permissions": ["view", "submit"],
    }
    cfile = content_file_location(context, TEST_PAGE_PATH)
    loader.load_content(context, TEST_PAGE_PATH[0], TEST_PAGE_PATH[1:], context, cfile)

    context["cs_session_data"] = {}
    context["cs_form"] = test_form

    default.pre_handle(context)

    return context


def mock_action(question_name, action, action_value=None):
    """
    Mocks an action to the specified question

    **Parameters:**

    * `question_name`: the question for which the `action` will be mocked
    * `action`: the desired action to mock
    * `action_value`: if required, the value to check, submit, save, etc., based on `action`

    **Returns:** the most recent problem state log (which should reflect the mock action) and the handler function
    """
    submit_form = {
        "names": json.dumps([question_name]),
        "action": action,
        "data": json.dumps({question_name: action_value}),
    }

    submit_context = generate_test_context(submit_form)

    handler = tutor.handler(submit_context, "default", False)
    handler[f"handle_{action}"](submit_context)

    return (
        cslog.most_recent(
            submit_context["cs_user_info"]["username"], TEST_PAGE_PATH, "problemstate"
        ),
        handler,
    )


def check_render(
    question_name,
    handler,
    last_log,
    last_action_value=None,
    score_display_value=None,
    has_previous_submission=True,
    render_value_fragment=None,
):
    """
    Checks whether a particular question is properly rendered based on the most recent problem state.

    **Parameters:**

    * `question_name`: the question for which the action will be mocked
    * `handler`: the handler function that is configured based on the context
    * `last_log`: the most recent problem state
    * `last_action_value`: if required, the value that was most recently processed based on `last_action` in `last_log`
    * `score_display_value`: the score string that should be displayed for `question_name` (if any)
    * `has_previous_submission`: whether `question_name` has a previous submission (meaning that the user can choose to
                                 revert to that submission)
    * `render_value_fragment`: a fragment of the expected render output to check if it is correctly rendered (the
                               default value is None if there should not be any rendering output)

    **Returns:** whether the rendering is correct
    """
    last_action_value = last_action_value or ""

    view_ctx = generate_test_context({"action": "view"})
    all_questions = [
        elem for elem in view_ctx["cs_problem_spec"] if isinstance(elem, tuple)
    ]
    rendered = handler["render_question"](
        all_questions[int(question_name[1:])], view_ctx, last_log
    )

    soup = BeautifulSoup(rendered, "html.parser")

    last_action = last_log.get("last_action", {}).get(question_name, "")

    warning_tag = soup.find("div", {"id": f"{question_name}_check_message"})
    warning_displays = (
        warning_tag and warning_tag.text == "This response has not yet been submitted."
    )
    text_box_displays = (
        soup.find("input", {"id": question_name}).attrs["value"] == last_action_value
        if last_action != "revert"
        else last_log.get("last_submit", {}).get(question_name, "")
    )
    render_output_displays = (
        not render_value_fragment
        or render_value_fragment
        in soup.find("div", {"id": f"expr{question_name}"}).text
    )
    score_displays = (
        soup.find("span", {"id": f"{question_name}_score_display"}).text
        == score_display_value
    )
    revert_button_displays = not has_previous_submission or soup.find(
        "button", {"id": f"{question_name}_revert"}
    )

    correct_text_box_and_render = text_box_displays and render_output_displays

    if (
        last_action == "submit"
    ):  # no warning, no change to the text box, render the latest submission, show the
        # submission's score, and hide the revert to previous submission button
        return (
            not warning_displays
            and correct_text_box_and_render
            and score_displays
            and not revert_button_displays
        )
    elif (
        last_action == "revert"
    ):  # no warning, revert the text box value to the latest submission, render the
        # latest submission, show the latest submission's score, and hide the revert to previous submission button
        return (
            not warning_displays
            and correct_text_box_and_render
            and score_displays
            and not revert_button_displays
        )
    elif (
        last_action == "check"
    ):  # show the warning, no change to the text box, render the latest check, hide the
        # latest submission's score (if there is one), and show the revert to previous submission button
        return (
            warning_displays
            and correct_text_box_and_render
            and not score_displays
            and revert_button_displays
        )
    elif (
        last_action == "save"
    ):  # show the warning, no change to the text box, no rendered output, hide the
        # latest submission's score (if there is one), and hide the revert to previous submission button
        return (
            warning_displays
            and correct_text_box_and_render
            and not score_displays
            and not revert_button_displays
        )


@pytest.fixture(autouse=True)
def setup():
    """Clears the logs before each test case."""
    test_log_path = "/tmp/catsoop_test/_logs/_courses/test_course/test_user/questions"
    shutil.rmtree(test_log_path, ignore_errors=True)


def test_workflow_1():
    """Check a question without any prior submissions."""
    test_question_name = "q000008"

    last_check_1, check_handler_1 = mock_action(
        question_name=test_question_name,
        action="check",
        action_value="10",
    )

    expected_last_check_1 = {
        "last_check": {test_question_name: {"data": "10", "type": "raw"}},
        "score_displays": {test_question_name: ""},
        "last_action": {test_question_name: "check"},
    }

    assert expected_last_check_1.items() <= last_check_1.items()
    assert check_render(
        question_name=test_question_name,
        handler=check_handler_1,
        last_log=last_check_1,
        last_action_value="10",
        has_previous_submission=False,
        render_value_fragment="10",
    )


def test_workflow_2():
    """Submit to a question and then check a new value."""
    test_question_name = "q000008"

    last_submit_1, submit_handler_1 = mock_action(
        question_name=test_question_name,
        action="submit",
        action_value="sqrt(cos(omega)+j*sin(omega))",
    )

    expected_last_submit_1 = {
        "last_submit": {
            test_question_name: {"data": "sqrt(cos(omega)+j*sin(omega))", "type": "raw"}
        },
        "nsubmits_used": {test_question_name: 1},
        "score_displays": {
            test_question_name: "<span "
            'style="color:rgb(0,200,0);font-weight:bolder;">100.00%</span>'
        },
        "scores": {test_question_name: True},  # True indicates 100.00% grade
        "last_action": {test_question_name: "submit"},
    }

    assert expected_last_submit_1.items() <= last_submit_1.items()  # is a subset of
    assert check_render(
        question_name=test_question_name,
        handler=submit_handler_1,
        last_log=last_submit_1,
        last_action_value="sqrt(cos(omega)+j*sin(omega))",
        score_display_value="100.00%",
        render_value_fragment="cos",
    )

    last_check_1, check_handler_1 = mock_action(
        question_name=test_question_name,
        action="check",
        action_value="5",
    )

    expected_last_check_1 = {
        "last_check": {test_question_name: {"data": "5", "type": "raw"}},
        "last_submit": {
            test_question_name: {"data": "sqrt(cos(omega)+j*sin(omega))", "type": "raw"}
        },
        "nsubmits_used": {test_question_name: 1},
        "score_displays": {test_question_name: ""},
        "scores": {test_question_name: True},
        "last_action": {test_question_name: "check"},
    }

    assert expected_last_check_1.items() <= last_check_1.items()
    assert check_render(
        question_name=test_question_name,
        handler=check_handler_1,
        last_log=last_check_1,
        last_action_value="5",
        render_value_fragment="5",
    )

    last_submit_2, submit_handler_2 = mock_action(
        question_name=test_question_name,
        action="submit",
        action_value="10",
    )

    expected_last_submit_2 = {
        "last_check": {test_question_name: {"data": "5", "type": "raw"}},
        "last_submit": {test_question_name: {"data": "10", "type": "raw"}},
        "nsubmits_used": {test_question_name: 2},
        "score_displays": {
            test_question_name: "<span "
            'style="color:rgb(200,0,0);font-weight:bolder;">0.00%</span>'
        },
        "scores": {test_question_name: False},  # False indicates 0.00% grade
        "last_action": {test_question_name: "submit"},
    }

    assert expected_last_submit_2.items() <= last_submit_2.items()
    assert check_render(
        question_name=test_question_name,
        handler=submit_handler_2,
        last_log=last_submit_2,
        last_action_value="10",
        score_display_value="0.00%",
        render_value_fragment="10",
    )


def test_workflow_3():
    """Check one question, submit another question, and then submit the original question."""
    test_question_name_1 = "q000008"
    test_question_name_2 = "q000000"

    last_check_1, check_handler_1 = mock_action(
        question_name=test_question_name_1,
        action="check",
        action_value="sqrt(cos(omega)+j*sin(omega))",
    )

    expected_last_check_1 = {
        "last_check": {
            test_question_name_1: {
                "data": "sqrt(cos(omega)+j*sin(omega))",
                "type": "raw",
            }
        },
        "score_displays": {test_question_name_1: ""},
        "last_action": {test_question_name_1: "check"},
    }

    assert expected_last_check_1.items() <= last_check_1.items()
    assert check_render(
        question_name=test_question_name_1,
        handler=check_handler_1,
        last_log=last_check_1,
        last_action_value="sqrt(cos(omega)+j*sin(omega))",
        has_previous_submission=False,
        render_value_fragment="cos",
    )

    last_submit_1, submit_handler_1 = mock_action(
        question_name=test_question_name_2,
        action="submit",
        action_value="cat",
    )

    expected_last_submit_1 = {
        "last_submit": {test_question_name_2: {"data": "cat", "type": "raw"}},
        "last_check": {
            test_question_name_1: {
                "data": "sqrt(cos(omega)+j*sin(omega))",
                "type": "raw",
            }
        },
        "nsubmits_used": {test_question_name_2: 1},
        "score_displays": {
            test_question_name_1: "",
            test_question_name_2: "<span "
            'style="color:rgb(0,200,0);font-weight:bolder;">100.00%</span>',
        },
        "scores": {test_question_name_2: True},
        "last_action": {test_question_name_1: "check", test_question_name_2: "submit"},
    }

    assert expected_last_submit_1.items() <= last_submit_1.items()
    assert check_render(
        question_name=test_question_name_2,
        handler=submit_handler_1,
        last_log=last_submit_1,
        last_action_value="cat",
        score_display_value="100.00%",
    )

    last_submit_2, submit_handler_2 = mock_action(
        question_name=test_question_name_1,
        action="submit",
        action_value="3",
    )

    expected_last_submit_2 = {
        "last_submit": {
            test_question_name_1: {"data": "3", "type": "raw"},
            test_question_name_2: {"data": "cat", "type": "raw"},
        },
        "last_check": {
            test_question_name_1: {
                "data": "sqrt(cos(omega)+j*sin(omega))",
                "type": "raw",
            }
        },
        "nsubmits_used": {test_question_name_1: 1, test_question_name_2: 1},
        "score_displays": {
            test_question_name_1: "<span "
            'style="color:rgb(200,0,0);font-weight:bolder;">0.00%</span>',
            test_question_name_2: "<span "
            'style="color:rgb(0,200,0);font-weight:bolder;">100.00%</span>',
        },
        "scores": {test_question_name_1: False, test_question_name_2: True},
        "last_action": {test_question_name_1: "submit", test_question_name_2: "submit"},
    }

    assert expected_last_submit_2.items() <= last_submit_2.items()
    assert check_render(
        question_name=test_question_name_1,
        handler=submit_handler_2,
        last_log=last_submit_2,
        last_action_value="3",
        score_display_value="0.00%",
        render_value_fragment="3",
    )


def test_workflow_4():
    """
    Submit `test_question_name_2`, check `test_question_name_1`, submit `test_question_name_2`, submit
    `test_question_name_1`, submit test_question_name_2`, check `test_question_name_1` with a new value,
    revert `test_question_name_1`, and submit `test_question_name_1`.

    This workflow tests actions to alternating questions in sequence.
    """
    test_question_name_1 = "q000008"
    test_question_name_2 = "q000000"

    last_submit_1, submit_handler_1 = mock_action(
        question_name=test_question_name_2,
        action="submit",
        action_value="cat",
    )

    expected_last_submit_1 = {
        "last_submit": {test_question_name_2: {"data": "cat", "type": "raw"}},
        "nsubmits_used": {test_question_name_2: 1},
        "score_displays": {
            test_question_name_2: "<span "
            'style="color:rgb(0,200,0);font-weight:bolder;">100.00%</span>',
        },
        "scores": {test_question_name_2: True},
        "last_action": {test_question_name_2: "submit"},
    }

    assert expected_last_submit_1.items() <= last_submit_1.items()
    assert check_render(
        question_name=test_question_name_2,
        handler=submit_handler_1,
        last_log=last_submit_1,
        last_action_value="cat",
        score_display_value="100.00%",
    )

    last_check_1, check_handler_1 = mock_action(
        question_name=test_question_name_1,
        action="check",
        action_value="sqrt(cos(omega)+j*sin(omega))",
    )

    expected_last_check_1 = {
        "last_check": {
            test_question_name_1: {
                "data": "sqrt(cos(omega)+j*sin(omega))",
                "type": "raw",
            }
        },
        "last_submit": {test_question_name_2: {"data": "cat", "type": "raw"}},
        "score_displays": {
            test_question_name_1: "",
            test_question_name_2: "<span "
            'style="color:rgb(0,200,0);font-weight:bolder;">100.00%</span>',
        },
        "last_action": {test_question_name_1: "check", test_question_name_2: "submit"},
        "nsubmits_used": {test_question_name_2: 1},
        "scores": {test_question_name_2: True},
    }

    assert expected_last_check_1.items() <= last_check_1.items()
    assert check_render(
        question_name=test_question_name_1,
        handler=check_handler_1,
        last_log=last_check_1,
        last_action_value="sqrt(cos(omega)+j*sin(omega))",
        has_previous_submission=False,
        render_value_fragment="cos",
    )

    last_submit_2, submit_handler_2 = mock_action(
        question_name=test_question_name_2,
        action="submit",
        action_value="cat",
    )

    expected_last_submit_2 = {
        "last_check": {
            test_question_name_1: {
                "data": "sqrt(cos(omega)+j*sin(omega))",
                "type": "raw",
            }
        },
        "last_submit": {
            test_question_name_2: {"data": "cat", "type": "raw"},
        },
        "score_displays": {
            test_question_name_1: "",
            test_question_name_2: "<span "
            'style="color:rgb(0,200,0);font-weight:bolder;">100.00%</span>',
        },
        "last_action": {
            test_question_name_1: "check",
            test_question_name_2: "submit",
        },
        "nsubmits_used": {test_question_name_2: 2},
        "scores": {test_question_name_2: True},
    }

    assert expected_last_submit_2.items() <= last_submit_2.items()
    assert check_render(
        question_name=test_question_name_2,
        handler=submit_handler_2,
        last_log=last_submit_2,
        last_action_value="cat",
        score_display_value="100.00%",
    )

    last_submit_3, submit_handler_3 = mock_action(
        question_name=test_question_name_1,
        action="submit",
        action_value="15",
    )

    expected_last_submit_3 = {
        "last_check": {
            test_question_name_1: {
                "data": "sqrt(cos(omega)+j*sin(omega))",
                "type": "raw",
            }
        },
        "last_submit": {
            test_question_name_1: {"data": "15", "type": "raw"},
            test_question_name_2: {"data": "cat", "type": "raw"},
        },
        "score_displays": {
            test_question_name_1: "<span "
            'style="color:rgb(200,0,0);font-weight:bolder;">0.00%</span>',
            test_question_name_2: "<span "
            'style="color:rgb(0,200,0);font-weight:bolder;">100.00%</span>',
        },
        "last_action": {
            test_question_name_1: "submit",
            test_question_name_2: "submit",
        },
        "nsubmits_used": {test_question_name_1: 1, test_question_name_2: 2},
        "scores": {test_question_name_1: False, test_question_name_2: True},
    }

    assert expected_last_submit_3.items() <= last_submit_3.items()
    assert check_render(
        question_name=test_question_name_1,
        handler=submit_handler_3,
        last_log=last_submit_3,
        last_action_value="15",
        score_display_value="0.00%",
        render_value_fragment="15",
    )

    last_submit_4, submit_handler_4 = mock_action(
        question_name=test_question_name_2,
        action="submit",
        action_value="Hello, world!",
    )

    expected_last_submit_4 = {
        "last_check": {
            test_question_name_1: {
                "data": "sqrt(cos(omega)+j*sin(omega))",
                "type": "raw",
            }
        },
        "last_submit": {
            test_question_name_1: {"data": "15", "type": "raw"},
            test_question_name_2: {"data": "Hello, world!", "type": "raw"},
        },
        "score_displays": {
            test_question_name_1: "<span "
            'style="color:rgb(200,0,0);font-weight:bolder;">0.00%</span>',
            test_question_name_2: "<span "
            'style="color:rgb(200,0,0);font-weight:bolder;">0.00%</span>',
        },
        "last_action": {
            test_question_name_1: "submit",
            test_question_name_2: "submit",
        },
        "nsubmits_used": {test_question_name_1: 1, test_question_name_2: 3},
        "scores": {test_question_name_1: False, test_question_name_2: False},
    }

    assert expected_last_submit_4.items() <= last_submit_4.items()
    assert check_render(
        question_name=test_question_name_2,
        handler=submit_handler_4,
        last_log=last_submit_4,
        last_action_value="Hello, world!",
        score_display_value="0.00%",
    )

    last_check_2, check_handler_2 = mock_action(
        question_name=test_question_name_1,
        action="check",
        action_value="7",
    )

    expected_last_check_2 = {
        "last_check": {
            test_question_name_1: {
                "data": "7",
                "type": "raw",
            }
        },
        "last_submit": {
            test_question_name_1: {"data": "15", "type": "raw"},
            test_question_name_2: {"data": "Hello, world!", "type": "raw"},
        },
        "score_displays": {
            test_question_name_1: "",
            test_question_name_2: "<span "
            'style="color:rgb(200,0,0);font-weight:bolder;">0.00%</span>',
        },
        "last_action": {
            test_question_name_1: "check",
            test_question_name_2: "submit",
        },
        "nsubmits_used": {test_question_name_1: 1, test_question_name_2: 3},
        "scores": {test_question_name_1: False, test_question_name_2: False},
    }

    assert expected_last_check_2.items() <= last_check_2.items()
    assert check_render(
        question_name=test_question_name_1,
        handler=check_handler_2,
        last_log=last_check_2,
        last_action_value="7",
    )

    last_revert_1, revert_handler_1 = mock_action(
        question_name=test_question_name_1, action="revert", action_value="9"
    )

    expected_last_revert_1 = {
        "last_check": {
            test_question_name_1: {
                "data": "15",
                "type": "raw",
            }
        },
        "last_submit": {
            test_question_name_1: {"data": "15", "type": "raw"},
            test_question_name_2: {"data": "Hello, world!", "type": "raw"},
        },
        "score_displays": {
            test_question_name_1: "<span "
            'style="color:rgb(200,0,0);font-weight:bolder;">0.00%</span>',
            test_question_name_2: "<span "
            'style="color:rgb(200,0,0);font-weight:bolder;">0.00%</span>',
        },
        "last_action": {
            test_question_name_1: "revert",
            test_question_name_2: "submit",
        },
        "nsubmits_used": {test_question_name_1: 1, test_question_name_2: 3},
        "scores": {test_question_name_1: False, test_question_name_2: False},
    }

    assert expected_last_revert_1.items() <= last_revert_1.items()
    assert check_render(
        question_name=test_question_name_1,
        handler=revert_handler_1,
        last_log=last_revert_1,
        score_display_value="0.00%",
        render_value_fragment="15",
    )

    last_submit_4, submit_handler_4 = mock_action(
        question_name=test_question_name_1,
        action="submit",
        action_value="sqrt(cos(omega)+j*sin(omega))",
    )

    expected_last_submit_4 = {
        "last_check": {
            test_question_name_1: {
                "data": "15",
                "type": "raw",
            }
        },
        "last_submit": {
            test_question_name_1: {
                "data": "sqrt(cos(omega)+j*sin(omega))",
                "type": "raw",
            },
            test_question_name_2: {"data": "Hello, world!", "type": "raw"},
        },
        "score_displays": {
            test_question_name_1: "<span "
            'style="color:rgb(0,200,0);font-weight:bolder;">100.00%</span>',
            test_question_name_2: "<span "
            'style="color:rgb(200,0,0);font-weight:bolder;">0.00%</span>',
        },
        "last_action": {
            test_question_name_1: "submit",
            test_question_name_2: "submit",
        },
        "nsubmits_used": {test_question_name_1: 2, test_question_name_2: 3},
        "scores": {test_question_name_1: True, test_question_name_2: False},
    }

    assert expected_last_submit_4.items() <= last_submit_4.items()
    assert check_render(
        question_name=test_question_name_1,
        handler=submit_handler_4,
        last_log=last_submit_4,
        last_action_value="sqrt(cos(omega)+j*sin(omega))",
        score_display_value="100.00%",
        render_value_fragment="cos",
    )
