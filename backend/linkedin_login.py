# linkedin_login_enhanced.py
import time
import random
from pathlib import Path
from playwright.sync_api import sync_playwright

class LinkedInLogin:
    def __init__(self, headless: bool = True, status_callback=None, proxy: dict = None):
        self.headless = headless
        self.status_callback = status_callback or (lambda msg: None)
        self.proxy = proxy
        self.playwright = sync_playwright().start()
        
        # Launch with stealth settings
        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-gpu'
            ]
        )
        self.context = None
        self.page = None
        self.logged_in = False
    
    def _init_context(self, username: str):
        storage_path = Path("data/linkedin") / username
        storage_path.mkdir(parents=True, exist_ok=True)
        state_file = storage_path / "state.json"
        
        # Realistic browser context configuration
        context_options = {
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'viewport': {'width': 1920, 'height': 1080},
            'locale': 'en-US',
            'timezone_id': 'America/New_York',
            'permissions': ['geolocation'],
            'geolocation': {'latitude': 40.7128, 'longitude': -74.0060},  # NYC
            'extra_http_headers': {
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1'
            }
        }
        
        # Add proxy if provided
        if self.proxy:
            context_options['proxy'] = {
                'server': self.proxy['server'],
                'username': self.proxy.get('username'),
                'password': self.proxy.get('password')
            }
        
        # Load saved session if exists
        if state_file.exists():
            time.sleep(random.uniform(1, 2))
            self.status_callback(f"🔄 Loading existing LinkedIn session for {username}")
            context_options['storage_state'] = str(state_file)
        
        self.context = self.browser.new_context(**context_options)
        self.page = self.context.new_page()
        
        # Inject anti-detection scripts
        self._inject_stealth_scripts()
        
        # Check if saved session is valid
        if state_file.exists():
            self.page.goto("https://www.linkedin.com/feed/", wait_until='networkidle')
            time.sleep(random.uniform(2, 4))
            
            if "feed" in self.page.url or "/in/" in self.page.url:
                self.logged_in = True
                return
    
    def _inject_stealth_scripts(self):
        """Inject JavaScript to mask automation detection"""
        self.page.add_init_script("""
            // Overwrite the `navigator.webdriver` property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Mock chrome object
            window.navigator.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };
            
            // Mock plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // Mock languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
            
            // Mock platform
            Object.defineProperty(navigator, 'platform', {
                get: () => 'Win32'
            });
            
            // Mock permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            
            // Hide automation
            delete navigator.__proto__.webdriver;
        """)
    
    def _human_type(self, selector: str, text: str):
        """Type text with human-like delays"""
        self.page.click(selector)
        for char in text:
            self.page.keyboard.type(char)
            time.sleep(random.uniform(0.05, 0.15))
    
    def _human_mouse_move(self):
        """Simulate random mouse movement"""
        x = random.randint(100, 500)
        y = random.randint(100, 500)
        self.page.mouse.move(x, y)
        time.sleep(random.uniform(0.1, 0.3))
    
    def login(self, username: str, password: str):
        self._init_context(username)
        
        if self.logged_in:
            return
        
        self.status_callback(f"🔐 Logging in as {username}")
        
        # Go to login page
        self.page.goto("https://www.linkedin.com/login", wait_until='networkidle')
        time.sleep(random.uniform(2, 4))
        
        # Human-like interaction
        self._human_mouse_move()
        time.sleep(random.uniform(0.5, 1))
        
        # Fill username with human typing
        self._human_type("input#username", username)
        time.sleep(random.uniform(0.8, 1.5))
        
        # Fill password with human typing
        self._human_type("input#password", password)
        time.sleep(random.uniform(0.8, 1.5))
        
        # Random mouse movement before submit
        self._human_mouse_move()
        time.sleep(random.uniform(0.5, 1))
        
        # Click submit button
        self.page.click("button[type=submit]")
        time.sleep(random.uniform(5, 8))
        
        # Check login status
        current_url = self.page.url
        if "feed" in current_url or "/in/" in current_url:
            self.logged_in = True
            self.status_callback("✅ Logged in successfully!")
            
            # Save session for reuse
            storage_path = Path("data/linkedin") / username
            state_file = storage_path / "state.json"
            self.context.storage_state(path=str(state_file))
            self.status_callback("💾 Saved LinkedIn session for future reuse")
        elif "checkpoint" in current_url or "challenge" in current_url:
            self.logged_in = False
            self.status_callback(f"⚠️ Security challenge detected! Manual verification needed.")
            self.status_callback(f"URL: {current_url}")
            # Wait for manual intervention
            time.sleep(60)
        else:
            self.logged_in = False
            self.status_callback(f"❌ Login failed. URL: {current_url}")
    
    def goto(self, url: str):
        if self.page:
            self.page.goto(url, wait_until='networkidle')
            time.sleep(random.uniform(1, 2))
        else:
            raise RuntimeError("Browser page not initialized. Call login() first.")
    
    def close(self):
        try:
            if self.context:
                self.context.close()
            self.browser.close()
            self.playwright.stop()
        except Exception as e:
            self.status_callback(f"⚠️ Error closing browser: {e}")
    
    @property
    def cookies(self):
        """Get cookies as a dictionary suitable for requests library"""
        if not self.context:
            return {}
        
        pw_cookies = self.context.cookies()
        
        cookie_dict = {
            cookie['name']: cookie['value'] 
            for cookie in pw_cookies 
            if 'linkedin.com' in cookie.get('domain', '')
        }
        
        return cookie_dict


# Usage example with proxy
if __name__ == "__main__":
    # Optional: Configure residential proxy
    proxy_config = {
        'server': 'http://your-proxy-server:port',
        'username': 'your-proxy-username',
        'password': 'your-proxy-password'
    }
    
    def status_print(msg):
        print(msg)
    
    # Initialize with proxy (or None for no proxy)
    linkedin = LinkedInLogin(
        headless=False, 
        status_callback=status_print,
        proxy=proxy_config  # or None
    )
    
    try:
        linkedin.login("your-email@example.com", "your-password")
        
        if linkedin.logged_in:
            linkedin.goto("https://www.linkedin.com/in/some-profile/")
            time.sleep(5)
    finally:
        linkedin.close()



