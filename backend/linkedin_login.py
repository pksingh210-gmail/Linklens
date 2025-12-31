# backend/linkedin_login.py
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

class LinkedInLogin:
    def __init__(self, headless: bool = True, status_callback=None):
        self.headless = headless
        self.status_callback = status_callback or (lambda msg: None)
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.logged_in = False
    
    def _start_browser(self):
        """Start Playwright browser with optimal settings."""
        if self.playwright:
            return
        
        self.playwright = sync_playwright().start()
        
        # Browser launch arguments for better compatibility
        launch_args = [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-blink-features=AutomationControlled',
            '--disable-features=IsolateOrigins,site-per-process',
            '--disable-web-security'
        ]
        
        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            args=launch_args,
            slow_mo=100  # Slow down operations for realism
        )
    
    def _init_context(self, username: str):
        """Initialize browser context with anti-detection."""
        self._start_browser()
        
        storage_path = Path("data/linkedin") / username.replace('@', '_at_').replace('.', '_')
        storage_path.mkdir(parents=True, exist_ok=True)
        state_file = storage_path / "state.json"
        
        self.status_callback(f"📁 Session storage: {state_file}")
        
        # Context configuration with anti-detection
        context_options = {
            'viewport': {'width': 1920, 'height': 1080},
            'user_agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            ),
            'locale': 'en-US',
            'timezone_id': 'America/New_York',
            'permissions': ['geolocation'],
            'geolocation': {'latitude': 40.7128, 'longitude': -74.0060},  # New York
            'color_scheme': 'light',
            'extra_http_headers': {
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
        }
        
        # Try to load existing session
        if state_file.exists() and state_file.stat().st_size > 100:
            try:
                self.status_callback(f"🔄 Loading saved session...")
                context_options['storage_state'] = str(state_file)
                self.context = self.browser.new_context(**context_options)
                self.page = self.context.new_page()
                
                # Anti-detection script
                self._inject_anti_detection()
                
                # Verify session
                self.page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
                time.sleep(3)
                
                if "feed" in self.page.url or "mynetwork" in self.page.url:
                    self.logged_in = True
                    self.status_callback("✅ Session restored successfully")
                    return
                else:
                    self.status_callback("⚠️ Session expired, re-authenticating...")
                    self.context.close()
            except Exception as e:
                self.status_callback(f"⚠️ Session restore failed: {str(e)[:50]}")
                if self.context:
                    self.context.close()
        
        # Create fresh context
        self.context = self.browser.new_context(**context_options)
        self.page = self.context.new_page()
        self._inject_anti_detection()
    
    def _inject_anti_detection(self):
        """Inject scripts to avoid bot detection."""
        self.page.add_init_script("""
            // Remove webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Mock plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // Mock languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
            
            // Chrome runtime
            window.chrome = {
                runtime: {}
            };
            
            // Permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
            );
        """)
    
    def login(self, username: str, password: str):
        """Login to LinkedIn with extended timeout and retry logic."""
        self._init_context(username)
        
        if self.logged_in:
            return
        
        self.status_callback(f"🔐 Attempting login as {username}")
        
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                self.status_callback(f"🔄 Login attempt {attempt}/{max_retries}")
                
                # Navigate to login page
                self.page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=60000)
                time.sleep(2)
                
                # Wait for form with extended timeout
                try:
                    self.page.wait_for_selector("input#username", state="visible", timeout=30000)
                except PlaywrightTimeoutError:
                    self.status_callback("⚠️ Login form not found, retrying...")
                    continue
                
                # Clear and type username slowly
                username_field = self.page.locator("input#username")
                username_field.click()
                time.sleep(0.3)
                username_field.fill("")
                time.sleep(0.5)
                username_field.type(username, delay=100)
                time.sleep(0.8)
                
                # Clear and type password slowly
                password_field = self.page.locator("input#password")
                password_field.click()
                time.sleep(0.3)
                password_field.fill("")
                time.sleep(0.5)
                password_field.type(password, delay=120)
                time.sleep(1)
                
                # Click submit button
                submit_button = self.page.locator("button[type='submit']")
                submit_button.click()
                
                # Wait for navigation with extended timeout
                self.status_callback("⏳ Waiting for LinkedIn response...")
                time.sleep(8)
                
                # Try to wait for network idle
                try:
                    self.page.wait_for_load_state("networkidle", timeout=45000)
                except PlaywrightTimeoutError:
                    self.status_callback("⚠️ Network still loading, continuing...")
                
                time.sleep(3)
                current_url = self.page.url
                self.status_callback(f"📍 Current URL: {current_url[:60]}...")
                
                # Check for various success indicators
                if any(x in current_url for x in ["feed", "mynetwork", "in/", "messaging"]):
                    self.logged_in = True
                    self.status_callback("✅ Login successful!")
                    
                    # Save session
                    storage_path = Path("data/linkedin") / username.replace('@', '_at_').replace('.', '_')
                    storage_path.mkdir(parents=True, exist_ok=True)
                    state_file = storage_path / "state.json"
                    self.context.storage_state(path=str(state_file))
                    self.status_callback(f"💾 Session saved to {state_file}")
                    return
                
                # Check for verification challenges
                elif any(x in current_url for x in ["checkpoint", "challenge", "add-phone", "uas/authenticate"]):
                    self.status_callback("🛑 LinkedIn requires verification!")
                    self.status_callback("⚠️ Please complete verification manually")
                    self.status_callback("💡 Options:")
                    self.status_callback("   1. Use local machine with headless=False")
                    self.status_callback("   2. Complete 2FA/phone verification")
                    self.status_callback("   3. Use a different LinkedIn account")
                    
                    # Wait up to 5 minutes for manual verification
                    self.status_callback("⏳ Waiting for manual verification (5 min timeout)...")
                    for i in range(60):
                        time.sleep(5)
                        current_url = self.page.url
                        if any(x in current_url for x in ["feed", "mynetwork", "in/"]):
                            self.logged_in = True
                            self.status_callback("✅ Verification completed!")
                            
                            # Save session after verification
                            storage_path = Path("data/linkedin") / username.replace('@', '_at_').replace('.', '_')
                            storage_path.mkdir(parents=True, exist_ok=True)
                            state_file = storage_path / "state.json"
                            self.context.storage_state(path=str(state_file))
                            self.status_callback(f"💾 Session saved")
                            return
                    
                    self.status_callback("❌ Verification timeout exceeded")
                    self.logged_in = False
                    return
                
                else:
                    self.status_callback(f"⚠️ Unexpected page: {current_url[:80]}")
                    if attempt < max_retries:
                        self.status_callback(f"🔄 Retrying in 3 seconds...")
                        time.sleep(3)
                        continue
                
            except PlaywrightTimeoutError as e:
                self.status_callback(f"⏱️ Timeout on attempt {attempt}: {str(e)[:60]}")
                if attempt < max_retries:
                    time.sleep(3)
                    continue
            except Exception as e:
                self.status_callback(f"❌ Error on attempt {attempt}: {str(e)[:80]}")
                if attempt < max_retries:
                    time.sleep(3)
                    continue
        
        # All attempts failed
        self.logged_in = False
        self.status_callback("❌ Login failed after all attempts")
        self.status_callback("💡 Suggestions:")
        self.status_callback("   1. Check credentials are correct")
        self.status_callback("   2. Try logging in manually first")
        self.status_callback("   3. Account may need verification")
    
    def goto(self, url: str):
        """Navigate to URL."""
        if self.page:
            self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
        else:
            raise RuntimeError("Browser not initialized")
    
    def close(self):
        """Close browser."""
        try:
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except Exception as e:
            if self.status_callback:
                self.status_callback(f"⚠️ Cleanup error: {e}")
    
    @property
    def cookies(self):
        """Get cookies for requests."""
        if not self.context:
            return {}
        
        pw_cookies = self.context.cookies()
        return {
            cookie['name']: cookie['value'] 
            for cookie in pw_cookies 
            if 'linkedin.com' in cookie.get('domain', '')
        }


