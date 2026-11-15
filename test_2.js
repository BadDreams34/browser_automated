() => {

document.querySelectorAll('[data_agent_id]').forEach(e => {
    e.removeAttribute('data_agent_id');
});

const selectors = [
            'button', 'textarea', 'input', 'select', 'a[href]',
            '[role="button"]', '[role="link"]', '[role="checkbox"]', 
            '[role="radio"]', '[role="switch"]', '[role="tab"]', '[role="menuitem"]','[onclick]','[tabindex]:not([tabindex="-1"])',
'[contenteditable="true"]','label','summary'
        ].join(', ');
const allElements = document.querySelectorAll(selectors);
let final_dict = [];
let index = 0;
allElements.forEach(e => {
    const style = window.getComputedStyle(e);
    if (style.display === 'none' || style.visibility ===  'hidden' || style.opacity === '0') {
        return;
    };
    const rect = e.getBoundingClientRect();
    if (!e.checkVisibility()) {
    return;
    };

    if (rect.width === 0 || rect.height === 0) {
    return;
    };

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
