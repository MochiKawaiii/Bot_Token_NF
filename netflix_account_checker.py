import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException

BROWSERLESS_TOKEN = os.environ.get("BROWSERLESS_TOKEN", "")

def check_account_status(cookie_dict):
    """
    Checks if a Netflix account is active, dead, or on-hold via Browserless.
    Returns: "active", "on_hold", or "dead"
    """
    if not BROWSERLESS_TOKEN:
        raise Exception("BROWSERLESS_TOKEN is not configured!")
    
    driver = None
    try:
        # === Connect to Browserless remote Chrome ===
        opts = Options()
        opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--disable-extensions")
        opts.add_argument("--window-size=1280,720")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
        
        # Disable images for speed
        prefs = {"profile.managed_default_content_settings.images": 2}
        opts.add_experimental_option("prefs", prefs)
        
        opts.set_capability("browserless:token", BROWSERLESS_TOKEN)
        
        driver = webdriver.Remote(
            command_executor="https://chrome.browserless.io/webdriver",
            options=opts
        )
        driver.set_page_load_timeout(30)
        driver.set_script_timeout(15)
        
        # 1. Inject Cookies
        driver.get("https://www.netflix.com/browse")
        time.sleep(1)
        
        nf_id = cookie_dict.get("NetflixId") or cookie_dict.get("netflix_id", "")
        sec_id = cookie_dict.get("SecureNetflixId") or cookie_dict.get("secure_netflix_id", "")
        
        if nf_id:
            driver.add_cookie({"name": "NetflixId", "value": nf_id, "domain": ".netflix.com", "path": "/"})
        if sec_id:
            driver.add_cookie({"name": "SecureNetflixId", "value": sec_id, "domain": ".netflix.com", "path": "/"})
        
        # 2. Check /browse behavior (as requested by user)
        driver.get("https://www.netflix.com/browse")
        time.sleep(2)
        
        # 3. Go to /account to definitively check for the on-hold banner
        driver.get("https://www.netflix.com/account")
        time.sleep(2)
        
        current_url = driver.current_url.lower()
        
        # If redirected to login, cookie is dead
        if "login" in current_url or "clearcookies" in current_url:
            return "dead"
            
        # Execute JS to find the dark-background-banner reliably (language independent)
        # This banner is displayed on the /account page when the account is on-hold.
        is_on_hold = driver.execute_script("""
            const banner = document.querySelector('div[data-uia="dark-background-banner"]');
            return banner !== null;
        """)
        
        if is_on_hold:
            return "on_hold"
            
        return "active"

    except Exception as e:
        # If network error or timeout occurs, throw it so the caller can handle it
        raise e
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
