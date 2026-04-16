"""
Netflix Cookie -> NFToken Login Link Generator
Uses Netflix iOS API to generate nftoken from cookies.
"""
import json
import os
import re
import sys
import urllib.parse
from datetime import datetime

import requests
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# Netflix iOS API endpoint
API_URL = "https://ios.prod.ftl.netflix.com/iosui/user/15.48"

# Query parameters to mimic iOS Netflix app
QUERY_PARAMS = {
    "appVersion": "15.48.1",
    "config": json.dumps({
        "gamesInTrailersEnabled": "false",
        "isTrailersEvidenceEnabled": "false",
        "cdsMyListSortEnabled": "true",
        "kidsBillboardEnabled": "true",
        "addHorizontalBoxArtToVideoSummariesEnabled": "false",
        "skOverlayTestEnabled": "false",
        "homeFeedTestTVMovieListsEnabled": "false",
        "baselineOnIpadEnabled": "true",
        "trailersVideoIdLoggingFixEnabled": "true",
        "postPlayPreviewsEnabled": "false",
        "bypassContextualAssetsEnabled": "false",
        "roarEnabled": "false",
        "useSeason1AltLabelEnabled": "false",
        "disableCDSSearchPaginationSectionKinds": ["searchVideoCarousel"],
        "cdsSearchHorizontalPaginationEnabled": "true",
        "searchPreQueryGamesEnabled": "true",
        "kidsMyListEnabled": "true",
        "billboardEnabled": "true",
        "useCDSGalleryEnabled": "true",
        "contentWarningEnabled": "true",
        "videosInPopularGamesEnabled": "true",
        "avifFormatEnabled": "false",
        "sharksEnabled": "true",
    }),
    "device_type": "NFAPPL-02-",
    "esn": "NFAPPL-02-IPHONE8%3D1-PXA-02026U9VV5O8AUKEAEO8PUJETCGDD4PQRI9DEB3MDLEMD0EACM4CS78LMD334MN3MQ3NMJ8SU9O9MVGS6BJCURM1PH1MUTGDPF4S4200",
    "idiom": "phone",
    "iosVersion": "15.8.5",
    "isTablet": "false",
    "languages": "en-US",
    "locale": "en-US",
    "maxDeviceWidth": "375",
    "model": "saget",
    "modelType": "IPHONE8-1",
    "odpAware": "true",
    "path": '["account","token","default"]',
    "pathFormat": "graph",
    "pixelDensity": "2.0",
    "progressive": "false",
    "responseFormat": "json",
}

# Headers to mimic Netflix iOS app (Argo client)
BASE_HEADERS = {
    "User-Agent": "Argo/15.48.1 (iPhone; iOS 15.8.5; Scale/2.00)",
    "x-netflix.request.attempt": "1",
    "x-netflix.request.client.user.guid": "A4CS633D7VCBPE2GPK2HL4EKOE",
    "x-netflix.context.profile-guid": "A4CS633D7VCBPE2GPK2HL4EKOE",
    "x-netflix.request.routing": '{"path":"/nq/mobile/nqios/~15.48.0/user","control_tag":"iosui_argo"}',
    "x-netflix.context.app-version": "15.48.1",
    "x-netflix.argo.translated": "true",
    "x-netflix.context.form-factor": "phone",
    "x-netflix.context.sdk-version": "2012.4",
    "x-netflix.client.appversion": "15.48.1",
    "x-netflix.context.max-device-width": "375",
    "x-netflix.context.ab-tests": "",
    "x-netflix.tracing.cl.useractionid": "4DC655F2-9C3C-4343-8229-CA1B003C3053",
    "x-netflix.client.type": "argo",
    "x-netflix.client.ftl.esn": "NFAPPL-02-IPHONE8=1-PXA-02026U9VV5O8AUKEAEO8PUJETCGDD4PQRI9DEB3MDLEMD0EACM4CS78LMD334MN3MQ3NMJ8SU9O9MVGS6BJCURM1PH1MUTGDPF4S4200",
    "x-netflix.context.locales": "en-US",
    "x-netflix.context.top-level-uuid": "90AFE39F-ADF1-4D8A-B33E-528730990FE3",
    "x-netflix.client.iosversion": "15.8.5",
    "accept-language": "en-US;q=1",
    "x-netflix.argo.abtests": "",
    "x-netflix.context.os-version": "15.8.5",
    "x-netflix.request.client.context": '{"appState":"foreground"}',
    "x-netflix.context.ui-flavor": "argo",
    "x-netflix.argo.nfnsm": "9",
    "x-netflix.context.pixel-density": "2.0",
    "x-netflix.request.toplevel.uuid": "90AFE39F-ADF1-4D8A-B33E-528730990FE3",
    "x-netflix.request.client.timezoneid": "Asia/Ho_Chi_Minh",
}

COOKIE_KEYS = ("NetflixId", "SecureNetflixId", "nfvdid", "OptanonConsent")


# ============================================================
# COOKIE READERS
# ============================================================

def read_cookies_from_txt(filepath):
    """Read cookies from Netscape/Mozilla TXT format."""
    cookies = {}
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split('\t')
            if len(parts) >= 7 and 'netflix.com' in parts[0]:
                cookies[parts[5]] = parts[6]
    return cookies


def read_cookies_from_json(filepath):
    """Read cookies from JSON file (browser extension export)."""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    cookies = {}
    if isinstance(data, list):
        for c in data:
            if 'netflix.com' in c.get('domain', ''):
                name = c.get('name', '')
                value = c.get('value', '')
                if name in COOKIE_KEYS:
                    cookies[name] = value
    return cookies


def read_cookies(filepath):
    """Auto-detect format and read cookies."""
    ext = os.path.splitext(filepath)[1].lower()

    cookies = {}

    # Try Netscape TXT format
    try:
        txt_cookies = read_cookies_from_txt(filepath)
        if txt_cookies:
            cookies.update(txt_cookies)
    except Exception:
        pass

    # Try JSON format
    if not cookies:
        try:
            cookies = read_cookies_from_json(filepath)
        except Exception:
            pass

    # Try raw cookie string format: NetflixId=xxx; SecureNetflixId=xxx
    if not cookies:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                text = f.read()
            for key in COOKIE_KEYS:
                match = re.search(rf'(?<!\w){re.escape(key)}=([^;\s,]+)', text)
                if match:
                    value = match.group(1)
                    if '%' in value:
                        try:
                            value = urllib.parse.unquote(value)
                        except Exception:
                            pass
                    cookies[key] = value
        except Exception:
            pass

    return cookies


# ============================================================
# NFTOKEN GENERATOR
# ============================================================

def fetch_nftoken(netflix_id):
    """
    Call Netflix iOS API to generate an nftoken from NetflixId cookie.
    Returns (token, expires_timestamp) or raises on failure.
    """
    headers = dict(BASE_HEADERS)
    headers["Cookie"] = f"NetflixId={netflix_id}"

    response = requests.get(
        API_URL,
        params=QUERY_PARAMS,
        headers=headers,
        timeout=30,
        verify=False,
    )
    response.raise_for_status()

    data = response.json()

    # Extract token from nested response: value.account.token.default.token
    token_data = (
        (((data.get("value") or {}).get("account") or {}).get("token") or {}).get("default")
        or {}
    )
    token = token_data.get("token")
    expires = token_data.get("expires")

    if not token:
        raise ValueError(f"No token in response. Keys: {list(data.keys())}")

    # Convert milliseconds to seconds if needed
    if isinstance(expires, int) and len(str(expires)) == 13:
        expires //= 1000

    return token, expires


def build_nftoken_link(token):
    """Build the Netflix login URL with nftoken."""
    return f"https://netflix.com/browse?nftoken={token}"


def format_expiry(expires):
    """Format expiry timestamp to human-readable string."""
    if not isinstance(expires, (int, float)):
        return "Unknown"
    try:
        return datetime.fromtimestamp(expires).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(expires)


# ============================================================
# MAIN
# ============================================================

def main():
    print()
    print("=" * 60)
    print("  NETFLIX COOKIE -> NFTOKEN LOGIN LINK GENERATOR")
    print("  Uses Netflix iOS API to generate real nftoken")
    print("=" * 60)
    print()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    cookie_dir = os.path.join(script_dir, "Cookie")

    if not os.path.exists(cookie_dir):
        print("[ERROR] Cookie folder not found!")
        print("  Create a 'Cookie' folder with .json/.txt cookie files.")
        input("\nPress Enter to exit...")
        sys.exit(1)

    files = [f for f in os.listdir(cookie_dir)
             if os.path.isfile(os.path.join(cookie_dir, f))]

    if not files:
        print("[ERROR] Cookie folder is empty!")
        input("\nPress Enter to exit...")
        sys.exit(1)

    print(f"[*] Found {len(files)} file(s) in Cookie/")
    print("-" * 60)

    results = []

    for filename in files:
        filepath = os.path.join(cookie_dir, filename)
        print(f"\n[+] Processing: {filename}")

        try:
            cookies = read_cookies(filepath)
        except Exception as e:
            print(f"    [FAIL] Cannot read file: {e}")
            continue

        netflix_id = cookies.get('NetflixId')
        if not netflix_id:
            print("    [FAIL] No NetflixId found in file")
            continue

        print(f"    NetflixId: {netflix_id[:60]}...")

        # Call Netflix iOS API to get nftoken
        print("    [*] Calling Netflix iOS API for nftoken...")
        try:
            token, expires = fetch_nftoken(netflix_id)
            link = build_nftoken_link(token)
            expiry_str = format_expiry(expires)

            print("    [OK] NFToken generated successfully!")
            print()
            print("    " + "=" * 52)
            print("    NFTOKEN LOGIN LINK:")
            print("    " + "=" * 52)
            print()
            print(f"    {link}")
            print()
            print(f"    Expires: {expiry_str}")
            print("    " + "-" * 52)

            results.append({
                'file': filename,
                'link': link,
                'token': token,
                'expires': expiry_str,
            })

        except requests.exceptions.HTTPError as e:
            print(f"    [FAIL] HTTP Error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"    Status: {e.response.status_code}")
                try:
                    print(f"    Body: {e.response.text[:200]}")
                except Exception:
                    pass
        except ValueError as e:
            print(f"    [FAIL] {e}")
        except Exception as e:
            print(f"    [FAIL] Error: {e}")

    # Save results
    if results:
        output_file = os.path.join(script_dir, "nftoken_links.txt")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"Netflix NFToken Links - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 60 + "\n\n")
            for r in results:
                f.write(f"File: {r['file']}\n")
                f.write(f"Link: {r['link']}\n")
                f.write(f"Expires: {r['expires']}\n")
                f.write("-" * 60 + "\n\n")

        print(f"\n{'=' * 60}")
        print(f"[DONE] Generated {len(results)} nftoken link(s)")
        print(f"[DONE] Saved to: nftoken_links.txt")
        print(f"{'=' * 60}")
    else:
        print(f"\n{'=' * 60}")
        print("[FAIL] Could not generate any nftoken links")
        print(f"{'=' * 60}")

    input("\nPress Enter to exit...")


if __name__ == '__main__':
    main()
