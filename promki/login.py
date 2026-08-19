import json
from pathlib import Path

LOGIN_TIMEOUT_MS = 300_000  # 5 minutes for interactive login
SILENT_TIMEOUT_MS = 20_000  # 20s for silent refresh via saved session


def load_access_token(session_file: Path | None = None) -> str | None:
    if session_file is None or not session_file.exists():
        return None
    try:
        with open(session_file) as f:
            state = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    if not isinstance(state, dict):
        return None
    for cookie in state.get("cookies", []):
        if isinstance(cookie, dict) and cookie.get("name") == "authToken":
            token = cookie.get("value")
            if token:
                return token
    return None


def capture_token(session_file: Path | None = None, silent: bool = False) -> str | None:
    has_session = session_file is not None and session_file.exists()
    if silent and not has_session:
        return None  # nothing to try silently — caller can fall back to interactive

    try:
        from playwright.sync_api import sync_playwright, Error as PlaywrightError
    except ImportError:
        raise SystemExit(
            "Playwright is required for --login. Install with:\n"
            "  uv sync --extra login\n"
            "  playwright install chromium"
        )

    token = None
    timeout_ms = SILENT_TIMEOUT_MS if silent else LOGIN_TIMEOUT_MS

    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=silent)
            except PlaywrightError:
                raise SystemExit(
                    "Chromium not found. Install it with:\n"
                    "  playwright install chromium"
                )

            context_kwargs = {}
            if has_session:
                context_kwargs["storage_state"] = str(session_file)
            context = browser.new_context(**context_kwargs)
            page = context.new_page()

            url = "https://www.lidl.pl/prm/promotions-list"
            if not silent:
                print(f"Opening {url} — please log in...")
            page.goto(url, wait_until="domcontentloaded")

            elapsed = 0
            try:
                while not token and elapsed < timeout_ms:
                    page.wait_for_timeout(500)
                    elapsed += 500
                    cookies = context.cookies()
                    for cookie in cookies:
                        if cookie["name"] == "authToken":
                            token = cookie["value"]
                            if session_file is not None:
                                try:
                                    context.storage_state(path=str(session_file))
                                except PlaywrightError:
                                    pass
                            break
            except PlaywrightError:
                pass  # browser closed by user

            browser.close()
    except PlaywrightError:
        pass

    if not token:
        if silent:
            return None
        raise SystemExit("No token captured. Did you log in and reach the coupons page?")

    if not silent:
        print("Token captured successfully.")
    return token
