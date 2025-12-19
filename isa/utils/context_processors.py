from flask import session as flask_session
from flask_babel import Locale


class _SessionWrapper:
    """Light wrapper around flask.session to make testing easier.

    Tests patch isa.utils.context_processors.session; using a simple
    wrapper object here prevents accessing the real LocalProxy during
    unittest.mock.patch setup (which would require a request context).
    """

    def get(self, key, default=None):
        return flask_session.get(key, default)


# Exposed name used in tests
session = _SessionWrapper()


def rtl_context_processor():
    """
    Context processor to inject 'is_rtl' variable into templates.

    This processor checks the 'session_language' from the session and determines
    if the current language is right-to-left (RTL). It then injects the 'is_rtl'
    variable into the template context, which can be used to conditionally apply
    RTL styles or logic in templates.
    
    """
    # Fall back to English if no language is set or it's falsy
    session_language = session.get('lang') or 'en'
    is_rtl = Locale(session_language).text_direction == "rtl"
    return dict(is_rtl=is_rtl)
