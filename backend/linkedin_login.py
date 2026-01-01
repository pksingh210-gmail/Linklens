# backend/linkedin_login.py

from pathlib import Path
import json
import time
import os
from playwright.sync_api import sync_playwright

DATA_DIR = Path("data/linkedin")
DATA_DIR.mkdir(parents=True, exist_ok=True)


def cookie_path_for_user(username: str) -> Path:
    """Return path to store li_at cookie for a given username."""
    safe_name = username.replace("@", "_at_").replace(".", "_dot_")
    return DATA_DIR / f"li_at_{safe_name}.json"


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

    # ------------------ Cookie-only login ------------------
    def login_with_cookie(self, username: str, li_at: str):
        """Login using li_at cookie only (cloud-safe)."""
        if not self.browser:
            self.start_browser()

        if not li_at:
            raise ValueError("Missing li_at cookie for login")

        # Add cookie to browser context
        self.context.add_cookies([{
            "name": "li_at",
            "value": li_at,
            "domain": ".linkedin.com",
            "path": "/",
            "secure": True,
            "httpOnly": True
        }])

        self.page.goto("https://www.linkedin.com/feed/", timeout=60000)
        time.sleep(3)

        if "/feed" in self.page.url:
            self.logged_in = True
            self.cookies = {"li_at": li_at}
            self.save_cookie(username, li_at)
            if self.status_callback:
                self.status_callback(f"✅ Logged in using li_at cookie for {username}")
        else:
            self.logged_in = False
            if self.status_callback:
                self.status_callback(f"❌ li_at cookie rejected for {username}")
            raise RuntimeError("li_at cookie rejected by LinkedIn")

    # ------------------ Save/load li_at cookie ------------------
    def save_cookie(self, username: str, li_at: str):
        """Save li_at cookie to file for a given user."""
        path = cookie_path_for_user(username)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump({"li_at": li_at}, f)
        if self.status_callback:
            self.status_callback(f"💾 li_at cookie saved for {username} at {path}")

    def load_cookie(self, username: str) -> str | None:
        """Load li_at cookie for user if exists."""
        path = cookie_path_for_user(username)
        if path.exists():
            with open(path, "r") as f:
                data = json.load(f)
                li_at = data.get("li_at")
                if self.status_callback:
                    self.status_callback(f"💾 Loaded li_at cookie for {username}")
                return li_at
        return None

    # ------------------ Legacy: username/password login (optional) ------------------
    def login_with_password(self, username: str, password: str):
        """Fallback login for local/laptop use (not recommended in cloud)."""
        if not self.browser:
            self.start_browser()

        self.page.goto("https://www.linkedin.com/login")
        time.sleep(2)
        self.page.fill("input#username", username)
        self.page.fill("input#password", password)
        self.page.click("button[type=submit]")

        time.sleep(5)
        self.logged_in = self.verify_login()

        if self.logged_in:
            self.cookies = self.context.cookies()
            if self.status_callback:
                self.status_callback(f"✅ Logged in with password as {username}")
        else:
            if self.status_callback:
                self.status_callback(f"❌ Login failed for {username}")

        return self.logged_in

    # ------------------ Verify login ------------------
    def verify_login(self):
        """Check if user is logged in by visiting feed."""
        self.page.goto("https://www.linkedin.com/feed/")
        time.sleep(3)
        return "feed" in self.page.url

    # ------------------ Close browser ------------------
    def close(self):
        """Close browser and context."""
        if self.context:
            self.context.close()
        if self.page:
            self.page.close()
        if self.browser:
            self.browser.close()


