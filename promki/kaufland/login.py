from pathlib import Path

LOGIN_TIMEOUT_MS = 300_000  # 5 minutes for interactive login
SILENT_TIMEOUT_MS = 20_000  # 20s for silent refresh via saved session

KAUFLAND_COUPONS_URL = "https://sklep.kaufland.pl/oferta/strefa-korzysci-xtra.html"


def capture_cookies(session_file: Path | None = None, silent: bool = False) -> dict | None:
    has_session = session_file is not None and session_file.exists()
    if silent and not has_session:
        return None

    try:
        from playwright.sync_api import sync_playwright, Error as PlaywrightError
    except ImportError:
        raise SystemExit(
            "Playwright is required for login. Install with:\n"
            "  uv sync --extra login\n"
            "  playwright install chromium"
        )

    storage_state = None
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

            if not silent:
                print(f"Opening {KAUFLAND_COUPONS_URL} — please log in...")

            # In silent mode, intercept API responses to detect
            # that the page's JS successfully refreshed the token.
            if silent:
                def _on_response(response):
                    nonlocal storage_state
                    if storage_state is not None:
                        return
                    if response.ok and response.url.startswith(
                        "https://sklep.kaufland.pl/.kl"
                    ):
                        storage_state = context.storage_state()
                        if session_file is not None:
                            try:
                                context.storage_state(path=str(session_file))
                            except PlaywrightError:
                                pass

                page.on("response", _on_response)

            page.goto(KAUFLAND_COUPONS_URL, wait_until="domcontentloaded")

            if silent:
                elapsed = 0
                try:
                    while not storage_state and elapsed < timeout_ms:
                        page.wait_for_timeout(500)
                        elapsed += 500
                except PlaywrightError:
                    pass
            else:
                saw_login_flow = False
                elapsed = 0
                try:
                    while not storage_state and elapsed < timeout_ms:
                        page.wait_for_timeout(500)
                        elapsed += 500

                        current_url = page.url

                        if "account.kaufland.com" in current_url:
                            saw_login_flow = True

                        if saw_login_flow and current_url.startswith(
                            "https://sklep.kaufland.pl/"
                        ):
                            page.wait_for_timeout(2000)
                            storage_state = context.storage_state()
                            if session_file is not None:
                                try:
                                    context.storage_state(path=str(session_file))
                                except PlaywrightError:
                                    pass
                            break
                except PlaywrightError:
                    pass

            browser.close()
    except PlaywrightError:
        pass

    if not storage_state:
        if silent:
            return None
        raise SystemExit("No session captured. Did you log in and reach the coupons page?")

    if not silent:
        print("Session captured successfully.")
    return storage_state


def _load_cookies_from_state(session_file: Path) -> dict[str, str]:
    import json

    with open(session_file) as f:
        state = json.load(f)
    cookies = {}
    for c in state.get("cookies", []):
        cookies[c["name"]] = c["value"]
    return cookies
