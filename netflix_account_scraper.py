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

# Country code -> Full name (Netflix supported regions)
COUNTRY_NAMES = {
    "AF": "Afghanistan", "AL": "Albania", "DZ": "Algeria", "AD": "Andorra",
    "AO": "Angola", "AG": "Antigua & Barbuda", "AR": "Argentina", "AM": "Armenia",
    "AU": "Australia", "AT": "Austria", "AZ": "Azerbaijan", "BS": "Bahamas",
    "BH": "Bahrain", "BD": "Bangladesh", "BB": "Barbados", "BY": "Belarus",
    "BE": "Belgium", "BZ": "Belize", "BJ": "Benin", "BT": "Bhutan",
    "BO": "Bolivia", "BA": "Bosnia & Herzegovina", "BW": "Botswana", "BR": "Brazil",
    "BN": "Brunei", "BG": "Bulgaria", "BF": "Burkina Faso", "BI": "Burundi",
    "KH": "Cambodia", "CM": "Cameroon", "CA": "Canada", "CV": "Cape Verde",
    "CF": "Central African Republic", "TD": "Chad", "CL": "Chile", "CN": "China",
    "CO": "Colombia", "KM": "Comoros", "CG": "Congo", "CD": "DR Congo",
    "CR": "Costa Rica", "CI": "Ivory Coast", "HR": "Croatia", "CU": "Cuba",
    "CY": "Cyprus", "CZ": "Czech Republic", "DK": "Denmark", "DJ": "Djibouti",
    "DM": "Dominica", "DO": "Dominican Republic", "EC": "Ecuador", "EG": "Egypt",
    "SV": "El Salvador", "GQ": "Equatorial Guinea", "ER": "Eritrea", "EE": "Estonia",
    "SZ": "Eswatini", "ET": "Ethiopia", "FJ": "Fiji", "FI": "Finland",
    "FR": "France", "GA": "Gabon", "GM": "Gambia", "GE": "Georgia",
    "DE": "Germany", "GH": "Ghana", "GR": "Greece", "GD": "Grenada",
    "GT": "Guatemala", "GN": "Guinea", "GW": "Guinea-Bissau", "GY": "Guyana",
    "HT": "Haiti", "HN": "Honduras", "HK": "Hong Kong", "HU": "Hungary",
    "IS": "Iceland", "IN": "India", "ID": "Indonesia", "IR": "Iran",
    "IQ": "Iraq", "IE": "Ireland", "IL": "Israel", "IT": "Italy",
    "JM": "Jamaica", "JP": "Japan", "JO": "Jordan", "KZ": "Kazakhstan",
    "KE": "Kenya", "KI": "Kiribati", "KP": "North Korea", "KR": "South Korea",
    "KW": "Kuwait", "KG": "Kyrgyzstan", "LA": "Laos", "LV": "Latvia",
    "LB": "Lebanon", "LS": "Lesotho", "LR": "Liberia", "LY": "Libya",
    "LI": "Liechtenstein", "LT": "Lithuania", "LU": "Luxembourg", "MO": "Macao",
    "MG": "Madagascar", "MW": "Malawi", "MY": "Malaysia", "MV": "Maldives",
    "ML": "Mali", "MT": "Malta", "MH": "Marshall Islands", "MR": "Mauritania",
    "MU": "Mauritius", "MX": "Mexico", "FM": "Micronesia", "MD": "Moldova",
    "MC": "Monaco", "MN": "Mongolia", "ME": "Montenegro", "MA": "Morocco",
    "MZ": "Mozambique", "MM": "Myanmar", "NA": "Namibia", "NR": "Nauru",
    "NP": "Nepal", "NL": "Netherlands", "NZ": "New Zealand", "NI": "Nicaragua",
    "NE": "Niger", "NG": "Nigeria", "MK": "North Macedonia", "NO": "Norway",
    "OM": "Oman", "PK": "Pakistan", "PW": "Palau", "PS": "Palestine",
    "PA": "Panama", "PG": "Papua New Guinea", "PY": "Paraguay", "PE": "Peru",
    "PH": "Philippines", "PL": "Poland", "PT": "Portugal", "QA": "Qatar",
    "RO": "Romania", "RU": "Russia", "RW": "Rwanda", "KN": "Saint Kitts & Nevis",
    "LC": "Saint Lucia", "VC": "Saint Vincent", "WS": "Samoa", "SM": "San Marino",
    "ST": "São Tomé & Príncipe", "SA": "Saudi Arabia", "SN": "Senegal",
    "RS": "Serbia", "SC": "Seychelles", "SL": "Sierra Leone", "SG": "Singapore",
    "SK": "Slovakia", "SI": "Slovenia", "SB": "Solomon Islands", "SO": "Somalia",
    "ZA": "South Africa", "SS": "South Sudan", "ES": "Spain", "LK": "Sri Lanka",
    "SD": "Sudan", "SR": "Suriname", "SE": "Sweden", "CH": "Switzerland",
    "SY": "Syria", "TW": "Taiwan", "TJ": "Tajikistan", "TZ": "Tanzania",
    "TH": "Thailand", "TL": "Timor-Leste", "TG": "Togo", "TO": "Tonga",
    "TT": "Trinidad & Tobago", "TN": "Tunisia", "TR": "Turkey", "TM": "Turkmenistan",
    "TV": "Tuvalu", "UG": "Uganda", "UA": "Ukraine", "AE": "UAE",
    "GB": "United Kingdom", "US": "United States", "UY": "Uruguay",
    "UZ": "Uzbekistan", "VU": "Vanuatu", "VA": "Vatican City", "VE": "Venezuela",
    "VN": "Vietnam", "YE": "Yemen", "ZM": "Zambia", "ZW": "Zimbabwe",
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


def escape_md(text):
    """Escape Telegram Markdown V1 special characters in text values."""
    if not text:
        return text
    for ch in ['*', '_', '`', '[', ']', '(', ')']:
        text = text.replace(ch, '\\' + ch)
    return text


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

    # Ensure link uses /browse for on-hold check
    browse_link = nftoken_link
    if '/account?nftoken=' in browse_link:
        browse_link = browse_link.replace('/account?nftoken=', '/browse?nftoken=')
    
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

            # === STEP 1: Open /browse to check on-hold & dead ===
            page.goto(browse_link, wait_until="domcontentloaded")
            page.wait_for_timeout(5000)

            current_url = page.url.lower()
            if "login" in current_url or "clearcookies" in current_url:
                return {"status": "dead"}

            # Check for On-Hold status on browse page (Netflix V2 selectors)
            is_on_hold = page.evaluate('''() => {
                // New Netflix V2 on-hold banner
                const storyBanner = document.querySelector('[data-uia="our-story-card-banner"]');
                const storyCta = document.querySelector('[data-uia="our-story-card-cta"]');
                // Old selectors (keep as fallback)
                const darkBanner = document.querySelector('div[data-uia="dark-background-banner"]');
                const updateBtn = document.querySelector('[data-uia="UPDATE_PAYMENT_METHOD"]');
                // Text-based detection
                const body = document.body.innerText.toLowerCase();
                const hasHoldText = body.includes('on hold') || body.includes('account is on hold');
                
                return storyBanner !== null || storyCta !== null || 
                       darkBanner !== null || updateBtn !== null || hasHoldText;
            }''')

            if is_on_hold:
                return {"status": "on_hold"}

            # === STEP 2: Navigate to /account to scrape info via GraphQL ===
            # NOTE: On-hold accounts still load /browse normally (profile gate),
            # so the reliable on-hold signal only appears here on /account.
            page.goto("https://www.netflix.com/account", wait_until="domcontentloaded")
            page.wait_for_timeout(5000)

            current_url = page.url.lower()
            if "login" in current_url or "clearcookies" in current_url:
                return {"status": "dead"}

            # Extract GraphQL model data directly from window.netflix
            graphql_data = page.evaluate('''() => {
                try {
                    const str = window.netflix.reactContext.models.graphql;
                    return typeof str === 'string' ? JSON.parse(str) : str;
                } catch (e) {
                    return null;
                }
            }''')

            # === RELIABLE ON-HOLD DETECTION (on /account) ===
            # 1) Primary: GraphQL growthHoldMetadata.isUserOnHold (100% accurate).
            #    membershipStatus stays "CURRENT_MEMBER" even when on-hold, so we
            #    must NOT rely on it — only isUserOnHold is authoritative.
            graphql_on_hold = False
            if graphql_data and "data" in graphql_data:
                ga = find_dict_by_substring(graphql_data["data"], "growthAccount")
                if ga:
                    hold_meta = ga.get("growthHoldMetadata")
                    if isinstance(hold_meta, dict) and hold_meta.get("isUserOnHold") is True:
                        graphql_on_hold = True

            # 2) Fallback: DOM signals on /account. The account page renders in the
            #    account's own country language (ES/PT/AR/HI/TH/...), so we must NOT
            #    depend on English text. Primary DOM signal is the data-uia code
            #    identifier (never translated); a multilingual keyword net is only a
            #    last-resort safety layer.
            account_dom_on_hold = page.evaluate('''() => {
                // Language-independent: data-uia is a code identifier, same in every locale.
                if (document.querySelector('[data-uia="UPDATE_PAYMENT_METHOD"]') !== null) return true;

                // Best-effort multilingual text net (major Netflix regions).
                const body = (document.body ? document.body.innerText : '').toLowerCase();
                const kw = [
                    'unable to process your last payment',        // EN
                    'update your payment information',            // EN
                    'cannot process your payment',                // EN
                    'no pudimos procesar',                        // ES
                    'actualiza tu informaci\\u00f3n de pago',       // ES
                    'no se pudo procesar tu pago',                // ES
                    'n\\u00e3o foi poss\\u00edvel processar',         // PT
                    'atualize suas informa\\u00e7\\u00f5es de pagamento', // PT
                    'impossible de traiter',                      // FR
                    'mettez \\u00e0 jour vos informations de paiement',  // FR
                    'zahlung konnte nicht',                       // DE
                    'aktualisiere deine zahlungs',                // DE
                ];
                return kw.some(k => body.includes(k));
            }''')

            if graphql_on_hold or account_dom_on_hold:
                return {"status": "on_hold"}

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
                        code = country_obj.get("code", "")
                        res["country"] = COUNTRY_NAMES.get(code, code)

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


def format_account_info(info, lang="vi"):
    """Formats scraped account dict into neat Telegram markdown text."""
    if info.get("status") == "dead":
        return "❌ Tài khoản đã bị đứt (Dead)." if lang == "vi" else "❌ Account is dead."
    if info.get("status") == "on_hold":
        return "⚠️ Tài khoản bị tạm ngưng thanh toán (On-Hold)." if lang == "vi" else "⚠️ Account is on-hold."

    # Escape markdown-sensitive values
    profiles_str = ", ".join(escape_md(p) for p in info.get("profiles", [])) or "N/A"
    payment = info.get("payment_method")
    plan_name = escape_md(info.get('plan_name') or 'N/A')
    country = escape_md(info.get('country') or 'N/A')
    quality = escape_md(info.get('quality') or 'N/A')
    
    if lang == "en":
        lines = [
            f"👤 *Profiles:* {profiles_str}",
            f"🌐 *Country:* {country}",
            f"📋 *Plan:* {plan_name}",
            f"📨 *Email:* `{info.get('masked_email') or 'N/A'}`",
            f"📅 *Member Since:* {info.get('member_since') or 'N/A'}",
            f"🎬 *Streams:* {info.get('streams') or 'N/A'} | *Quality:* {quality}",
        ]
        if info.get("next_billing"):
            lines.append(f"💳 *Next Payment:* {info['next_billing']}")
        if payment:
            lines.append(f"💳 *Payment Method:* `{payment}`")
    else:
        lines = [
            f"👤 *Profiles:* {profiles_str}",
            f"🌐 *Quốc gia:* {country}",
            f"📋 *Gói:* {plan_name}",
            f"📨 *Email:* `{info.get('masked_email') or 'N/A'}`",
            f"📅 *Thành viên từ:* {info.get('member_since') or 'N/A'}",
            f"🎬 *Streams:* {info.get('streams') or 'N/A'} | *Chất lượng:* {quality}",
        ]
        if info.get("next_billing"):
            lines.append(f"💳 *Hạn thanh toán:* {info['next_billing']}")
        if payment:
            lines.append(f"💳 *Thẻ thanh toán:* `{payment}`")

    return "\n".join(lines)
