

async def extract_elements(pages):
    '''extract only meaningful information from the page, like give me clickable or interactable elements from the page at any instant and return a specific format output as dictionary'''

    # how to really work with it ? 
    # maybe work with Javascript okay firstly write a javascript 
    script = '''
() => {
let selectors = 'button, textarea, radio, a, input, select, [role="button"],
        [role="link"],
        [role="checkbox"],
        [role="radio"],
        [role="switch"],
        [role="tab"],
        [role="menuitem"]';
let elements = document.querySelectorAll(selectors)

const allElements = document.querySelectorAll('*');
const interactive = Array.from(allElements).filter(e => {
    return e.hasAttribute('onclick') || window.getComputedStyle(e).cursor === 'pointer' || e.matches(selectors);
})

// now the map thing okay, map does maps any element to any other element # 
let final_dict = interactive.map((e, i) => {
    // just map it to the simple dictionaray 
    return {id : i, tagname : e.tagName.toLowerCase(), text : e.innerText ? e.innerText.trim().substring(0, 50) : '', type : e.type || '', placeholder : e.placeholder || ''}
})

return final_dict
'''
    return await pages.evaluate(script)

