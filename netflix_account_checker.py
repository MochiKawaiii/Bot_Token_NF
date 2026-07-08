import os
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

BROWSERLESS_TOKEN = os.environ.get("BROWSERLESS_TOKEN", "")

# Browserless V2 endpoint (WebSocket)
BROWSERLESS_WS = f"wss://production-sfo.browserless.io/chrome/playwright?token={BROWSERLESS_TOKEN}"


def check_account_status(link):
    """
    Checks if a Netflix account is active, dead, or on-hold via Browserless using the nftoken link.
    Returns: "active", "on_hold", or "dead"
    """
    if not BROWSERLESS_TOKEN:
        raise Exception("BROWSERLESS_TOKEN is not configured!")
    
    # Change /browse to /account to go directly to the account page where the banner is
    test_link = link.replace('/browse?nftoken=', '/account?nftoken=')
    
    with sync_playwright() as pw:
        browser = None
        try:
            # === Connect to Browserless remote Chrome (V2) ===
            browser = pw.chromium.connect(BROWSERLESS_WS)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 720}
            )
            page = context.new_page()
            page.set_default_timeout(30000)
            
            # 1. Visit the account link with nftoken
            page.goto(test_link, wait_until="domcontentloaded")
            page.wait_for_timeout(4000)
            
            current_url = page.url.lower()
            
            # If redirected to login, cookie is dead
            if "login" in current_url or "clearcookies" in current_url:
                return "dead"
                
            # 2. Check for the on-hold banner or update payment button
            is_on_hold = page.evaluate('''() => {
                const banner = document.querySelector('div[data-uia="dark-background-banner"]');
                const updateBtn = document.querySelector('[data-uia="UPDATE_PAYMENT_METHOD"]');
                return banner !== null || updateBtn !== null;
            }''')
            
            if is_on_hold:
                return "on_hold"
                
            return "active"

        except Exception as e:
            # If network error or timeout occurs, throw it so the caller can handle it
            raise e
        finally:
            if browser:
                try:
                    browser.close()
                except Exception:
                    pass
