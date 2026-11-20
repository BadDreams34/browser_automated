from playwright.sync_api import sync_playwright, Error as PlaywrightError

class Tab:
    def __init__(self, id,page):
        self.tab_id = id
        self.page = page

class BrowserWindow:
    def __init__(self, context) -> None:
         self._tab_id = 1
         self.context = context
         self.opened_tabs = []
         self.current_visible_tab_id = None

    def create_new_tab(self):
        page = self.context.new_page()
        tab = Tab(self._tab_id, page)
        self.current_visible_tab_id = self._tab_id
        self._tab_id += 1
        self.opened_tabs.append(tab)
        page.bring_to_front()
        return page

    def switch_tab(self, tab_id):
        found = False
        for tab in self.opened_tabs:
            if tab.tab_id == tab_id:
                found = True
                page = tab.page
        if not found:
            raise ValueError("Given Tab_id is not valid")
        page.bring_to_front()
        self.current_visible_tab_id = tab_id
        return page

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    default_context = browser.contexts[0]
    browser_window = BrowserWindow(default_context)

    page_1 = browser_window.create_new_tab()
    page_1.goto("https://www.youtube.com")
    page_2 = browser_window.create_new_tab()
    page_2.goto("https://www.reddit.com")

    page = browser_window.switch_tab(1)
    page.goto('https://www.google.com')
    page = browser_window.create_new_tab()
    page.goto('https://www.chatgpt.com')


    for tabs in browser_window.opened_tabs:
        print(vars(tabs))
        print()

    
