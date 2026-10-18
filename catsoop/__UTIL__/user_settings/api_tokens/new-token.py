cs_content_header = "Generate New API Token"

if str(cs_username) == "None":
    print(
        '<p>Please <a href="CURRENT/?loginaction=login">log in</a> to use this page.</p>'
    )
elif "sure" not in cs_form:
    print(
        "<p>Are you sure you want to generate a new API token?  Anyone with access to this token will be able to access this CAT-SOOP instance as though they were you, so please keep it secure.</p>"
    )
    print(
        '<p><a href="CURRENT/new-token?sure=yes">Confirm</a>, or <a href="CURRENT">cancel and return to your API token list</a>.'
    )
else:
    # if we're here, we actually want to generate a new key.  go for it.
    new_token = csm_api.new_api_token(globals(), cs_username)
    print("<p>Your new API token is ready!  The token is shown below:</p>")
    print(f"<pre>{new_token}</pre>")
    print("<p>Before continuing, please note:</p>")
    print("<ul>")
    print(
        "<li>The full token will <b>never</b> be shown to you again.  Make sure you take a copy before continuing.</li>"
    )
    print(
        "<li>Anyone with access to this token will be able to interact with this CAT-SOOP instance as though they were you, so please keep it secure.</p>"
    )
    print("</ul>")
    print(
        '<p>If you have read and understand the points above, you can <a href="CURRENT">return to your API token list.</p>'
    )
