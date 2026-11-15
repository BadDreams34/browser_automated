from playwright.sync_api import sync_playwright, Error as PlaywrightError
import time


class ChatGPTClient:

    def __init__(
        self,
        headless=True,
        user_data_dir=None,
        timeout=120000
    ):
        self.headless = headless
        self.user_data_dir = user_data_dir
        self.timeout = timeout

        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def start(self):
        """Start browser and initialize ChatGPT page."""

        self.playwright = sync_playwright().start()

        if self.user_data_dir:
            self.context = (
                self.playwright.chromium.launch_persistent_context(
                    user_data_dir=self.user_data_dir,
                    headless=self.headless
                )
            )
            self.browser = None
        else:
            self.browser = self.playwright.chromium.launch(
                headless=self.headless
            )

            self.context = self.browser.new_context()

        self.page = (
            self.context.pages[0]
            if self.context.pages
            else self.context.new_page()
        )

        self._navigate("https://chatgpt.com")

        return self

    def _navigate(self, url):
        """Navigate with network retry."""

        while True:
            try:
                self.page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=30000
                )
                return

            except PlaywrightError as e:
                if any(
                    error in str(e)
                    for error in [
                        "ERR_NETWORK_CHANGED",
                        "ERR_INTERNET_DISCONNECTED"
                    ]
                ):
                    print("Network error. Retrying...")
                    time.sleep(2)
                else:
                    raise

    def ask(self, message):
        """Send a message and return ChatGPT response."""

        if not self.page:
            raise RuntimeError("Start the client first.")

        prompt = self.page.get_by_placeholder("Ask ChatGPT")

        prompt.wait_for(
            state="visible",
            timeout=30000
        )

        prompt.fill(message)

        self.page.get_by_label("Send message").click()

        self.page.get_by_label("Stop generating").wait_for(
            state="hidden",
            timeout=self.timeout
        )

        copy_button = self.page.get_by_label(
            "Copy response"
        ).last

        copy_button.wait_for(
            state="visible",
            timeout=30000
        )

        # Read the latest assistant response.
        response = self.page.locator(
            '[data-message-author-role="assistant"]'
        ).last

        return response.inner_text()

    def close(self):
        """Close browser resources."""

        if self.context:
            self.context.close()

        if self.browser:
            self.browser.close()

        if self.playwright:
            self.playwright.stop()

        self.page = None
        self.context = None
        self.browser = None
        self.playwright = None

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
