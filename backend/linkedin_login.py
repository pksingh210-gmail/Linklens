# backend/linkedin_login.py
import time
import os
import base64
from pathlib import Path
from playwright.sync_api import sync_playwright

class LinkedInLogin:
    def __init__(self, headless=True, status_callback=None):
        self.headless = headless
        self.status_cb = status_callback
        self.logged_in = False
        self.cookies = {}

    def log(self, msg):
        if self.status_cb:
            self.status_cb(msg)
        else:
            print(msg)

    def login(self, username=None, password=None):
        from playwright.sync_api import sync_playwright, TimeoutError

        # Try using cookie first from environment
        env_var_name = f"LINKEDIN_SESSION_{username.split('@')[0].upper()}" if username else None
        saved_cookie = os.environ.get(env_var_name)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context()

            # Load cookie if exists
            if saved_cookie:
                import json
                try:
                    cookies = json.loads(saved_cookie)
                    context.add_cookies(cookies)
                    self.log("✅ Loaded cookies from env")
                except Exception as e:
                    self.log(f"⚠️ Failed to load cookies: {e}")

            page = context.new_page()
            try:
                page.goto("https://www.linkedin.com/login", timeout=120_000)

                # If username/password provided, perform login
                if username and password:
                    page.fill('input#username', username)
                    page.fill('input#password', password)
                    page.click('button[type="submit"]')

                    # Wait for successful login element
                    page.wait_for_selector('input[placeholder="Search"]', timeout=120_000)
                    self.log("✅ Login successful with username/password")

                    # Save cookies for future sessions
                    cookies = context.cookies()
                    self.cookies = {c['name']: c['value'] for c in cookies}
                    self.log("💾 Cookies saved for session")

                else:
                    # Check if cookies worked
                    if page.url.startswith("https://www.linkedin.com/feed"):
                        self.log("✅ Logged in using cookies")
                        self.logged_in = True

                self.logged_in = True

            except TimeoutError:
                self.log("❌ Login failed: Timeout")
                self.logged_in = False
            finally:
                browser.close()

