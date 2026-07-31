"""
Netflix Account Scraper - Extracts structured account info via Browserless V2 + Playwright.
Reads directly from Netflix ReactContext GraphQL model for 100% accuracy and speed.
"""
import os
import re
import json
from playwright.sync_api import sync_playwright

BROWSERLESS_TOKEN = os.environ.get("BROWSERLESS_TOKEN", "")

# Plan metadata mapping (Stream count & resolution)
PLAN_SPECS = {
    "4001": {"name": "Basic", "quality": "720p (HD)", "streams": 1},
    "4002": {"name": "Standard", "quality": "1080p (Full HD)", "streams": 2},
    "4003": {"name": "Premium", "quality": "4K (Ultra HD)", "streams": 4},
}

def mask_email(email):
    """Mask email for privacy e.g. andres7566@hotmail.com -> an***66@hotmail.com"""
    if not email or "@" not in email:
        return email
    name, domain = email.split("@", 1)
    if len(name) <= 2:
        masked_name = name[0] + "***"
    elif len(name) <= 4:
        masked_name = name[:1] + "***" + name[-1:]
    else:
        masked_name = name[:2] + "***" + name[-2:]
    return f"{masked_name}@{domain}"


def find_dict_by_substring(obj, target_substring):
    """Recursively find dictionary value whose key contains target_substring"""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if target_substring in k and isinstance(v, dict):
                return v
            elif isinstance(v, dict):
                found = find_dict_by_substring(v, target_substring)
                if found:
                    return found
    return None


def scrape_account_info(nftoken_link):
    """
    Scrape Netflix account info using Playwright + Browserless V2.
    
    Returns a dict:
    {
        "status": "active" | "on_hold" | "dead",
        "email": str or None,
        "masked_email": str or None,
        "country": str or None,
        "plan_name": str or None,
        "quality": str or None,
        "streams": int or None,
        "member_since": str or None,
        "next_billing": str or None,
        "payment_method": str or None,
        "profiles": list of str,
        "profile_count": int,
    }
    """
    if not BROWSERLESS_TOKEN:
        raise Exception("BROWSERLESS_TOKEN is not configured!")

    account_link = nftoken_link.replace('/browse?nftoken=', '/account?nftoken=')
    ws_url = f"wss://production-sfo.browserless.io/chrome/playwright?token={BROWSERLESS_TOKEN}"

    with sync_playwright() as pw:
        browser = None
        try:
            browser = pw.chromium.connect(ws_url)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 900}
            )
            page = context.new_page()
            page.set_default_timeout(30000)

            page.goto(account_link, wait_until="domcontentloaded")
            page.wait_for_timeout(4000)

            current_url = page.url.lower()
            if "login" in current_url or "clearcookies" in current_url:
                return {"status": "dead"}

            # Check for On-Hold status
            is_on_hold = page.evaluate('''() => {
                const banner = document.querySelector('div[data-uia="dark-background-banner"]');
                const updateBtn = document.querySelector('[data-uia="UPDATE_PAYMENT_METHOD"]');
                return banner !== null || updateBtn !== null;
            }''')

            if is_on_hold:
                return {"status": "on_hold"}

            # Extract GraphQL model data directly from window.netflix
            graphql_data = page.evaluate('''() => {
                try {
                    const str = window.netflix.reactContext.models.graphql;
                    return typeof str === 'string' ? JSON.parse(str) : str;
                } catch (e) {
                    return null;
                }
            }''')

            res = {
                "status": "active",
                "email": None,
                "masked_email": None,
                "country": None,
                "plan_name": None,
                "quality": None,
                "streams": None,
                "member_since": None,
                "next_billing": None,
                "payment_method": None,
                "profiles": [],
                "profile_count": 0,
            }

            if graphql_data and "data" in graphql_data:
                gdata = graphql_data["data"]

                # 1. Parse Profiles & Email
                profile_names = []
                primary_email = None

                for key, val in gdata.items():
                    if key.startswith("Profile:"):
                        if isinstance(val, dict) and "name" in val:
                            profile_names.append(val["name"])
                        if isinstance(val, dict) and "growthEmail" in val:
                            g_email = val["growthEmail"]
                            if isinstance(g_email, dict) and g_email.get("email"):
                                email_val = g_email["email"]
                                if isinstance(email_val, dict) and "value" in email_val:
                                    primary_email = email_val["value"]

                res["profiles"] = profile_names
                res["profile_count"] = len(profile_names)
                if primary_email:
                    res["email"] = primary_email
                    res["masked_email"] = mask_email(primary_email)

                # 2. Parse GrowthAccount info recursively
                growth_acc = find_dict_by_substring(gdata, "growthAccount")
                if growth_acc:
                    # Country
                    country_obj = growth_acc.get("countryOfSignUp")
                    if isinstance(country_obj, dict):
                        res["country"] = country_obj.get("code")

                    # Member since
                    m_since = growth_acc.get("memberSince")
                    if m_since and isinstance(m_since, str):
                        res["member_since"] = m_since.split("T")[0]

                    # Next billing
                    nb_date = growth_acc.get("nextBillingDate")
                    if isinstance(nb_date, dict):
                        res["next_billing"] = nb_date.get("localDate", "").split("T")[0]

                    # Plan info
                    curr_plan = growth_acc.get("currentPlan")
                    if isinstance(curr_plan, dict) and "plan" in curr_plan:
                        plan_obj = curr_plan["plan"]
                        res["plan_name"] = plan_obj.get("name")
                        plan_id = str(plan_obj.get("planId", ""))
                        if plan_id in PLAN_SPECS:
                            res["quality"] = PLAN_SPECS[plan_id]["quality"]
                            res["streams"] = PLAN_SPECS[plan_id]["streams"]
                            if not res["plan_name"]:
                                res["plan_name"] = PLAN_SPECS[plan_id]["name"]

                    # Payment methods
                    pay_methods = growth_acc.get("growthPaymentMethods")
                    if isinstance(pay_methods, list) and len(pay_methods) > 0:
                        pm = pay_methods[0]
                        if isinstance(pm, dict):
                            brand = ""
                            if isinstance(pm.get("paymentOptionLogo"), dict):
                                brand = pm["paymentOptionLogo"].get("paymentOptionLogo", "")
                            card_num = pm.get("displayText", "")
                            res["payment_method"] = f"{brand} •••• {card_num}".strip()

            # Fallback for streams/quality if plan_name is known but planId was not mapped
            if res["plan_name"] and not res["quality"]:
                p_lower = res["plan_name"].lower()
                if "premium" in p_lower:
                    res["quality"] = "4K (Ultra HD)"
                    res["streams"] = 4
                elif "estándar" in p_lower or "standard" in p_lower:
                    res["quality"] = "1080p (Full HD)"
                    res["streams"] = 2
                elif "básico" in p_lower or "basic" in p_lower:
                    res["quality"] = "720p (HD)"
                    res["streams"] = 1

            return res

        finally:
            if browser:
                try:
                    browser.close()
                except Exception:
                    pass


def format_account_info(info):
    """Formats scraped account dict into neat Telegram markdown text."""
    if info.get("status") == "dead":
        return "❌ Tài khoản đã bị đứt (Dead)."
    if info.get("status") == "on_hold":
        return "⚠️ Tài khoản bị tạm ngưng thanh toán (On-Hold)."

    profiles_str = ", ".join(info.get("profiles", [])) or "None"
    
    lines = [
        f"👤 Profile: {profiles_str}",
        f"🌐 Quốc gia: {info.get('country') or 'N/A'}",
        f"📋 Gói: {info.get('plan_name') or 'N/A'}",
        f"📨 Email: {info.get('masked_email') or 'N/A'}",
        f"📅 Thành viên từ: {info.get('member_since') or 'N/A'}",
        f"🎬 Streams: {info.get('streams') or 'N/A'} | Chất lượng: {info.get('quality') or 'N/A'}",
    ]
    if info.get("next_billing"):
        lines.append(f"💳 Hạn thanh toán: {info['next_billing']}")
    if info.get("payment_method"):
        lines.append(f"💳 Thẻ thanh toán: {info['payment_method']}")

    return "\n".join(lines)
