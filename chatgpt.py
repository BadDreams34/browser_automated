from playwright.sync_api import sync_playwright, Error as PlaywrightError
import pyperclip
import time


def navigate_url(url,page):
    while True: 
        try:
            page.goto(url,wait_until="load", timeout=10000)
            print(f"Sucessfully Loaded the page {url}")
            break
        except PlaywrightError as e:
            if e.name == "ERR_NETWORK_CHANGED" or e.name == "ERR_INTERNET_DISCONNECTED":
                print(f"Network error occurred. Retrying...")
                time.sleep(2)

def ask_chatgpt(message):
    with sync_playwright() as p:
#        browser = p.chromium.connect_over_cdp("http://localhost:9222")
#        default_context = browser.contexts[0]
        context = p.chromium.launch_persistent_context(
                        user_data_dir="./chatgpt_profile",
                        headless=False
                        )

        page = context.pages[0] if context.pages else context.new_page()
        
        # navigate to chatgpt.com
        navigate_url('https://www.chatgpt.com',page)

        # paste the query and messages okay
        locator_elem = page.get_by_placeholder("Ask ChatGPT")
        locator_elem.wait_for(state="visible",timeout=30000)
        locator_elem.fill(message)

        locator_send = page.get_by_label("Send message").click()
        page.get_by_label("Stop generating").wait_for(
            state="hidden",
            timeout=120000
        )


        # Copy response
        copy_button = page.get_by_label("Copy response").last
        copy_button.wait_for(state="visible", timeout=30000)
        pyperclip.copy("")
        copy_button.click()


        time.sleep(1)

        for _ in range(50):
            result = pyperclip.paste()

            if result.strip():
                return result

            time.sleep(0.2)

        raise TimeoutError("Clipboard did not receive the response.")
