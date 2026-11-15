import json
import asyncio
import pyperclip
import time
from pydantic import BaseModel, Field, ValidationError, model_validator, HttpUrl
from playwright.sync_api import sync_playwright, Error as PlaywrightError
from typing import Literal, Optional, Annotated
import ollama
from ollama import Client
import os

# query = "Search on gemini about Change my leetcode profile by image from google."
query = "Search on youtube how to beat someone on leetcode"
def debug_message(message):
    print("\n========== MESSAGE BREAKDOWN ==========")
    print("Type:", type(message).__name__)

    if isinstance(message, dict):
        for key, value in message.items():
            serialized = json.dumps(value, ensure_ascii=False)
            print(
                f"{key}: {len(serialized)} chars "
                f"({len(serialized) // 4} approx tokens)"
            )

    elif isinstance(message, str):
        print("Message is a string.")
        print("Total characters:", len(message))

        # Inspect the largest sections if your message
        # contains serialized JSON.
        try:
            parsed = json.loads(message)
            debug_message(parsed)
        except (ValueError, TypeError):
            print(message[:500])

    elif isinstance(message, list):
        print("Items:", len(message))
        for i, item in enumerate(message):
            print(f"Item {i}: {len(str(item))} chars")

    print("======================================")

def ask_chatgpt(message):
   # chatgpt_page = next(
   #  (p for p in pages if "chatgpt.com" in p.url),
   #  None
   #    )
   chatgpt_page = None
   try:
      chatgpt_page = default_context.new_page()
      # if chatgpt_page is None:
      #    chatgpt_page = default_context.new_page()
      #    chatgpt_page.goto("https://chatgpt.com")

      chatgpt_page.goto(
         "https://chatgpt.com",
         wait_until="domcontentloaded"
      )


      # with sync_playwright() as p:
   #        browser = p.chromium.connect_over_cdp("http://localhost:9222")
   #        default_context = browser.contexts[0]
   #        context = p.chromium.launch_persistent_context(
   #                        user_data_dir="./chatgpt_profile",
   #                        headless=False
   #                        )

         #page = context.pages[0] if context.pages else context.new_page()

         
         # navigate to chatgpt.com
      #navigate_url('https://www.chatgpt.com')

      
      # paste the query and messages okay
      locator_elem = chatgpt_page.get_by_placeholder("Ask ChatGPT")
      locator_elem.wait_for(state="visible",timeout=30000)
      payload = json.dumps(message, ensure_ascii=False)

      print("\n========== PROMPT DEBUG ==========")
      print("Characters:", len(payload))
      print("Approx tokens:", len(payload) // 4)
      print("Size in KB:", round(len(payload.encode("utf-8")) / 1024, 2))

      if isinstance(message, dict):
         for key, value in message.items():
            content = json.dumps(value, ensure_ascii=False)
            print(f"{key}: {len(content)} characters")

      print("==================================\n")

      locator_elem.fill(json.dumps(message, indent=2))
      chatgpt_page.get_by_label("Send message").click()
      chatgpt_page.get_by_label("Stop generating").wait_for(
         state="hidden",
         timeout=120000
      )


      # Copy response
      copy_button = chatgpt_page.get_by_label("Copy response").last
      copy_button.wait_for(state="visible", timeout=30000)
      pyperclip.copy("")
      copy_button.click()


      time.sleep(1)

      for _ in range(50):
         result = pyperclip.paste()

         if result.strip():
               print(repr(result))
               return result

         time.sleep(0.2)


      raise TimeoutError("Clipboard did not receive the response.")
   finally:
      if chatgpt_page and not chatgpt_page.is_closed():
         chatgpt_page.close()


client = Client(
    host='http://localhost:11434',
)

MODEL = 'qwen3.5:4b'

curr_page_url = ''


class Task:
   def __init__(self, query, iscompleted=False) -> None:
        self.tasks = []
        self.query = query
        self.completed = iscompleted
main_task = Task(query)

class Subtask:
    _counter = 1
    def __init__(self, description, prev_exec_task = None, output = None, completed= False,) -> None:
        self.subtask_id = Subtask._counter
        Subtask._counter += 1
        self.description = description
        self.previously_executed_task = prev_exec_task
        self.executed_tasks = []
        self.sub_task_execution_output = output
        self.completed = completed

class NextAction(BaseModel):
        selected_element_id: Annotated[
        int,
        Field(
                default=-1,
                description=(
                "The ID of the exact element from the supplied page_content "
                "that must be interacted with. It must match an existing element ID. "
                "Never invent, modify, or guess an ID. Use -1 when no browser or when action is locate"
                "element needs to be interacted with."
            ))
        ] 
        action : Annotated[
         Literal['click', 'fill', 'locate'], 
         Field(
            description=(
                "The browser operation to perform. Use 'click' to activate "
                "the selected element. Use 'fill' to enter text into an input "
                "or textarea. Use 'locate' when task requires to open a new webpage and is required to navigate to a particular website."
                "such as when the task is complete or more information is needed."
            )
        )]
        text: Annotated[
        str,
        Field(
                default= '',
            description=(
                "Never use 'none' or 'null' as text. Use an empty string."
                "The exact text to enter when action is 'fill'. or url when action is 'locate'"
                "Preserve the intended spelling, capitalization, and content. "
                "if action is 'locate' provide the exact url browser should redirect to for further execution of script"
                "Must be emptry string for 'click'."
                "IT MUST PROVIDE NOTHING ELSE AND JUST EITHER URL OR THE EXACT TEXT TO FILL IN"
            )
        ) 
    ] 

        @model_validator(mode="after")
        def validate_action_fields(self):
            if self.text.strip().lower() in ["none", "null"]:
                  raise ValueError("Never use 'none' or 'null' as text. Use an empty string.")
            if self.action == "fill" or self.action == "locate":
                  if not self.text:
                           raise ValueError("Text is not provided when action is fill.")
            if self.action == "locate":
               try:
                  HttpUrl(self.text)
               except Exception:
                  raise ValueError("text must contain a valid http/https url for action locate")
            if self.action == "click" and self.text:
                  raise ValueError("Text is provided whilst the action is click.")
            if self.action in ["fill", "click"]:
                  if self.selected_element_id == -1:
                           raise ValueError("No element is provide whilist the action is click")
                  # check if the selected element id is in the page content's id itself ! 
                  found = False
                  for element in page_content:
                     if element['id'] == self.selected_element_id:
                        found = True
                  if not found:
                     raise ValueError("The selected Element id is not present in page_content.")

            if self.action == "locate":
                  if self.selected_element_id != -1:
                           raise ValueError("element id is provide whilist the action is locate")
            return self

def extract_visible_text(page):
   try:
      visible_text = page.locator("body").inner_text(timeout=5000)
      return visible_text.strip()[:1000]
   except Exception as e:
      print(f"error during extraction {e}")
      return ""
   

def validate_action_compatibility(action, page_content):
   if action.action == "locate":
        return

   element = next( (
            e for e in page_content
            if e["id"] == action.selected_element_id
        ),
        None
    )

   if element is None:
        raise ValueError("Element does not exist in page content")

   if action.action == "fill":

        tag = element["tag"].lower()
        input_type = (element.get("type") or "text").lower()

        is_fillable = (
            tag == "textarea"
            or (
                tag == "input"
                and input_type not in {
                    "button", "submit", "reset",
                    "checkbox", "radio", "file",
                    "image"
                }
            )
            or element.get("is_contenteditable") is True
        )

        if not is_fillable:
            raise ValueError(
                f"Element {element['id']} is not fillable. "
                f"Tag: {tag}, type: {input_type}, "
                f"text: {element.get('text')}"
            )
      
def navigate_url(url):
    while True: 
        try:
            page.goto(url,wait_until="load", timeout=10000)
            print(f"Sucessfully Loaded the page {url}")
            break
        except PlaywrightError as e:
            if e.name == "ERR_NETWORK_CHANGED" or e.name == "ERR_INTERNET_DISCONNECTED":
                print(f"Network error occurred. Retrying...")
                time.sleep(2)
    

# def extract_elements(pages):
#     '''extract only meaningful information from the page, like give me clickable or interactable elements from the page at any instant and return a specific format output as dictionary'''
#     script = """

# () => {
#     document.querySelectorAll('[data_agent_id]').forEach(e => {
#         e.removeAttribute('data_agent_id');
#     });

#     const selectors = [
#         'button', 'textarea', 'input', 'select', 'a[href]',
#         '[role="button"]', '[role="link"]',
#         '[role="checkbox"]', '[role="radio"]',
#         '[role="switch"]', '[role="tab"]',
#         '[role="menuitem"]', '[onclick]',
#         '[tabindex]:not([tabindex="-1"])',
#         '[contenteditable="true"]', 'label', 'summary'
#     ].join(', ');

#     const allElements = document.querySelectorAll(selectors);
#     const final_dict = [];
#     let index = 0;

#     allElements.forEach(e => {
#         const style = window.getComputedStyle(e);
#         const rect = e.getBoundingClientRect();

#         if (
#             style.display === 'none' ||
#             style.visibility === 'hidden' ||
#             style.opacity === '0' ||
#             !e.checkVisibility() ||
#             rect.width === 0 ||
#             rect.height === 0
#         ) return;

#         const id = index++;
#         e.setAttribute('data_agent_id', id);

#         // Associated labels
#         const labels = e.labels
#             ? Array.from(e.labels).map(l => l.innerText.trim())
#             : [];

#         // Accessible naming information
#         const ariaLabel = e.getAttribute('aria-label');

#         const labelledBy = e.getAttribute('aria-labelledby');
#         const labelledByText = labelledBy
#             ? labelledBy.split(/\\s+/).map(id => {
#                 return document.getElementById(id)?.innerText || '';
#             }).join(' ').trim()
#             : '';

#         // Limited parent context
#         const parentText = e.parentElement
#             ? e.parentElement.innerText.trim().slice(0, 200)
#             : '';

#         const elementInfo = {
#             id,
#             tag: e.tagName.toLowerCase(),
#             text: (e.innerText || '').trim().slice(0, 200),

#             type: e.getAttribute('type'),
#             role: e.getAttribute('role'),

#             placeholder: e.getAttribute('placeholder'),
#             aria_label: ariaLabel,
#             labelled_by_text: labelledByText,
#             labels,

#             name: e.getAttribute('name'),
#             title: e.getAttribute('title'),

#             href: e.tagName === 'A' ? e.href : null,

#             alt: e.getAttribute('alt'),

#             parent_text: parentText,

#             is_disabled:
#                 e.disabled === true ||
#                 e.getAttribute('aria-disabled') === 'true',

#             is_checked:
#                 typeof e.checked === 'boolean'
#                     ? e.checked
#                     : null,

#             is_contenteditable:
#                 e.isContentEditable
#         };

#         final_dict.push(elementInfo);
#     });

#     return final_dict;
# }

# """
#     return pages.evaluate(script)

def extract_elements(page):
    script = """
    () => {
        // Remove IDs from the previous extraction.
        document.querySelectorAll('[data_agent_id]').forEach(e => {
            e.removeAttribute('data_agent_id');
        });

        const selectors = [
            'button',
            'input:not([type="hidden"])',
            'textarea',
            'select',
            'a[href]',
            '[role="button"]',
            '[role="link"]',
            '[role="checkbox"]',
            '[role="radio"]',
            '[role="switch"]',
            '[role="tab"]',
            '[role="menuitem"]',
            '[role="option"]',
            '[role="combobox"]',
            '[role="searchbox"]',
            '[onclick]',
            '[tabindex]:not([tabindex="-1"])',
            '[contenteditable="true"]',
            'summary'
        ].join(',');

        const elements = Array.from(
            document.querySelectorAll(selectors)
        );

        const results = [];
        let index = 0;

        function getText(el) {
            return (el.innerText || el.textContent || '')
                .replace(/\\s+/g, ' ')
                .trim()
                .slice(0, 120);
        }

        function getAccessibleName(el) {
            // Explicit accessible name
            const ariaLabel = el.getAttribute('aria-label');
            if (ariaLabel) return ariaLabel.trim();

            // aria-labelledby
            const labelledBy = el.getAttribute('aria-labelledby');

            if (labelledBy) {
                const text = labelledBy
                    .split(/\\s+/)
                    .map(id => document.getElementById(id))
                    .filter(Boolean)
                    .map(getText)
                    .join(' ')
                    .trim();

                if (text) return text;
            }

            // Associated labels
            if (el.labels && el.labels.length) {
                const text = Array.from(el.labels)
                    .map(getText)
                    .filter(Boolean)
                    .join(' ');

                if (text) return text;
            }

            // Image alt, title, placeholder
            if (el.getAttribute('alt'))
                return el.getAttribute('alt');

            if (el.getAttribute('title'))
                return el.getAttribute('title');

            if (el.getAttribute('placeholder'))
                return el.getAttribute('placeholder');

            // Input button values
            if (
                ['submit', 'button', 'reset'].includes(
                    el.type?.toLowerCase()
                )
            ) {
                return el.value || '';
            }

            return getText(el);
        }

        function getSection(el) {
            const section = el.closest(
                'header, nav, main, aside, footer, form, ' +
                '[role="banner"], [role="navigation"], ' +
                '[role="main"], [role="complementary"], ' +
                '[role="dialog"], [role="search"]'
            );

            if (!section) return null;

            return {
                tag: section.tagName.toLowerCase(),
                name:
                    section.getAttribute('aria-label') ||
                    section.getAttribute('title') ||
                    ''
            };
        }

        function isVisible(el) {
            const style = window.getComputedStyle(el);
            const rect = el.getBoundingClientRect();

            if (
                style.display === 'none' ||
                style.visibility === 'hidden' ||
                Number(style.opacity) === 0 ||
                rect.width === 0 ||
                rect.height === 0 ||
                el.closest('[aria-hidden="true"], [inert]')
            ) {
                return false;
            }

            if (
                typeof el.checkVisibility === 'function' &&
                !el.checkVisibility({
                    checkOpacity: true,
                    checkVisibilityCSS: true
                })
            ) {
                return false;
            }

            // Must intersect the current viewport.
            if (
                rect.bottom <= 0 ||
                rect.right <= 0 ||
                rect.top >= window.innerHeight ||
                rect.left >= window.innerWidth
            ) {
                return false;
            }

            return true;
        }

        // First pass: identify visible interactive elements.
        elements.forEach(el => {
            if (!isVisible(el)) return;

            const id = index++;
            el.setAttribute('data_agent_id', id);

            const rect = el.getBoundingClientRect();

            const parent = el.parentElement;

            // Only direct text of the parent, not its entire subtree.
            const parentText = parent
                ? Array.from(parent.childNodes)
                    .filter(n => n.nodeType === Node.TEXT_NODE)
                    .map(n => n.textContent.trim())
                    .filter(Boolean)
                    .join(' ')
                    .slice(0, 100)
                : '';

            const disabled =
                el.matches(':disabled') ||
                el.getAttribute('aria-disabled') === 'true';

            results.push({
                id,

                tag: el.tagName.toLowerCase(),
                role: el.getAttribute('role'),
                type: el.getAttribute('type'),

                name: getAccessibleName(el),

                placeholder: el.getAttribute('placeholder'),
                name_attribute: el.getAttribute('name'),
                href: el.tagName === 'A' ? el.href : null,

                section: getSection(el),
                parent_text: parentText,

                disabled,

                checked:
                    typeof el.checked === 'boolean'
                        ? el.checked
                        : null,

                expanded: el.getAttribute('aria-expanded'),
                selected: el.getAttribute('aria-selected'),

                contenteditable: el.isContentEditable,

                bounds: {
                    x: Math.round(rect.x),
                    y: Math.round(rect.y),
                    width: Math.round(rect.width),
                    height: Math.round(rect.height)
                }
            });
        });

        // Second pass: identify nested interactive elements.
        const idMap = new Map(
            results.map(item => [item.id, item])
        );

        results.forEach(item => {
            const el = document.querySelector(
                `[data_agent_id="${item.id}"]`
            );

            const parentInteractive = el?.parentElement?.closest(
                '[data_agent_id]'
            );

            item.parent_interactive_id = parentInteractive
                ? Number(parentInteractive.getAttribute('data_agent_id'))
                : null;
        });

        return results;
    }
    """

    return page.evaluate(script)


SUBTASK_COMPLETION_DECIDER = '''
You are state decider component of a browser automation agent.
You will recieve:
- Subtask Description
- A list of executed tasks taken to accompalish that task.
- Previously executed Task
- current web_page_url : The URL currently opened in the browser.

Your task is to decide whether the subtask is completed or not based on the subtask description and execution history and the current web_page.
You need to return "True" if it is completed and "False" if it is not.
DO NOT RETURN ANYTHING ELSE THAN THE WORD True or False.
expected output : 
True/False
'''

CREATE_SUBTASK_PROMPT = '''
You are the planning component of a browser automation agent.

You will receive:
- The original user query.
- previously generated subtasks in "tasks" where each subtask provides information about their current status and execution outputs.
- The current webpage URL.

Your responsibility is to determine the NEXT logical subtask required to complete the user's original query. and only return the output in plain english and nothing else.

Rules: 
- Generate exactly ONE next subtask.
- consider the execution history and the query before deciding what to do next.
- The subtask must contribute directly towards completing the original user query.
- Do not assume that an action succeeded merely because it was previously requested. Use its execution output.

THINKING PROCESS:
- based on page_content, decide what is the page about and whether everything is alright, it might be invalid page or you might not be logged in, you might be stuck in a loop,
try to think what next action should take you more toward the subtask !
- you might just be at a wrong url as well !
- you might be doing something completely irrelavant, make sure you think about ur execution history and make a better subtask which contribute to the automation.


examples of subtasks:
- Opening instagram.com
- Searching for xyz product on amazon.
- navigating to facebook.com.
Return only the next subtask description in plain English.
'''

CREATE_INITIAL_SUBTASK = '''
You are the planning component of a browser automation agent.

You will receive:
- The original user query.
- The current webpage URL.

Your responsibility is to determine the FIRST logical subtask required to complete the user's original query. and only return the output in plain english and nothing else.

Rules:
- generate only the initial subtask required and the subtask must contribute directly towards completing the original user query.
STRICT OUTPUT RULES:
1. If action is "locate":
   - text MUST contain the destination URL.
   - selected_element_id MUST be -1.
2. If action is "click":
   - text MUST be an empty string "".
   - selected_element_id MUST contain the exact element ID.
3. If action is "fill":
   - text MUST contain the value to enter.
   - selected_element_id MUST contain the exact element ID.


IMPORTANT:
- Never output "none", "null", "None", or "N/A" as text.
- Empty string "" is the ONLY valid representation of no text.
- These are strict requirements, not suggestions.


examples of subtasks:
- Opening instagram.com
- Searching for xyz product on amazon.
- navigating to facebook.com.
Return only the next subtask description in plain English.
'''

CREATE_NEXT_ACTION = '''
You are next action deciding Component of a browser.
You are provided with the following:
1. current web_page_url
   The URL currently opened in the browser.

2.  A list of currently visible and interactable
   webpage elements, each having a unique ID.
   This may be empty.

3. sub_task:
   The current goal that the agent must accomplish.

4.executed_actions:
   Actions already performed while attempting
   to complete the current subtask, including
   their execution results. this maybe empty

YOUR RESPONSIBILITY:
Determine the NEXT SINGLE browser action required
to make progress towards completing the given subtask.

AVAILABLE ACTIONS:

1. locate:
   Navigate to a specific webpage URL.

2. click:
   Click a specific element identified by its ID
   in page_content.

3. fill:
   Fill a text input, textarea or contenteditable
   element with the required text.

THINKING PROCESS:
- based on page_content, decide what is the page about and whether everything is alright, it might be invalid page or you might not be logged in, you might be stuck in a loop,
try to think what next action should take you more toward the subtask !

DECISION RULES:
1. Carefully examine the subtask, current URL,
   page contents and execution history before
   selecting an action.

2. If the current webpage is irrelevant to the
   subtask, navigate to the appropriate webpage.

3. If the current webpage is relevant, examine the given page_content for the 
   available elements and identify the element
   required for the next operation.

4. Select only element IDs explicitly present
   in page_content. Never invent or guess IDs.
5. Use click only when activating the selected
   element is necessary.

6. Use fill only when entering text into an
   appropriate input element is necessary.

7. When using fill, provide the exact intended text in 'text' field.
   Do not invent user information or preferences.

8. Consider executed_actions carefully.
   Do not repeat successfully executed actions
   unless there is a specific reason to do so.

9. Never assume an action succeeded merely because
   it appears in executed_actions. Examine its
   execution result.

10. If the required element is unavailable,
    do not select an unrelated element.
    Return none and explain what is missing.

11. Please think before selection and Do not select unrelated elements just to make progress.

ELEMENT COMPATIBILITY RULES:
1. Before selecting an element, inspect:
   - tag
   - type
   - role
   - text
   - placeholder
   - aria_label
   - labels
   - is_disabled

2. The element's visible text does not determine
   whether it is fillable.

3. Never select an element merely because its text
   resembles the requested search query.

4. If no appropriate element exists, do not invent
   an action or select an unrelated element.
'''

TASK_COMPLETEION_DECIDER = '''
You are state decider component of a browser automation agent. The given automation task is divided into various subtasks.
You will recieve:
- list of all the subtasks which have been created till now. each entry in the list contains all the information about the given subtask.
- current_web_page url : the url currently opened in the browser.
- visual content of the webpage currently
- a list of all the interactable elements of the current page.

Your task is to decide whether the task is completed or not based on the subtask descriptions and execution history and the current web_page contents along with the text content and interactive elements.
You need to return "True" if it is completed and "False" if it is not.
If this task is completed, it marks the end of the original query automation and that the current automation task is being accompalished successfully.
DO NOT RETURN ANYTHING ELSE THAN THE WORD True or False.
expected output : 
True/False

'''

CREATE_NEXT_ACTION_ERROR = '''
You are next action deciding Component of a browser.
You are provided with the following:
0. Your previous output which had an error along with the error message ! 
1. current web_page_url
   The URL currently opened in the browser.

2.  A list of currently visible and interactable
   webpage elements, each having a unique ID.
   This may be empty.

3. sub_task:
   The current goal that the agent must accomplish.

4.executed_actions:
   Actions already performed while attempting
   to complete the current subtask, including
   their execution results. this maybe empty

YOUR RESPONSIBILITY:
In your previous output you made an error, and You need to recheck your answer in order to fix that error,
Determine the NEXT SINGLE browser action required to make progress towards completing the given subtask.

AVAILABLE ACTIONS:

1. locate:
   Navigate to a specific webpage URL.

2. click:
   Click a specific element identified by its ID
   in page_content.

3. fill:
   Fill a text input, textarea or contenteditable
   element with the required text.


DECISION RULES:
1. Carefully examine the subtask, current URL,
   page contents and execution history before
   selecting an action.

2. If the current webpage is irrelevant to the
   subtask, navigate to the appropriate webpage.

3. If the current webpage is relevant, examine the given page_content for the 
   available elements and identify the element
   required for the next operation.

4. Select only element IDs explicitly present
   in page_content. Never invent or guess IDs.
5. Use click only when activating the selected
   element is necessary.

6. Use fill only when entering text into an
   appropriate input element is necessary.

7. When using fill, provide the exact intended text in 'text' field.
   Do not invent user information or preferences.

8. Consider executed_actions carefully.
   Do not repeat successfully executed actions
   unless there is a specific reason to do so.

9. Never assume an action succeeded merely because
   it appears in executed_actions. Examine its
   execution result.

10. If the required element is unavailable,
    do not select an unrelated element.
    Return none and explain what is missing.

11. Please think before selection and Do not select unrelated elements just to make progress.

ELEMENT COMPATIBILITY RULES:
1. Before selecting an element, inspect:
   - tag
   - type
   - role
   - text
   - placeholder
   - aria_label
   - labels
   - is_disabled

2. The element's visible text does not determine
   whether it is fillable.

3. Never select an element merely because its text
   resembles the requested search query.

4. If no appropriate element exists, do not invent
   an action or select an unrelated element.
'''
execution_subtask_cnt = 0

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    default_context = browser.contexts[0]
    pages = default_context.pages
    page = default_context.pages[0] if default_context.pages else default_context.new_page()

    while True: # main error execution loop
        if execution_subtask_cnt == 0:
                #output = client.chat(model=MODEL, messages=[
                #        {'role':'system', 'content': CREATE_INITIAL_SUBTASK},
               #       {'role':'user', 'content': f"curr_url : {curr_page_url}, query : {query}"}
                #])

                messages=[
                        {'role':'system', 'content': CREATE_INITIAL_SUBTASK},
                        {'role':'user', 'content': f"curr_url : {curr_page_url}, query : {query}"}
    
                ]
                debug_message(messages)
                subt = ask_chatgpt(messages)

                subtask = Subtask(subt)
                execution_subtask_cnt += 1

        elif execution_subtask_cnt > 0:
                messages = [{'role':'system', 'content': TASK_COMPLETEION_DECIDER},
                           {'role': 'user', 'content': f"user_query : {main_task.query}\n ALL SUBTASKS LIST : {main_task.tasks} \n Current_page_url : {curr_page_url} \n current_page_visual_context : {extract_visible_text(page)} "}
                           ]
                
                debug_message(messages)
                res = ask_chatgpt(messages).strip().lower()
                if res not in ['true', 'false']:
                  raise ValueError("Invalid completion response")
                main_task.completed = res == 'true'
                if main_task.completed:
                   print("AUTOMATION SUCESSFULLY COMPLETED")
                   break
                
                

                page_content = extract_elements(page)
                task_history = [vars(task) for task in main_task.tasks]
                print(task_history)
               #  output = client.chat(model=MODEL, messages=[
               #          {'role':'system', 'content': CREATE_SUBTASK_PROMPT},
               #          {'role':'user', 'content': f"curr_url : {curr_page_url}, query : {query}"},
               #          {'role':'user', 'content': f"subtask_history : {task_history}, current_page_contents : {page_content} "}
               #  ])
                messages=[
                        {'role':'system', 'content': CREATE_SUBTASK_PROMPT},
                        {'role':'user', 'content': f"curr_url : {curr_page_url}, query : {query}"},
                        {'role':'user', 'content': f"subtask_history : {task_history}, current_page_contents : {page_content} "},
                        {'role':'user', 'content': f"curr_page visual text content : {extract_visible_text(page)}"}
                ]
                debug_message(messages)
                subt = ask_chatgpt(messages)
                subtask = Subtask(subt)
                execution_subtask_cnt += 1

        print(vars(subtask))
        # execution of subtask phase 
        # So like right now. What I have is basically. I have a sub task. And and. I want to give the model my so task. Along with page contents. Along with. Current web page URL. And all the previously occurred tasks. And model's job is to just. Provide that next action. Is not it too easy? But wait, even here. Think more. So like you will provide. Model a certain action. There can be errors in the action. Like I mean to say that you have an action. You need to handle the errors..ro But first. It is for true that. Yeah, I will decide what to do next. From that natural language. Don't think the next action. Based on the current page content. Is it clear? Yes, it is. So just provide. Yeah, these things and make sure that the action it give is more reliable. It doesn't address any error No it does not. Or it does it. It's a bit complex thing. Because what it needs to tell is. Like if you have this particular seat. Then you need to either locate. Or slept or whatever stuff

        error = ""
        while not subtask.completed:
                curr_page_url = page.url
                page_content = extract_elements(page)

                if error:
                        # output = client.chat(model=MODEL, messages=[
                        #         {'role': 'system', 'content' : CREATE_NEXT_ACTION_ERROR},
                        #         {'role': 'user', 'content': f"current_web_page_url : {curr_page_url}, \n page_content : {page_content} \n sub_task :{subtask.description} \n  previously_execute_subtask : {subtask.previously_executed_task} \n {vars(subtask)} \n executed_actions : {subtask.executed_tasks}, \n subtask_status : {subtask.sub_task_status}"},
                        #         {'role': "user", 'content': f"error encountered while trying to generate output last time : {error}\n your previous response full of error : {subtask.previously_executed_task}"}
                        # ],
                        # format = NextAction.model_json_schema())
                        messages=[
                                {'role': 'system', 'content' : CREATE_NEXT_ACTION_ERROR},
                                {'role': 'user', 'content': f"current_web_page_url : {curr_page_url}, \n page_content : {page_content} \n sub_task :{subtask.description} \n  previously_execute_subtask : {subtask.previously_executed_task} \n {vars(subtask)} \n executed_actions : {subtask.executed_tasks}"},
                                {'role': "user", 'content': f"error encountered while trying to generate output last time : {error}\n your previous response full of error : {subtask.previously_executed_task}"},
                                {'role': 'user', 'content': f"OUTPUT FORMAT : {NextAction.model_json_schema()}"},
                                {'role':'user', 'content': f"curr_page visual text content : {extract_visible_text(page)}"}
                        ]


                        debug_message(messages)
                        output = ask_chatgpt(messages)
                        error = ''
                else:
                        # output = client.chat(model=MODEL, messages=[
                        #         {'role': 'system', 'content' : CREATE_NEXT_ACTION},
                        #         {'role': 'user', 'content': f"current_web_page_url : {curr_page_url}, \n page_content : {page_content} \n sub_task :{subtask.description} \n  previously_execute_subtask : {subtask.previously_executed_task} \n {vars(subtask)} \n executed_actions : {subtask.executed_tasks}, \n subtask_status : {subtask.sub_task_status}"}
                        # ],
                        # format = NextAction.model_json_schema())

                        messages=[
                                {'role': 'system', 'content' : CREATE_NEXT_ACTION},
                                {'role': 'user', 'content': f"current_web_page_url : {curr_page_url}, \n page_content : {page_content} \n sub_task :{subtask.description} \n  previously_execute_subtask : {subtask.previously_executed_task} \n {vars(subtask)} \n executed_actions : {subtask.executed_tasks} "},
                                {'role': 'user', 'content': f"OUTPUT FORMAT : {NextAction.model_json_schema()}"},
                                {'role':'user', 'content': f"curr_page visual text content : {extract_visible_text(page)}"}
                        ]


                        debug_message(messages)
                        output = ask_chatgpt(messages)


               # raw_response = output['message']['content']
                raw_response = output.replace(r'\_', '_')
                #pydantic validation 
                try:
                        subtask.previously_executed_task = raw_response
                        next_action = NextAction.model_validate_json(raw_response)
                except ValidationError as e:
                        print(e)
                        error = e
                        continue
                        
                print(next_action)

                #semantic error validation 
                validate_action_compatibility(next_action, page_content)

                
                # automation using playwright
                if next_action.action == "locate":
                        navigate_url(next_action.text)
                        subtask.previously_executed_task = f"Sucessfully located the page {next_action.text}"
                        subtask.executed_tasks.append(subtask.previously_executed_task)
                        curr_page_url = next_action.text
                elif next_action.action in ["click", "fill"]:
                        target_elem = page_content[next_action.selected_element_id]
                        locator_elem = page.locator(
                                f'[data_agent_id="{next_action.selected_element_id}"]'
                        )
                        if next_action.action == "click":
                                locator_elem.click()
                                subtask.previously_executed_task = f"Sucessfully click on the element {target_elem} the page {curr_page_url}"
                                subtask.executed_tasks.append(subtask.previously_executed_task)
                        else:

                                locator_elem.fill(next_action.text)
                                subtask.previously_executed_task = f"Sucessfully filled the text {next_action.text} on the element {target_elem}"
                                subtask.executed_tasks.append(subtask.previously_executed_task)
                
                
                
                # decide whether the subtask is completed or whether there is still action remaining 
               # output = client.chat(model=MODEL, )
                messages=[
                    {'role':'system', 'content':SUBTASK_COMPLETION_DECIDER},
                    {'role': 'user', 'content': f"subtask Description : {subtask.description} \n executed tasks list : {subtask.executed_tasks}, previously_executed task taken towards subtask : {subtask.previously_executed_task}"},
                    {'role':'user', 'content': f"curr_url : {curr_page_url} curr_page visual text content : {extract_visible_text(page)}"}
                 ]

                debug_message(messages)
                result = ask_chatgpt(messages).strip().lower()

                if result not in ("true", "false"): 
                  raise ValueError("Invalid completion response")

                subtask.completed = result == "true"
                if subtask.completed:
                    main_task.tasks.append(subtask)