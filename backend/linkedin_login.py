# backend/linkedin_login.py

from pathlib import Path
import json
import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

DATA_DIR = Path("data/linkedin")
DATA_DIR.mkdir(parents=True, exist_ok=True)


def cookie_path_for_user(username: str) -> Path:
    """Return path to store session cookie for a given username."""
    safe_name = username.replace("@", "_at_").replace(".", "_dot_")
    return DATA_DIR / f"session_{safe_name}.json"


class LinkedInLogin:
    def __init__(self, headless=True, status_callback=None):
        self.headless = headless
        self.status_callback = status_callback
        self.logged_in = False
        self.cookies = {}
        self.browser = None
        self.context = None
        self.page = None

    def start_browser(self):
        """Start Playwright browser and context."""
        pw = sync_playwright().start()
        self.browser = pw.chromium.launch(headless=self.headless)
        self.context = self.browser.new_context()
        self.page = self.context.new_page()

    def login(self, username: str, password: str):
        """Login to LinkedIn using cookies if present, otherwise username/password."""
        cookie_file = cookie_path_for_user(username)

        if not self.browser:
            self.start_browser()

        # --- Try to load cookies first ---
        if cookie_file.exists():
            try:
                self.load_cookies(cookie_file)
                if self.verify_login():
                    self.logged_in = True
                    if self.status_callback:
                        self.status_callback(f"✅ Logged in using cloud cookies for {username}")
                    return True
                else:
                    if self.status_callback:
                        self.status_callback(f"⚠️ Cookies invalid/expired for {username}, doing full login")
            except Exception as e:
                if self.status_callback:
                    self.status_callback(f"⚠️ Failed to load cookies: {e}, doing full login")

        # --- Full login with username/password ---
        try:
            self.page.goto("https://www.linkedin.com/login")
            time.sleep(2)
            self.page.fill("input#username", username)
            self.page.fill("input#password", password)
            self.page.click("button[type=submit]")

            # wait for feed page or error
            self.logged_in = self.wait_for_feed(timeout=20)
        except PlaywrightTimeoutError:
            self.logged_in = False
        except Exception as e:
            self.logged_in = False
            if self.status_callback:
                self.status_callback(f"❌ Login exception: {e}")

        # --- Save cookies if login successful ---
        if self.logged_in:
            self.cookies = self.context.cookies()
            self.save_cookies(cookie_file)
            if self.status_callback:
                self.status_callback(f"✅ Logged in successfully as {username}")
        else:
            if self.status_callback:
                self.status_callback(f"❌ Login failed for {username}")

        return self.logged_in

    def wait_for_feed(self, timeout=20):
        """Wait for LinkedIn feed page to confirm login."""
        start = time.time()
        while time.time() - start < timeout:
            self.page.goto("https://www.linkedin.com/feed/")
            time.sleep(3)
            if "feed" in self.page.url:
                return True
            # optionally check for login error messages here
        return False

    def load_cookies(self, path: Path):
        """Load cookies from JSON file into the browser context."""
        if path.exists():
            with open(path, "r") as f:
                cookies = json.load(f)
            self.context.add_cookies(cookies)
            self.cookies = cookies
            if self.status_callback:
                self.status_callback(f"💾 Loaded cookies from {path}")

    def save_cookies(self, path: Path):
        """Save current session cookies to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.context.cookies(), f)
        if self.status_callback:
            self.status_callback(f"💾 Saved session cookie to {path}")

    def verify_login(self):
        """Check if user is logged in by visiting the feed."""
        try:
            self.page.goto("https://www.linkedin.com/feed/")
            time.sleep(3)
            return "feed" in self.page.url
        except Exception:
            return False

    def close(self):
        """Close browser and context."""
        if self.context:
            self.context.close()
        if self.page:
            self.page.close()
        if self.browser:
            self.browser.close()
