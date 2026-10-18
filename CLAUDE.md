# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
make develop                 # pip3 install -e .  (editable install; restart server to pick up changes)
catsoop configure            # interactive wizard -> ~/.config/catsoop/config.py (override path with $CATSOOP_CONFIG)
catsoop start                # launch web server (:7667), checker, reporter (:7668), plugins
catsoop logread|logwrite|logedit ...   # inspect/modify cslog log files
make test                    # pytest catsoop/test
pytest catsoop/test/test_cslog.py                       # single file
pytest catsoop/test/test_cslog.py::TestClass::test_name # single test
black .                      # required formatter; upstream checklist requires no diff after running it
```

Tests need no manual setup: `catsoop/test/setup_data.py` (imported by `catsoop/test/__init__.py`) builds `/tmp/catsoop_test`, symlinks `catsoop/__TEST_COURSE__` in as `test_course`, and points `CATSOOP_CONFIG` at `catsoop/test/test_config.py`.

Local demo deployment (see `demo/README.md`): runs this checkout from venv `~/.venvs/catsoop-desktop` with its own config `~/.config/catsoop-desktop/config.py` (selected via `CATSOOP_CONFIG`; `~/.config/catsoop/config.py` belongs to an unrelated older deployment and must not be used). `python demo/setup_demo.py` links `demo/courses/*` into the data root `~/.local/share/catsoop`, creates login accounts (password `demo1234`) and seeds simulated submissions; `--clear` undoes it. Start with `demo/start.sh` (http://localhost:7667).

Courses live in `<cs_data_root>/courses/<course>/` (default data root `~/.local/share/catsoop`); the sample course is at `https://catsoop.org/catsoop/sample_course`.

## Upstream contribution rules (from `website/docs/contributing/hacking`)

- **Upstream CAT-SOOP does not accept code or docs written in whole or in part by generative AI.** Changes made with Claude are fine for local/fork use but must not be submitted upstream.
- Prefer functions and dicts over classes.
- Public functions need docstrings in CAT-SOOP Markdown (API docs on the website are generated from them); update `website/` when behavior changes.
- Add a `CHANGELOG.md` entry for changes.

## Architecture

### Processes (`catsoop/scripts/start_catsoop.py`)
Independent processes that communicate **only through the filesystem** under `cs_data_root`:
- **Web**: `scripts/wsgi_server.py` (cheroot) or uWSGI → `catsoop/wsgi.py:application` → `dispatch.main`.
- **Checker** (`scripts/checker.py`): asynchronous grading. Submissions move through `_logs/_checker/{staging,queued,running,results}/`; files left in `running/` at startup are requeued. Parallelism via `cs_checker_parallel_checks`.
- **Reporter** (`scripts/reporter.py`): websocket server that watches those dirs and pushes queue position/status to the browser.

### Request lifecycle (`dispatch.py:main`)
1. `/_static/...` short-circuits to a static file.
2. `loader.load_global_data` execs `base_context.py` (which execs the user's `config.py`) into a fresh **`context` dict**. Everything is passed around as this dict: `cs_*` keys are config/state, `csm_*` keys are core modules (`csm_cslog`, `csm_auth`, `csm_loader`, ...). Code in course files, handlers, qtypes and auth backends is `exec`'d into it and accesses these as globals.
3. Session from cookie `catsoop_sid_<hash>` (`session.py`, stored as a cslog log, 2-week expiry).
4. `/_lti/...` is handled by `lti.py` before auth, which then re-calls `dispatch.main`.
5. `loader.do_preload`: execs every `preload.py` from course root down to the page. **Runs before authentication** — preload can't see user info, but can alter auth behavior (e.g. `cs_auth_required`, `cs_permissions`).
6. Auth (see below).
7. `loader.load_content`: execs the page's `content.{md,xml,py,catsoop}`, evaluating `<python>` tags; `tutor.question(...)` calls populate `cs_problem_spec`. Children's `preload.py` files are run into `cs_children`.
8. `tutor.handle_page` → `__HANDLERS__/<cs_handler>/<name>.py:handle(context)` (default `default`). The default handler dispatches on the `action` form field via `mode_handlers` (`view`, `submit`, `check`, `save`, `viewanswer`, `grade`, `whdw`, `manage_groups`, ...). Returning a 3-tuple sends a raw HTTP response.
9. `display_page` renders the template; session saved.

Plugin hooks (`loader.run_plugins`): `pre_preload`, `pre_auth`, `post_auth`, `post_load`, `pre_handle`, `post_handle`. Course-level hooks: `cs_post_load`, `cs_pre_handle`, `cs_post_handle` defined in preload.

Special top-level paths: `_util` (`__UTIL__`, e.g. user_settings, api), `_qtype`, `_handler`, `_plugin`, `_auth` (e.g. OIDC callbacks at `/_auth/openid_connect/callback`). `cs_sole_course` makes one course the root and rewrites paths (several recent fixes concern this).

### Authentication — *who* is the user (`auth.py:get_logged_in_user`)
Precedence: LTI session data → `api_token` form field (`api.py`, `_api_tokens` log) → the backend named by `cs_auth_type` at `__AUTH__/<name>/<name>.py`.

A backend defines `get_logged_in_user(context)` returning `{username, name, email}`, `{}` (anonymous), or a control dict: `cs_reload`, `cs_redirect`, or `cs_render_now` (render `cs_content` immediately, used for login forms). Optional `user_menu_options(context)`. Login flows are driven by `?loginaction=` (`login`, `logout`, `change_password`, `confirm_reg`, ...). Backends: `login` (built-in accounts, PBKDF2-SHA512 hashes in `_logininfo` log, email confirmation), `openid_connect` (auth code + PKCE; reuses helpers from `login` via `get_auth_type_by_name`), `ldap3`, `sso`, `dummy` (fixed user, dev only). LTI users get username `lti_<id>` (prefix configurable in `cs_lti_config`).

### Authorization — *what* they can do (`auth.py:_get_user_information`)
Per-course, independent of auth backend:
- Execs `<data_root>/courses/<course>/__USERS__/<username>.py` (e.g. `role = "Student"`, `section = "2"`) into user_info.
- Unless the file sets `permissions` directly, permissions = `cs_permissions[role]` from course preload; missing file → `cs_default_role`; logged out → role `Unauthenticated`, at most `view`.
- Permission strings: `view`, `submit`, `view_all`/`submit_all` (ignore release/due dates), `impersonate`, `admin`, `whdw`, `email`, `grade`. See `__TEST_COURSE__/preload.py` for the canonical role table.
- Impersonation: `?as=<user>` (needs `impersonate`; real user kept in `user_info["real_user"]`; vetoable via `cs_impersonation_allowed(old, new)`). `?as_role=<role>` previews with the intersection of permissions.
- Enforcement is ad hoc set membership checks in handlers (e.g. `"submit" not in perms and "submit_all" not in perms` in `default.py`).

### Storage (`cslog.py`)
No SQL database. Every datum is an append-only log of pickled (optionally lzma-compressed / encrypted) Python objects, addressed by `(db_name, path, logname)`. With a path: `_logs/_courses/<course>/<db_name>/<path...>/<logname>.log` (db_name is usually a username); without: `_logs/<db_name>/<logname>.log` (e.g. `_sessions`, `_logininfo`, `_api_tokens`, `_question_info`). Core API: `most_recent`, `read_log`, `update_log` (append), `overwrite_log`, `modify_most_recent`. When encryption is on, path components are hashed, so files can't be located by name.

### Analytics dashboard
`?action=analytics` on any course page (needs `whdw`): `catsoop/analytics.py` computes everything live on each request from `__USERS__`, page `preload.py` files (`cs_long_name`, `cs_release_date`, `cs_due_date`, `cs_assignment_category`), the `_question_info` cache, and per-student `problemstate`/`problemgrades` logs; `handle_analytics` in `default.py` renders HTML or CSV. Course settings: `cs_analytics_category_weights`, `cs_analytics_student_roles`, `cs_analytics_at_risk_threshold`. Core CAT-SOOP has no categories/weights/gradebook of its own, and late work is accepted by default unless `cs_auto_lock` is set.

### Question types (`__QTYPES__/<name>/<name>.py`)
Module-level `defaults`, `total_points(**info)`, `handle_submission(submissions, **info)` (returns score/message), `render_html(last_log, **info)`, `answer_display(**info)`. `smallbox` is the minimal example; `tutor.qtype_inherit` lets a type extend another. `pythoncode` runs student code via `__SANDBOXES__` (`python`, `bwrap`, `remote`). Courses can define their own types in a course-level `__QTYPES__`.

## Repo notes
- On Windows/WSL checkouts, CRLF conversion can make every file appear modified; check with `git diff --ignore-cr-at-eol --stat` before assuming real changes.
- `website/` is itself a CAT-SOOP course (the catsoop.org docs).
