from pydantic import BaseModel, Field, ValidationError, model_validator, HttpUrl
from playwright.sync_api import sync_playwright, Error as PlaywrightError
def extract_elements(pages):
    '''extract only meaningful information from the page, like give me clickable or interactable elements from the page at any instant and return a specific format output as dictionary'''
    script = """

() => {
    document.querySelectorAll('[data_agent_id]').forEach(e => {
        e.removeAttribute('data_agent_id');
    });

    const selectors = [
        'button', 'textarea', 'input', 'select', 'a[href]',
        '[role="button"]', '[role="link"]',
        '[role="checkbox"]', '[role="radio"]',
        '[role="switch"]', '[role="tab"]',
        '[role="menuitem"]', '[onclick]',
        '[tabindex]:not([tabindex="-1"])',
        '[contenteditable="true"]', 'label', 'summary'
    ].join(', ');

    const allElements = document.querySelectorAll(selectors);
    const final_dict = [];
    let index = 0;

    allElements.forEach(e => {
        const style = window.getComputedStyle(e);
        const rect = e.getBoundingClientRect();

        if (
            style.display === 'none' ||
            style.visibility === 'hidden' ||
            style.opacity === '0' ||
            !e.checkVisibility() ||
            rect.width === 0 ||
            rect.height === 0
        ) return;

        const id = index++;
        e.setAttribute('data_agent_id', id);

        // Associated labels
        const labels = e.labels
            ? Array.from(e.labels).map(l => l.innerText.trim())
            : [];

        // Accessible naming information
        const ariaLabel = e.getAttribute('aria-label');

        const labelledBy = e.getAttribute('aria-labelledby');
        const labelledByText = labelledBy
            ? labelledBy.split(/\\s+/).map(id => {
                return document.getElementById(id)?.innerText || '';
            }).join(' ').trim()
            : '';

        // Limited parent context
        const parentText = e.parentElement
            ? e.parentElement.innerText.trim().slice(0, 200)
            : '';

        const elementInfo = {
            id,
            tag: e.tagName.toLowerCase(),
            text: (e.innerText || '').trim().slice(0, 200),

            type: e.getAttribute('type'),
            role: e.getAttribute('role'),

            placeholder: e.getAttribute('placeholder'),
            aria_label: ariaLabel,
            labelled_by_text: labelledByText,
            labels,

            name: e.getAttribute('name'),
            title: e.getAttribute('title'),

            href: e.tagName === 'A' ? e.href : null,

            alt: e.getAttribute('alt'),

            parent_text: parentText,

            is_disabled:
                e.disabled === true ||
                e.getAttribute('aria-disabled') === 'true',

            is_checked:
                typeof e.checked === 'boolean'
                    ? e.checked
                    : null,

            is_contenteditable:
                e.isContentEditable
        };

        final_dict.push(elementInfo);
    });

    return final_dict;
}

"""
    return pages.evaluate(script)
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    default_context = browser.contexts[0]
    page = default_context.pages[0] if default_context.pages else default_context.new_page()

    print(extract_elements(page))
    
 