cs_content_header = "Delete API Token"

if str(cs_username) == "None":
    print(
        '<p>Please <a href="CURRENT/?loginaction=login">log in</a> to use this page.</p>'
    )
elif "prefix" not in cs_form:
    print(
        '<p>You must specify a prefix to delete.  Please <a href="CURRENT">return to your API token list</a>.</p>'
    )
elif "sure" not in cs_form:
    import html

    prefix = html.escape(cs_form["prefix"])
    print(
        f"<p>Continuing onward will delete all API tokens associated with your account that start with the prefix <code>{prefix!r}</code>.  Are you sure you want to continue?</p>"
    )
    print(
        f'<p><a href="CURRENT/delete-token?prefix={prefix}&sure=yes">Confirm deletion</a>, or <a href="CURRENT">cancel and return to your API token list</a>.</p>'
    )
else:
    # we're here, go ahead and delete.
    prefix = html.escape(cs_form["prefix"])
    tokens = sorted(set(csm_api.get_api_tokens(globals(), cs_username)))
    to_delete = [tok for tok in tokens if tok.startswith(prefix)]
    for token in to_delete:
        csm_api.delete_api_token(globals(), token)
    print(
        f'<p>We have removed <b>{len(to_delete)}</b> token{"s" if len(to_delete) != 1 else ""} from your account.  You may now <a href="CURRENT">return to your API token list.</a></p>'
    )
