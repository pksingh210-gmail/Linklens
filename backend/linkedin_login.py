# backend/linkedin_login.py
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

class LinkedInLogin:
    def __init__(self, headless: bool = True, status_callback=None):
        self.headless = headless
        self.status_callback = status_callback or (lambda msg: None)
        self.playwright = sync_playwright().start()
        
        # Launch browser with anti-detection settings
        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled'
            ]
        )
        self.context = None
        self.page = None
        self.logged_in = False
    
    def _init_context(self, username: str):
        """Initialize browser context with user session."""
        storage_path = Path("data/linkedin") / username
        storage_path.mkdir(parents=True, exist_ok=True)
        state_file = storage_path / "state.json"
        
        # Anti-detection: realistic viewport and user agent
        viewport = {'width': 1920, 'height': 1080}
        user_agent = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        )
        
        # Try to load saved session
        if state_file.exists():
            self.status_callback(f"🔄 Loading existing session for {username}")
            try:
                self.context = self.browser.new_context(
                    storage_state=str(state_file),
                    viewport=viewport,
                    user_agent=user_agent
                )
                self.page = self.context.new_page()
                
                # Verify session is still valid
                self.page.goto("https://www.linkedin.com/feed/", timeout=30000)
                time.sleep(3)
                
                if "feed" in self.page.url or "/in/" in self.page.url:
                    self.logged_in = True
                    self.status_callback("✅ Reused saved session")
                    return
                else:
                    self.status_callback("⚠️ Session expired, logging in fresh...")
            except Exception as e:
                self.status_callback(f"⚠️ Failed to load session: {str(e)[:50]}")
        
        # Create fresh context with anti-detection
        self.context = self.browser.new_context(
            viewport=viewport,
            user_agent=user_agent,
            locale='en-US',
            timezone_id='America/New_York'
        )
        
        # Remove webdriver detection
        self.page = self.context.new_page()
        self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
    
    def login(self, username: str, password: str):
        """Perform LinkedIn login with retry logic."""
        self._init_context(username)
        
        if self.logged_in:
            return
        
        self.status_callback(f"🔐 Logging in as {username}")
        
        try:
            # Navigate to login page
            self.page.goto("https://www.linkedin.com/login", timeout=60000)
            time.sleep(2)
            
            # Wait for login form to be visible
            self.page.wait_for_selector("input#username", timeout=30000)
            
            # Human-like typing with delays
            self.page.fill("input#username", "")
            time.sleep(0.5)
            self.page.type("input#username", username, delay=100)
            time.sleep(0.5)
            
            self.page.fill("input#password", "")
            time.sleep(0.5)
            self.page.type("input#password", password, delay=120)
            time.sleep(1)
            
            # Click login button
            self.page.click("button[type=submit]")
            
            # Wait for navigation (increased timeout)
            self.page.wait_for_load_state("networkidle", timeout=60000)
            time.sleep(5)
            
            current_url = self.page.url
            
            # Check for CAPTCHA or verification
            if "checkpoint" in current_url or "challenge" in current_url:
                self.status_callback("⚠️ LinkedIn requires verification (CAPTCHA/2FA)")
                self.status_callback("🛑 Please verify manually in the browser window")
                
                # Wait for manual verification (5 minutes)
                for i in range(60):
                    time.sleep(5)
                    current_url = self.page.url
                    if "feed" in current_url or "/in/" in current_url:
                        break
                    if i % 6 == 0:  # Every 30 seconds
                        self.status_callback(f"⏳ Waiting for verification... ({i*5}s)")
            
            # Check if login successful
            if "feed" in current_url or "/in/" in current_url:
                self.logged_in = True
                self.status_callback("✅ Logged in successfully!")
                
                # Save session for reuse
                storage_path = Path("data/linkedin") / username
                storage_path.mkdir(parents=True, exist_ok=True)
                state_file = storage_path / "state.json"
                self.context.storage_state(path=str(state_file))
                self.status_callback("💾 Session saved for future use")
            else:
                self.logged_in = False
                self.status_callback(f"❌ Login failed. Current URL: {current_url}")
                
        except Exception as e:
            self.logged_in = False
            self.status_callback(f"❌ Login error: {str(e)}")
    
    def goto(self, url: str):
        """Navigate to a URL."""
        if self.page:
            self.page.goto(url, timeout=60000)
        else:
            raise RuntimeError("Browser page not initialized. Call login() first.")
    
    def close(self):
        """Close browser and cleanup."""
        try:
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except Exception as e:
            self.status_callback(f"⚠️ Error closing browser: {e}")
    
    @property
    def cookies(self):
        """Get cookies as a dictionary for requests library."""
        if not self.context:
            return {}
        
        pw_cookies = self.context.cookies()
        
        cookie_dict = {
            cookie['name']: cookie['value'] 
            for cookie in pw_cookies 
            if 'linkedin.com' in cookie.get('domain', '')
        } 
        return cookie_dict

