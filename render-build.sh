#!/usr/bin/env bash
# render-build.sh - Script cài đặt cho Render Web Service
# Cài Chrome + ChromeDriver trên server Linux

set -o errexit

echo "=== Cài đặt Google Chrome Stable ==="
# Tải và cài Google Chrome
apt-get update -qq && apt-get install -y -qq wget gnupg2
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list
apt-get update -qq && apt-get install -y -qq google-chrome-stable

# Lấy phiên bản Chrome đã cài
CHROME_VERSION=$(google-chrome --version | grep -oP '\d+\.\d+\.\d+')
echo "Chrome installed: $CHROME_VERSION"

echo "=== Cài đặt ChromeDriver ==="
# Tải ChromeDriver phù hợp với Chrome version
CHROMEDRIVER_URL="https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}.0/linux64/chromedriver-linux64.zip"
# Fallback: dùng endpoint mới nhất nếu URL trên không tồn tại
wget -q "$CHROMEDRIVER_URL" -O /tmp/chromedriver.zip 2>/dev/null || {
    echo "Falling back to ChromeDriver latest..."
    LATEST=$(wget -qO- "https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_STABLE")
    wget -q "https://storage.googleapis.com/chrome-for-testing-public/${LATEST}/linux64/chromedriver-linux64.zip" -O /tmp/chromedriver.zip
}

cd /tmp
unzip -o chromedriver.zip
mv chromedriver-linux64/chromedriver /usr/local/bin/chromedriver
chmod +x /usr/local/bin/chromedriver
rm -rf chromedriver.zip chromedriver-linux64

echo "ChromeDriver installed at: $(which chromedriver)"
chromedriver --version

echo "=== Cài đặt Python dependencies ==="
pip install --upgrade pip
pip install -r requirements.txt

echo "=== Build hoàn tất! ==="
