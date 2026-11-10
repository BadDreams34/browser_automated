import ollama

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

# i m going to pass what here pass this whole page in ollama and tell it to give me a structured command ! 
system_prompt = '''You are a task list generator Agent.Based on a given user query for a particular browser automation task, your job is to divide this task into a plan which includes steps needing to be followed to perform this task.
E.g. if you are given a prompt to autopost on reddit. You will provide an output of list of steps like this 
Expected Output : 
1. Check if the user is logged in. 
2. Go to the particular subreddit url.
3. Fill in the title in the provided box
4. Fill in the Body in the provided box
5. Check if the post requires to have a flair, if so select one.
6. Close the flair dialog box and post.
You need to make sure you provided clearly defined set of instructions. Make sure The instructions are actually the tasks and output is of this form :
1. step_1 
2. step_2 
3. step_3
and so on...
Divide it into as much possible doable task as possible. 
It Might be worthy to rethink your own reponse before providing the final output to the user. Generate three different answers and then select one based on your own thinking. try to reason them. Also make sure the final output strictly follows the mentioned structure.

To provide the given output follow the given steps: 
1. Use the web_search tool to perform google search on how to perform this step. Take idea from there and list it into clearly doable steps.
2. After generating the final answer reverify your answer by checking it again yourself by maybe googling and seeing if it is what is to be made.
3. Keep in mind that you are writing these tasks for an ai agent to perform a particular automation so be sure to include edge cases of making sure to be logged in and stuff like that.
'''

query = "Change my Leetcode profile picture to the one you might find from google."

ollama.create(model='task_list_generator', from_='deepseek-r1:14b',system = system_prompt)

response = ollama.generate(model='task_list_generator', prompt= query)
print(response)
