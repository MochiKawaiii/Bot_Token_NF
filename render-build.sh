#!/usr/bin/env bash
# render-build.sh - Tải Chrome for Testing (portable, không cần root)
set -o errexit

echo "=== Tải Chrome for Testing (Portable) ==="
# Lấy phiên bản mới nhất
LATEST=$(wget -qO- "https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_STABLE")
echo "Latest stable version: $LATEST"

# Tải Chrome for Testing (không cần cài đặt, chạy trực tiếp)
CHROME_URL="https://storage.googleapis.com/chrome-for-testing-public/${LATEST}/linux64/chrome-linux64.zip"
echo "Downloading Chrome from: $CHROME_URL"
wget -q "$CHROME_URL" -O /tmp/chrome.zip
unzip -o -q /tmp/chrome.zip -d /opt/render/project/
rm /tmp/chrome.zip
echo "Chrome installed at: /opt/render/project/chrome-linux64/chrome"

# Tải ChromeDriver
DRIVER_URL="https://storage.googleapis.com/chrome-for-testing-public/${LATEST}/linux64/chromedriver-linux64.zip"
echo "Downloading ChromeDriver from: $DRIVER_URL"
wget -q "$DRIVER_URL" -O /tmp/chromedriver.zip
unzip -o -q /tmp/chromedriver.zip -d /opt/render/project/
chmod +x /opt/render/project/chromedriver-linux64/chromedriver
rm /tmp/chromedriver.zip
echo "ChromeDriver installed at: /opt/render/project/chromedriver-linux64/chromedriver"

echo "=== Cài đặt Python dependencies ==="
pip install --upgrade pip
pip install -r requirements.txt

echo "=== Build hoàn tất! ==="
