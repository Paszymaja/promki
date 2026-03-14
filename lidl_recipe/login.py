from pathlib import Path

from dotenv import set_key

LOGIN_TIMEOUT_MS = 300_000  # 5 minutes


def capture_token(country: str = "PL") -> str:
    try:
        from playwright.sync_api import sync_playwright, Error as PlaywrightError
    except ImportError:
        raise SystemExit(
            "Playwright is required for --login. Install with:\n"
            "  uv sync --extra login\n"
            "  playwright install chromium"
        )

    token = None

    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=False)
            except PlaywrightError:
                raise SystemExit(
                    "Chromium not found. Install it with:\n"
                    "  playwright install chromium"
                )

            context = browser.new_context()
            page = context.new_page()

            url = f"https://www.lidl.{country.lower()}/prm/promotions-list"
            print(f"Opening {url} — please log in...")
            page.goto(url, wait_until="domcontentloaded")

            elapsed = 0
            try:
                while not token and elapsed < LOGIN_TIMEOUT_MS:
                    page.wait_for_timeout(500)
                    elapsed += 500
                    cookies = context.cookies()
                    for cookie in cookies:
                        if cookie["name"] == "authToken":
                            token = cookie["value"]
                            break
            except PlaywrightError:
                pass  # browser closed by user

            browser.close()
    except PlaywrightError:
        pass  # browser already closed

    if not token:
        raise SystemExit("No token captured. Did you log in and reach the coupons page?")

    print("Token captured successfully.")
    return token


def save_token_to_env(token: str) -> None:
    env_path = Path(".env")
    if not env_path.exists():
        env_path.touch()
    set_key(str(env_path), "LIDL_ACCESS_TOKEN", token)
