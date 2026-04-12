from http import cookies

ADVISOR_SESSION_COOKIE = "advisor_session"


def get_cookie_value(headers: dict, name: str) -> str | None:
    raw_cookie = headers.get("Cookie")
    if not raw_cookie:
        return None
    jar = cookies.SimpleCookie()
    jar.load(raw_cookie)
    morsel = jar.get(name)
    return morsel.value if morsel else None


def build_session_cookie(value: str, secure: bool) -> str:
    parts = [
        f"{ADVISOR_SESSION_COOKIE}={value}",
        "HttpOnly",
        "Path=/",
        "SameSite=Lax",
        "Max-Age=86400",
    ]
    if secure:
        parts.append("Secure")
    return "; ".join(parts)


def build_clear_session_cookie(secure: bool) -> str:
    parts = [
        f"{ADVISOR_SESSION_COOKIE}=",
        "HttpOnly",
        "Path=/",
        "SameSite=Lax",
        "Max-Age=0",
    ]
    if secure:
        parts.append("Secure")
    return "; ".join(parts)
