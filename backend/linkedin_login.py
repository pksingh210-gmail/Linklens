# backend/linkedin_login.py
import time
import os
import base64
from pathlib import Path
from playwright.sync_api import sync_playwright

class LinkedInLogin:
    def __init__(self, headless: bool = True, status_callback=None):
        self.headless = headless
        self.status_callback = status_callback or (lambda msg: None)
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        self.context = None
        self.page = None
        self.logged_in = False
    
    def _init_context(self, username: str):
        """Initialize context and page for a user."""
        storage_path = Path("data/linkedin") / username.replace('@', '_at_').replace('.', '_')
        storage_path.mkdir(parents=True, exist_ok=True)
        state_file = storage_path / "state.json"
        
        # NEW: Check for session in environment variable
        env_var_name = f"LINKEDIN_SESSION_{username.replace('@', '_').replace('.', '_').upper()}"
        env_session = os.environ.get(env_var_name)
        
        if env_session and not state_file.exists():
            try:
                session_data = base64.b64decode(env_session).decode()
                with open(state_file, 'w') as f:
                    f.write(session_data)
                self.status_callback(f"✅ Loaded session from environment variable")
            except Exception as e:
                self.status_callback(f"⚠️ Failed to load env session: {str(e)[:50]}")
        
        time.sleep(1)
        
        if state_file.exists():
            time.sleep(1)
            self.status_callback(f"🔄 Loading existing LinkedIn session for {username}")
            self.context = self.browser.new_context(storage_state=str(state_file))
            self.page = self.context.new_page()
            
            try:
                self.page.goto("https://www.linkedin.com/feed/", timeout=30000)
                time.sleep(3)
                
                if "feed" in self.page.url or "/in/" in self.page.url:
                    self.logged_in = True
                    self.status_callback("✅ Reused saved login session")
                    return
                else:
                    self.status_callback("⚠️ Saved session invalid, logging in fresh...")
            except Exception as e:
                self.status_callback(f"⚠️ Session validation error: {str(e)[:50]}")
        
        # If no valid session, create fresh context and page
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
    
    def login(self, username: str, password: str):
        """Perform login."""
        self._init_context(username)
        
        if self.logged_in:
            return
        
        self.status_callback(f"🔐 Logging in as {username}")
        
        try:
            self.page.goto("https://www.linkedin.com/login", timeout=60000)
            time.sleep(2)
            
            # Wait for login form
            self.page.wait_for_selector("input#username", timeout=30000)
            
            self.page.fill("input#username", username)
            self.page.fill("input#password", password)
            self.page.click("button[type=submit]")
            
            time.sleep(8)
            
            current_url = self.page.url
            
            if "feed" in current_url or "/in/" in current_url:
                self.logged_in = True
                self.status_callback("✅ Logged in successfully!")
                
                # Save session for reuse
                storage_path = Path("data/linkedin") / username.replace('@', '_at_').replace('.', '_')
                storage_path.mkdir(parents=True, exist_ok=True)
                state_file = storage_path / "state.json"
                self.context.storage_state(path=str(state_file))
                self.status_callback("💾 Saved LinkedIn session for future reuse")
            else:
                self.logged_in = False
                self.status_callback(f"❌ Login failed. URL: {current_url}")
                self.status_callback("💡 Run locally with headless=False to complete verification")
        
        except Exception as e:
            self.logged_in = False
            self.status_callback(f"❌ Login error: {str(e)}")
            self.status_callback("💡 Use environment variable LINKEDIN_SESSION_PKSINGH210 to bypass login")
    
    def goto(self, url: str):
        """Navigate to URL."""
        if self.page:
            self.page.goto(url, timeout=60000)
        else:
            raise RuntimeError("Browser page not initialized. Call login() first.")
    
    def close(self):
        """Close browser and context."""
        try:
            if self.context:
                self.context.close()
            self.browser.close()
            self.playwright.stop()
        except Exception as e:
            self.status_callback(f"⚠️ Error closing browser: {e}")
    
    @property
    def cookies(self):
        """
        Get cookies as a dictionary suitable for requests library.
        Returns dict with cookie names as keys and values.
        """
        if not self.context:
            return {}
        
        pw_cookies = self.context.cookies()
        
        cookie_dict = {
            cookie['name']: cookie['value'] 
            for cookie in pw_cookies 
            if 'linkedin.com' in cookie.get('domain', '')
        }
        
        return cookie_dict
