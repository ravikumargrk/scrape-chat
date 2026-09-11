import os
from dotenv import load_dotenv
load_dotenv()

# 2. Now it is safe to import Playwright
from playwright.sync_api import sync_playwright
import subprocess
import sys 
import time
import requests 

chrome_exec = os.environ.get('CHROME_EXEC')
chrome_rdp = os.environ.get('REMOTE_DEBUGGING_PORT')
MAX_ITERS = os.environ.get('MAX_LOAD_SEC', 10)

if (not chrome_exec) or (not chrome_rdp):
    raise RuntimeError('Define config in .env')

browser_init = [chrome_exec, '--force-device-scale-factor=1', '--disable-vulkan' , f'--remote-debugging-port={chrome_rdp}', '--user-data-dir=chrome-profile']

process = subprocess.Popen(
    browser_init,
    stdout=sys.stdout,
    stderr=sys.stderr,
    text=True,
)

def await_rdp_load():
    browser_loaded=False
    for _ in range(int(MAX_ITERS)):
        try:
            response = requests.get(f"http://localhost:{chrome_rdp}/json/version", timeout=1)
            if response.status_code == 200:
                print('Browser Loaded.')
                browser_loaded=True
                break
        except requests.RequestException:
            print('Waiting for browser to finish loading ...')
            pass
        time.sleep(1)
    if not browser_loaded:
        raise RuntimeError('Browser loading timedout.')

def wait_for_response(page, timeout=120):
    responses = page.locator("[data-assistant-markdown]")

    # Wait for at least one assistant response to appear.
    responses.first.wait_for(state="visible", timeout=30000)

    response = responses.last

    start = time.time()
    previous_text = ""
    stable_since = None

    while time.time() - start < timeout:
        current_text = response.inner_text()

        if current_text == previous_text:
            if stable_since is None:
                stable_since = time.time()
            elif time.time() - stable_since >= 2:
                # Text hasn't changed for 2 seconds -> assume streaming is finished.
                return current_text
        else:
            previous_text = current_text
            stable_since = None

        time.sleep(0.5)

    # Timeout reached; return whatever has been received so far.
    return response.inner_text()

def scrape_active_browser():
    with sync_playwright() as p:
        print("Connecting to browser ...")

        browser = p.chromium.connect_over_cdp(
            f"http://localhost:{chrome_rdp}"
        )

        context = browser.contexts[0]
        page = context.pages[0]

        page.goto(
            "https://chatgpt.com/",
            wait_until="domcontentloaded"
        )

        # print("URL:", page.url)
        # print("TITLE:", page.title())

        composer = page.locator("#mobile-composer-prompt")
        composer.wait_for(state="visible", timeout=30000)

        composer.fill("Tell me about LLMs.")
        composer.press("Enter")
        print(wait_for_response(page))
        
        try:
            time.sleep(60*30)
        except KeyboardInterrupt:
            browser.close()

        
if __name__ == "__main__":
    
    await_rdp_load()
    scrape_active_browser()
    process.kill()
