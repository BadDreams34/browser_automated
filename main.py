from __future__ import annotations
from playwright.sync_api import sync_playwright, Error as PlaywrightError
import ollama
from typing import Literal, Optional, Annotated
import playwright
import time
import json
from pydantic import BaseModel, Field, ValidationError
import datetime

task_list = ''
current_page_url = ''
curr_state = []
next_task = ''
query = "Change my Leetcode profile picture to the one you might find from google."
MODEL = 'deepseek-r1:14b'
f_name = f"debug_{datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")}.txt"
file = open(f_name, "w+")
def extract_elements(pages):
    '''extract only meaningful information from the page, like give me clickable or interactable elements from the page at any instant and return a specific format output as dictionary'''
    script = """
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
"""
    return pages.evaluate(script)


class next_action(BaseModel):
    selected_element_id: Annotated[
        Optional[int],

        Field(description=(
                "The ID of the exact element from the supplied page_content "
                "that must be interacted with. It must match an existing element ID. "
                "Never invent, modify, or guess an ID. Use null when no browser "
                "element needs to be interacted with."
            ))
    ] = None
    action: Annotated[
        Literal["click","fill","navigate", None],
         Field(
            description=(
                "The browser operation to perform. Use 'click' to activate "
                "the selected element. Use 'fill' to enter text into an input "
                "or textarea. Use navigate when task requires to open a new webpage and is required to navigate to a particular website."
                "Use None when no browser interaction is required, "
                "such as when the task is complete or more information is needed."
            )
        )
    ]
    
    text: Annotated[
        Optional[str],
        Field(
            description=(
                "The exact text to enter when action is 'fill'. "
                "Preserve the intended spelling, capitalization, and content. "
                "if action is 'navigation' provide the exact url browser should redirect to for further execution of script"
                "Must be null for 'click' and 'none'."
            )
        )
    ] = None

    
    error: Annotated[
        Optional[str],
        Field(
            description=(
                "Describe the specific obstacle preventing task execution. "
                "Include relevant observations and why the current step cannot "
                "proceed. Use null when no error exists. Provide enough information "
                "for the program to replan the task."
            )
        )
        
    ] = None

    task_state: Annotated[
        Literal["error_occured", "completed", "running"],
        Field(description=(
            "Keep track of the currently executed task. Used for debugging. Keep the default to running."
        ))
    ]
    
    

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
1. After generating the final answer reverify your answer by checking it again yourself and seeing if it is what is to be made.
2. Keep in mind that you are writing these tasks for an ai agent to perform a particular automation so be sure to include edge cases of making sure to be logged in and stuff like that.
3. Make sure that the task should be generate since the agent has only the capability to Navigate to a specific Url, click on a specific element using its id on the web or fill in any text in a specific element.
'''

NEXT_ACTION_PROMPT = """
You are the next-action decision component of a browser automation agent.

You receive:
- The user's original request.
- task_list :  contains the list of tasks in plain english. 
- curr_state : current state of the browser automation agent and performed actions till now.
- The current URL.
- page_content : A list of visible, interactable webpage elements.

Choose at most ONE browser action that advances the earliest relevant pending task.

Rules:
1. Select an element only by an ID present in page_content.
2. Use action="click" if the element with the selected id should be clicked.
3. Use action="fill" only for an ordinary text input, textarea, or contenteditable element.
5. Do not invent text that the user has not supplied or clearly requested.
6. Do not claim an action succeeded; Python will report whether it succeeded.
9. If blocked (for example, login is required, a CAPTCHA appears, or a required
   local file has not been supplied), use action="none", selected_element_id=null,
   and explain the blocker in error.
10. If an element is not present in page_content, do not guess its ID. and provide relevent details in error.
12. Prefer the least consequential action that advances the task.
13. It Might be worthy to rethink your own reponse before providing the final output to the user. Generate three different answers and then select one based on your own thinking. try to reason them. Also make sure the final output strictly follows the mentioned structure.
14. If the user's task is already completed, return action="none",
    selected_element_id=null, and error=null.
15. If no suitable element is available, do not select an unrelated element.
    Return action="none" and explain the situation in error.
14. if the current task requires opening a new webpage, use action="navigate" to redirect user to the given website and provide the exact url in the text field.
"""

system_prompt_3 = '''Based on the given query Your task is to generate the initial_web_url on which browser should go to to start this automation. Be sure to provide the output with only a link to the initial weburl.
e.g. Query : Change my instagram profile. Output : https://www.instagram.com
e.g.2 Query : move my youtube playlist to spotify. Output : https://www.youtube.com/
Make sure the output format is as follows : 
>>>Output Start
https://www.example.com
<<<OUTPUT END
Be sure to just return the link which suits best as the initial link according to the given query and thus going to be first website to go on to.
'''

ERROR_VALIDATION_PROMPT = '''You are given an error that occured while trying to decide the next immediate action in the current script and you are also provided with a list of already occured states in the current execution with curr_state and a Task List which consists of list of items in plain words. Based on the given curr_state and the error, your task is to generate a new_task list based on the given error in order to fix the given error. 
You need to keep the format of task list as it was and generate your output in the same structure as the task list. 
Expected output format:
>>>output start 
1. step_1
2. step_2
3. step_3
<<<output_end

It Might be worthy to rethink your own reponse before providing the final output to the user. Generate three different answers and then select one based on your own thinking. try to reason them. Also make sure the final output strictly follows the mentioned structure.
To provide the given output follow the given steps: 
1. After generating the final answer reverify your answer by checking it again yourself and seeing if it is what is to be made.
2. Make sure you provide instructions considering the error from the given query and the task list generate tends to address the error and helps in smooth automation flow.
'''

# Initialiser
output = ollama.chat(model=MODEL, messages=[
    {'role': 'system', 'content': system_prompt_3},
    {'role': 'user', 'content': query}
])
current_page_url = output['message']['content']

# Tasks Generation
output = ollama.chat(model=MODEL, messages=[
    {'role': 'system', 'content': system_prompt},
    {'role': 'user', 'content': query}
])
task_list = output['message']['content']
print(task_list)

# really just go to first page 
# check for error in the next_action 
# if there is error:
#       regenerate the task list with reference to the error using another model and thus another system_prompt# error_solved : True
#       now generate the next actionable step once again normally !  perform the given action using playwright and if there is any error possibly rely it on yourself ! 

def navigate_url(url):
    while True: 
        try:
            page.goto(url,wait_until="load", timeout=10000)
            print("Sucessfully Loaded the page")
            break
        except PlaywrightError as e:
            curr_state.append(f"Error during navigating to {url}")
            file.write(f"Error during navigating to {url}\n")
            if e.name == "ERR_NETWORK_CHANGED" or e.name == "ERR_INTERNET_DISCONNECTED":
                print(f"Network error occurred. Retrying...")
                time.sleep(2)
    

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    default_context = browser.contexts[0]
    page = default_context.pages[0] if default_context.pages else default_context.new_page()

    navigate_url(current_page_url)

    while True: # main error execution loop
        page_content = extract_elements(page) 

        #next action generation
        output = ollama.chat(
            model=MODEL, 
            messages=[
                {'role':'system', 'content': NEXT_ACTION_PROMPT},
                {'role':'user', 'content': f"current_page_url : {current_page_url}\n page_content : {page_content} \n task_list : {task_list} curr_state : {curr_state}"}
                ],
            format=next_action.model_json_schema())
        raw_response = output['message']['content']

        #Pydantic validation
        try:
            next_action_data = next_action.model_validate_json(raw_response)
        except ValidationError as e:
            curr_state.append(f"Validation Failed. err : {e}. Sent for revalidation")
            file.write(f"Validation Failed. err : {e}. Sent for revalidation\n")
            continue
        
        # logical error handling    
        if next_action_data.error:
            response = ollama.chat(model=MODEL, messages=[
                {'role':'system', 'content': ERROR_VALIDATION_PROMPT},
                {'role':'user', 'content': f" error_message : {next_action_data.error} task_list : {task_list} curr_state : {curr_state}"}
                ])
            next_action_data.task_state = "error_occured"
            curr_state.append(next_action_data)
            task_list = response['message']['content']
            curr_state.append(f"Encountered and addressed error: {next_action_data.error}")
            file.write(f"{curr_state}\n")
            continue

        # execution using Playwright
        if next_action_data.selected_element_id is not None:
            found = False
            for element in page_content:
                if element['id'] == next_action_data.selected_element_id:
                    found = True

            if not found:
                print("Element is not found in the page")
                next_action_data.task_state = "error_occured"
                curr_state.append(next_action_data)
                curr_state.append(f"Element given by {next_action_data} is not from the given list of page of content. Reverify.")
                file.write(f"{curr_state}\n")
                continue

            locator_elem = page.locator(
                f'[data_agent_id={next_action_data.selected_element_id}]'
            )
            if locator_elem.count() != 1:
                next_action_data.task_state = "error_occured"
                curr_state.append(next_action_data)
                curr_state.append(f"Page rerendered since {next_action_data} is not found on the page")
                file.write(f"{curr_state}\n")
                continue

            try:
                if next_action_data.action == "click":
                    locator_elem.click()
                    next_action_data.task_state = "completed"
                    curr_state.append(next_action_data)
                    file.write(f"{curr_state}\n")

                elif next_action_data.action == "fill":
                    if next_action_data.text:
                        locator_elem.fill(next_action_data.text)
                        next_action_data.task_state = "completed"
                        curr_state.append(next_action_data)
                        file.write(f"{curr_state}\n")

                    else:
                        next_action_data.task_state = "error_occured"
                        curr_state.append(next_action_data)
                        curr_state.append(f"Action is 'type', but no text was provided.")
                        file.write(f"{curr_state}\n")

                        continue
                elif next_action_data.action == "navigate":
                    if next_action_data.text:
                        navigate_url(next_action_data.text)
                        current_page_url = next_action_data.text
                        next_action_data.task_state = "completed"
                        curr_state.append(next_action_data)
                        file.write(f"{curr_state}\n")
                    else:
                        next_action_data.task_state = "error_occured"
                        curr_state.append(next_action_data)
                        curr_state.append(f"Action is 'navigate', but no url is provided.")
                        file.write(f"{curr_state}\n")
                        continue

            except PlaywrightError as e:
                next_action_data.task_state = "error_occured"
                curr_state.append(next_action_data)
                curr_state.append(f"Playwright execution failed: {e}")
                continue
file.close()