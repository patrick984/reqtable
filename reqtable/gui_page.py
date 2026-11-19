def render_page(token: str) -> str:
    return f"<!doctype html><title>reqtable</title><script>const TOKEN = {token!r};</script>"
