
from playwright.sync_api import sync_playwright, Error as PlaywrightError
import playwright
import time


def extract_elements(pages):
    '''extract only meaningful information from the page, like give me clickable or interactable elements from the page at any instant and return a specific format output as dictionary'''
    script = """
() => {
const selectors = [
            'button', 'textarea', 'input', 'select', 'a[href]',
            '[role="button"]', '[role="link"]', '[role="checkbox"]', 
            '[role="radio"]', '[role="switch"]', '[role="tab"]', '[role="menuitem"]'
        ].join(', ');
const allElements = document.querySelectorAll(selectors);
let final_dict = [];
let index = 0;
allElements.forEach(e => {
    const style = window.getComputedStyle(e);
    if (style.display === 'none' || style.visibility ===  'hidden' || style.opacity === '0') {
        return;
    }

    const id = index++;
    e.setAttribute('data_agent_id', id)

    final_dict.push({
        id: id,
        tag: e.tagName.toLowerCase(),
        text: (e.innerText || '').trim()
    });
});

return final_dict;
};
"""
    return pages.evaluate(script)

with sync_playwright() as p:
    
    current_page_url = 'https://www.reddit.com'
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    default_context = browser.contexts[0]
    page = default_context.pages[0] if default_context.pages else default_context.new_page()

    while True: 
        try:
            page.goto(current_page_url,wait_until="load", timeout=10000)
            print("Sucessfully Loaded the page")
            break
        except PlaywrightError as e:
            if e.name == "ERR_NETWORK_CHANGED" or e.name == "ERR_INTERNET_DISCONNECTED":
                print(f"Network error occurred. Retrying...")
                time.sleep(2)
    
    page_content = extract_elements(page)
    print(page_content)
