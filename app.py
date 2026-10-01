import logging
import os
import subprocess
import threading
import time

import requests
from dotenv import load_dotenv

# from playwright.sync_api import Locator, Page
from playwright.sync_api import sync_playwright

# Load environment
load_dotenv()
chrome_exec = os.environ.get("CHROME_EXEC")
chrome_rdp = os.environ.get("REMOTE_DEBUGGING_PORT")
MAX_ITERS = os.environ.get("MAX_LOAD_SEC", "10")
if (not chrome_exec) or (not chrome_rdp):
    raise RuntimeError("Define config in .env")

# Configure your logger
logging.basicConfig(
    filename="browser.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def log_stream(stream, log_level):
    """Reads a stream line-by-line and logs it in real-time."""
    # errors="replace" handles decoding errors gracefully if output contains weird characters
    with stream:
        for line in iter(stream.readline, ""):
            logger.log(log_level, line.strip())


def run_command_with_logging(cmd):
    # Start the process with pipes for stdout and stderr
    # text=True handles string decoding automatically instead of raw bytes
    process = subprocess.Popen(
        browser_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
    )
    # Create and start separate threads to read stdout and stderr concurrently
    stdout_thread = threading.Thread(
        target=log_stream, args=(process.stdout, logging.INFO)
    )
    stderr_thread = threading.Thread(
        target=log_stream, args=(process.stderr, logging.ERROR)
    )
    stdout_thread.start()
    stderr_thread.start()
    logger.info(f"Browser started in background with PID {process.pid}")
    return process


def await_rdp_load():
    browser_loaded = False
    for _ in range(int(MAX_ITERS)):
        try:
            response = requests.get(
                f"http://localhost:{chrome_rdp}/json/version", timeout=1
            )
            if response.status_code == 200:
                print("Browser Loaded.")
                browser_loaded = True
                break
        except requests.RequestException:
            print("Waiting for browser to finish loading ...")
        time.sleep(1)
    if not browser_loaded:
        raise RuntimeError("Browser loading timedout.")


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


def connect_browser():
    """Connect to browser context and return context and page safely"""
    print("Connecting to browser ...")
    pw_object = sync_playwright().start()
    browser = pw_object.chromium.connect_over_cdp(f"http://localhost:{chrome_rdp}")
    first_context = browser.contexts[0]  # Always exists
    page = first_context.pages[0]  # Exists because we launched with url
    print(f"Connected to {page.url}")
    composer = page.locator("#mobile#composer#prompt")
    composer.wait_for(state="visible", timeout=30000)
    return pw_object, first_context, page, composer


# def scrape_active_browser():
#    with sync_playwright() as p:
#        print("Connecting to browser ...")
#
#        browser = p.chromium.connect_over_cdp(
#            f"http://localhost:{chrome_rdp}"
#        )
#
#        context = browser.contexts[0]
#        page = context.pages[0]
#
#        page.goto(
#            "https://chatgpt.com/",
#            wait_until="domcontentloaded"
#        )
#
#        # print("URL:", page.url)
#        # print("TITLE:", page.title())
#
#        composer = page.locator("#mobile#composer#prompt")
#        composer.wait_for(state="visible", timeout=30000)
#
#        composer.fill("Tell me about LLMs.")
#        composer.press("Enter")
#        print(wait_for_response(page))
#
#        try:
#            time.sleep(60*30)
#        except KeyboardInterrupt:
#            browser.close()

# from langchain_core.language_models.chat_models import BaseChatModel
# from langchain_core.messages import AIMessage, HumanMessage
#
# class ScrapingChatModel(BaseChatModel):
#     page: Page
#     composer: Locator
#
#     @property
#     def _llm_type(self):
#         return "transform-text"
#
#     def _generate(self, messages, stop=None, run_manager=None, **kwargs):
#         # Convert ChatModel messages → your function's string input
#         input_text = "\n".join(
#             message.content
#             for message in messages
#         )
#
#         # Your actual implementation
#         composer.fill(input_text)
#         composer.press("Enter")
#         output_text = transform_text(input_text)
#
#         return ChatResult(
#             generations=[
#                 ChatGeneration(
#                     message=AIMessage(content=output_text)
#                 )
#             ]
#         )
#

if __name__ == "__main__":
    # browser flags
    browser_cmd = [
        chrome_exec,
        "--force-device-scale-factor=1",
        "--disable-vulkan",
        f"--remote-debugging-port={chrome_rdp}",
        "--user-data-dir=chrome-profile",
        r"https://chatgpt.com/",
    ]
    # run browser
    _process = run_command_with_logging(browser_cmd)
    # wait
    await_rdp_load()
    _pw, _context, page, composer = connect_browser()
    # try:
    #     chat_handler = chat_handler(page)
    #
    #     # take input from stdin
    # except:
    #     _pw.stop()
    #     process.kill()
    #
