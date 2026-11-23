'''A Browser Automation Agent, which works with multiple tabs of a browser efficiently to perform a given automation.'''
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
import sys
from prompts import SUBTASK_OUTPUT_FEEDER, SUBTASK_COMPLETION_DECIDER, CREATE_SUBTASK_PROMPT, CREATE_INITIAL_SUBTASK, CREATE_NEXT_ACTION, TASK_COMPLETEION_DECIDER, CREATE_NEXT_ACTION_ERROR

# Input Query that the browser automation should perform
query = input("What should i do > ")
use_local_llm = True

# BROWSER TABS MANAGEMENT
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

def current_browser_state(browser_window):
    '''Outputs the metadata of all the opened tabs along with their tab_ids and the currently opened url'''
    tabs = []
    for tab in browser_window.opened_tabs:
        tabs.append({
                "tab_id": tab.tab_id,
                "url": tab.page.url,
                "title": tab.page.title(),
                "is_current": (
                    tab.tab_id ==
                    browser_window.current_visible_tab_id
                )
            })
    return tabs

def corrected_tab(tab_id, browser_window):
    '''Returns the page corresponding to a given tab_id'''
    for tab in browser_window.opened_tabs:
        if tab.tab_id == tab_id:
            return tab.page
    raise ValueError("Given Tab is not found in the list of currently opened tabs")


def ask_chatgpt(message):
   """Instead of harneshing local llms, use the cloud chatgpt llm to get response thus a free alternative for higher prices of cloud llms APIs."""
   chatgpt_page = None
   try:
      chatgpt_page = default_context.new_page()
      chatgpt_page.goto(
         "https://chatgpt.com",
         wait_until="domcontentloaded"
      )
      
      # paste the query and messages 
      locator_elem = chatgpt_page.get_by_placeholder("Ask ChatGPT")
      locator_elem.wait_for(state="visible",timeout=30000)

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


# Local LLM alternative option
client = Client(
    host='http://localhost:11434',
)
#MODEL = 'qwen3.5:4b' # download a model in ollama and provide the name of the model here 
MODEL = 'gemma4:e4b'

curr_page_url = '' # variable holding the url of the current tab


class Task:
   '''Class holding the task and all the subtasks created during the runtime'''
   def __init__(self, query, iscompleted=False) -> None:
        self.tasks = []
        self.query = query
        self.completed = iscompleted
main_task = Task(query)

class Subtask:
    '''Class holding metadata about each subtask required during the execution'''
    _counter = 1
    def __init__(self, endgoal, description, dependent_tab = -1, prev_exec_task = None, output = None, completed= False,) -> None:
        self.subtask_id = Subtask._counter
        Subtask._counter += 1
        self.description = description
        self.dependent_tab = dependent_tab 
        self.tab_id = []
        self.endgoal = endgoal
        self.previously_executed_task = prev_exec_task
        self.executed_tasks = []
        self.sub_task_execution_output = output
        self.completed = completed

class Subtask_think(BaseModel):
    '''Output Format of the subtask decider llm query'''
    description : Annotated[str, Field(
        description=("Description of the new subtask, along with considering the previous subtask's outputs ( and including them if required) in consideration. If no previous subtask is there implies this is the first subtask.")
    )]
    dependent_tab : Annotated[int, Field(
        description=("Exact id of the tab the current task is dependent on, If the current subtask is dependent on one of the previous subtask's output i.e. previous tab, it must must that tab_id. Leave it empty if the current subtask is independent.")
    )]
    endgoal : Annotated[str, Field(
        description=("The expected output of the current subtask.")
    )
]
class Decision_format(BaseModel):
    """Output format specifier of the final decision made by the subtask completion decider"""
    decision : Annotated[bool, Field(
        description=(
            "Your task is to decide whether the thing is completed or not "
            "You need to return 'True' if it is completed and 'False' if it is not."
        )
    )]

                
class NextAction(BaseModel):
        '''Output Format of the next action decider llm query'''
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
         Literal['click', 'fill', 'locate', 'switch'], 
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
                "The exact text to enter when action is 'fill'. or url when action is 'locate' or tab_id which to switch on when action is switch"
                "Preserve the intended spelling, capitalization, and content. "
                "if action is 'locate' provide the exact url browser should redirect to for further execution of script"
                "If action is switch provide the exact tab_id which the task should switch to from opened tabs based on subtask."
                "Must be emptry string for 'click'."
                "IT MUST PROVIDE NOTHING ELSE AND JUST EITHER URL OR THE EXACT TEXT TO FILL IN"
            )
        ) 
    ] 

        @model_validator(mode="after")
        def validate_action_fields(self):
            if self.text.strip().lower() in ["none", "null"]:
                  raise ValueError("Never use 'none' or 'null' as text. Use an empty string.")
            if self.action == "fill" or self.action == "locate" or self.action == "switch":
                  if not self.text:
                           raise ValueError("Text is not provided when action is fill/locate/switch.")
            if self.action == "switch":
                found = False
                for tab in browser_window.opened_tabs:
                    if int(self.text) == tab.tab_id:
                        found = True
                if not found:    
                    print(current_browser_state(browser_window))
                    raise ValueError("Target tab is not available in the list of currently opened tabs.")
            if self.action == "locate":
               if self.text.rstrip("/") == curr_subtask_page.url.rstrip("/"):
                  raise ValueError("Already on this URL. Choose an action on the current page.")

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
   '''Extracts the visible text from the page'''
   try:
      visible_text = page.locator("body").inner_text(timeout=5000)
      return visible_text.strip()[:1000]
   except Exception as e:
      print(f"error during extraction {e}")
      return ""
   

def validate_action_compatibility(action, page_content):
   '''Validates the element if it is present on the page or not'''
   if action.action == "locate" or action.action == "switch":
        return

   element = next((
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
      
def navigate_url(url,page):
    '''navigates to a particular url on the given page'''
    while True: 
        try:
            page.goto(url,wait_until="load", timeout=10000)
            print(f"Sucessfully Loaded the page {url}")
            break
        except PlaywrightError as e:
            if e.name == "ERR_NETWORK_CHANGED" or e.name == "ERR_INTERNET_DISCONNECTED":
                print(f"Network error occurred. Retrying...")
                time.sleep(2)

def extract_elements(page):
    '''extracts interactable elements from the page to be used in the script'''
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

execution_subtask_cnt = 0
error = ''
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    default_context = browser.contexts[0]
    browser_window = BrowserWindow(default_context)
    
    while True: # main execution loop
        if len(error) != 0:
                task_history = [vars(task) for task in main_task.tasks]
                i = 0
                completion_error = ''
                while i == 0 or len(completion_error) != 0:
                    messages = [{'role':'system', 'content': TASK_COMPLETEION_DECIDER},
                            {'role': 'user', 'content': f"user_query : {main_task.query}\n ALL SUBTASKS LIST : {task_history} \n Current_page_url : {curr_page_url} \n current_page_visual_context : {extract_visible_text(curr_subtask_page)}  currently_opened_tab_ids with urls currently opeend : {current_browser_state(browser_window)}"},
                            ]
                    if completion_error:
                        messages.append({'role':'user', 'content': f"{completion_error}"})
                    if use_local_llm:
                        response = client.chat(model=MODEL, messages=messages , format=Decision_format.model_json_schema())
                        res = response['message']['content']
                        print(res)
                        res = Decision_format.model_validate_json(res).decision
                        completion_error = ''
                        main_task.completed = res == True
                    else:
                        res = ask_chatgpt(messages).strip().lower()
                        if res not in ['true', 'false']:
                            completion_error = "INVALID COMPLETION RESPONSE IN THE COMPLETION RESPONSE YOU RETURN SOMETHING ELSE THAN TRUE OR FALSE"
                            print("INVALID COMPLETION RESPONSE IN THE COMPLETION RESPONSE YOU RETURN SOMETHING ELSE THAN TRUE OR FALSE")
                            continue
                    i += 1
                    if main_task.completed:
                        print("AUTOMATION SUCESSFULLY COMPLETED")
                        sys.exit() 

                page_content = extract_elements(curr_subtask_page)
                task_history = [vars(task) for task in main_task.tasks]
                print(task_history)
                # uncomment to use local llm instead of cloud
                #  output = client.chat(model=MODEL, messages=[
                #          {'role':'system', 'content': CREATE_SUBTASK_PROMPT},
                #          {'role':'user', 'content': f"curr_url : {curr_page_url}, query : {query}"},
                #          {'role':'user', 'content': f"subtask_history : {task_history}, current_page_contents : {page_content} "}
                #  ])
                messages=[
                        {'role':'system', 'content': CREATE_SUBTASK_PROMPT},
                        {'role':'user', 'content': f"curr_url : {curr_page_url}, query : {main_task.query}"},
                        {'role':'user', 'content': f"subtask_history : {task_history}, current_page_contents : {page_content} "},
                        {'role':'user', 'content': f"curr_page visual text content : {extract_visible_text(curr_subtask_page)} \n currently_opened_tab_ids with urls currently opeend : {current_browser_state(browser_window)}"}
                ]
                if use_local_llm:
                    res = client.chat(model=MODEL, messages=messages)
                    raw_response = res['message']['content']
                    print(raw_response)
                else:
                    raw_response = ask_chatgpt(messages)
                    raw_response = raw_response.replace(r'\_', '_')
                    raw_response = raw_response.replace(r'\[', '[')
                    raw_response = raw_response.replace(r'\]', ']')
                subt = Subtask_think.model_validate_json(raw_response)
                description = subt.description
                endgoal = subt.endgoal 
                subtask = Subtask(endgoal, description)
                subtask.dependent_tab = subt.dependent_tab
                execution_subtask_cnt += 1

                print(vars(subtask))
                if subtask.dependent_tab != -1:
                    try:
                        curr_subtask_page = corrected_tab(subtask.dependent_tab, browser_window)
                        error = ''
                    except ValueError as e:
                        print(e)
                        error = e
                        continue
                else:
                    curr_subtask_page = browser_window.create_new_tab()
        else:
            if execution_subtask_cnt == 0:
                if use_local_llm:
                    messages=[
                        {'role':'system', 'content': CREATE_INITIAL_SUBTASK},
                        {'role':'user', 'content': f"curr_url : {curr_page_url}, query : {query}currently_opened_tab_ids with urls currently opeend : {current_browser_state(browser_window)}"},
                        ]
                    res = client.chat(model=MODEL, messages=messages, format=Subtask_think.model_json_schema() )
                    raw_response = res['message']['content']
                    print(raw_response)
                else:
                    messages=[
                            {'role':'system', 'content': CREATE_INITIAL_SUBTASK},
                            {'role':'user', 'content': f"curr_url : {curr_page_url}, query : {query}currently_opened_tab_ids with urls currently opeend : {current_browser_state(browser_window)}"},
                            {'role': 'user', 'content': f"OUTPUT FORMAT : {Subtask_think.model_json_schema()}"}
                    ]
                    raw_response = ask_chatgpt(messages)
                    raw_response = raw_response.replace(r'\_', '_')
                    raw_response = raw_response.replace(r'\[', '[')
                    raw_response = raw_response.replace(r'\]', ']')
                subt = Subtask_think.model_validate_json(raw_response)
                description = subt.description
                endgoal = subt.endgoal 
                subtask = Subtask(endgoal, description)
                subtask.dependent_tab = subt.dependent_tab
                execution_subtask_cnt += 1
                curr_subtask_page = browser_window.create_new_tab()


            elif execution_subtask_cnt > 0:
                task_history = [vars(task) for task in main_task.tasks]
                messages = [{'role':'system', 'content': TASK_COMPLETEION_DECIDER},
                            {'role': 'user', 'content': f"user_query : {main_task.query}\n ALL SUBTASKS LIST : {task_history} \n Current_page_url : {curr_page_url} \n current_page_visual_context : {extract_visible_text(curr_subtask_page)}  currently_opened_tab_ids with urls currently opeend : {current_browser_state(browser_window)}"},
                                {'role': 'user', 'content': f"OUTPUT FORMAT : {Subtask_think.model_json_schema()}"}
                            ]
                
                i = 0
                completion_error = ''
                while i == 0 or len(completion_error) != 0:
                    if completion_error:
                        messages = [{'role':'system', 'content': TASK_COMPLETEION_DECIDER},
                                    {'role': 'user', 'content': f"user_query : {main_task.query}\n ALL SUBTASKS LIST : {task_history} \n Current_page_url : {curr_page_url} \n current_page_visual_context : {extract_visible_text(curr_subtask_page)}  currently_opened_tab_ids with urls currently opeend : {current_browser_state(browser_window)}"},
                                        {'role': 'user', 'content': f"OUTPUT FORMAT : {Subtask_think.model_json_schema()}"},
                                        {'role':'user', 'content': f"ERROR MESSAGE IN YOUR PREVIOUS RESPONSE : {completion_error}"}
                                    ]
                    if use_local_llm:
                        if completion_error:
                            messages = [{'role':'system', 'content': TASK_COMPLETEION_DECIDER},
                                        {'role': 'user', 'content': f"user_query : {main_task.query}\n ALL SUBTASKS LIST : {task_history} \n Current_page_url : {curr_page_url} \n current_page_visual_context : {extract_visible_text(curr_subtask_page)}  currently_opened_tab_ids with urls currently opeend : {current_browser_state(browser_window)}"},
                                            {'role':'user', 'content': f"ERROR MESSAGE IN YOUR PREVIOUS RESPONSE : {completion_error}"}
                                        ]
                        else:
                            messages = [{'role':'system', 'content': TASK_COMPLETEION_DECIDER},
                                {'role': 'user', 'content': f"user_query : {main_task.query}\n ALL SUBTASKS LIST : {task_history} \n Current_page_url : {curr_page_url} \n current_page_visual_context : {extract_visible_text(curr_subtask_page)}  currently_opened_tab_ids with urls currently opeend : {current_browser_state(browser_window)}"},
                                ]
                        response = client.chat(model=MODEL, messages=messages, format=Decision_format.model_json_schema())
                        reslt = response['message']['content']
                        res = Decision_format.model_validate_json(reslt).decision
                        main_task.completed = res == True
                        print(res)
                    else:
                        res = ask_chatgpt(messages).strip().lower()
                        if res not in ['true', 'false']:
                            completion_error = "INVALID COMPLETION RESPONSE IN THE COMPLETION RESPONSE YOU RETURN SOMETHING ELSE THAN TRUE OR FALSE"
                            print("INVALID COMPLETION RESPONSE IN THE COMPLETION RESPONSE YOU RETURN SOMETHING ELSE THAN TRUE OR FALSE")
                            continue
                            main_task.completed = res == 'true'
                    i += 1
                    completion_error = ''
                    if main_task.completed:
                        print("AUTOMATION SUCESSFULLY COMPLETED")
                        sys.exit() 

                page_content = extract_elements(curr_subtask_page)
                task_history = [vars(task) for task in main_task.tasks]
                print(task_history)
                if use_local_llm:
                    output = client.chat(model=MODEL, messages=[
                            {'role':'system', 'content': CREATE_SUBTASK_PROMPT},
                            {'role':'user', 'content': f"curr_url : {curr_page_url}, query : {query}"},
                            {'role':'user', 'content': f"subtask_history : {task_history}, current_page_contents : {page_content} "},
                            {'role':'user', 'content': f"curr_page visual text content : {extract_visible_text(curr_subtask_page)} \n currently_opened_tab_ids with urls currently opeend : {current_browser_state(browser_window)}"}
                    ])
                    raw_response = output['message']['content']
                    print(raw_response)
                else:
                    messages = [
                            {'role':'system', 'content': CREATE_SUBTASK_PROMPT},
                            {'role':'user', 'content': f"curr_url : {curr_page_url}, query : {main_task.query}"},
                            {'role':'user', 'content': f"subtask_history : {task_history}, current_page_contents : {page_content} "},
                            {'role':'user', 'content': f"curr_page visual text content : {extract_visible_text(curr_subtask_page)} \n currently_opened_tab_ids with urls currently opeend : {current_browser_state(browser_window)}"}
                    ]
                    raw_response = ask_chatgpt(messages)
                    raw_response = raw_response.replace(r'\_', '_')
                    raw_response = raw_response.replace(r'\[', '[')
                    raw_response = raw_response.replace(r'\]', ']')
                subt = Subtask_think.model_validate_json(raw_response)
                description = subt.description
                endgoal = subt.endgoal 
                subtask = Subtask(endgoal, description)
                subtask.dependent_tab = subt.dependent_tab
                execution_subtask_cnt += 1

                print(vars(subtask))
                
                if subtask.dependent_tab != -1:
                    try:
                        curr_subtask_page = corrected_tab(subtask.dependent_tab, browser_window)
                    except ValueError as e:
                        print(e)
                        continue
                else:
                    curr_subtask_page = browser_window.create_new_tab()
            
        error = ""
        while not subtask.completed:
                curr_page_url = curr_subtask_page.url
                page_content = extract_elements(curr_subtask_page)

                if error:
                        print(f"ERROR IN NEXT SUBTASK ACTION #DEBUG {error}")
                        if use_local_llm:
                            message = [
                                    {'role': 'system', 'content' : CREATE_NEXT_ACTION_ERROR},
                                    {'role': 'user', 'content': f"current_web_page_url : {curr_page_url}, \n page_content : {page_content} \n sub_task :{subtask.description} \n  previously_execute_subtask : {subtask.previously_executed_task} \n {vars(subtask)} \n executed_actions : {subtask.executed_tasks}"},
                                    {'role': "user", 'content': f"error encountered while trying to generate output last time : {error}\n your previous response full of error : {subtask.previously_executed_task}"},
                                    {'role':'user', 'content': f"curr_page visual text content : {extract_visible_text(curr_subtask_page)}, users_original_query : {main_task.query}currently_opened_tab_ids with urls currently opeend : {current_browser_state(browser_window)}"}
                            ]

                            print(f"#DEBUG INPUT MESSAGE \n\n {message} \n\n\n")
                            output_res = client.chat(model=MODEL, messages = message, format = NextAction.model_json_schema())
                            raw_response = output_res['message']['content']
                            print(raw_response)
                        else:
                            messages=[
                                    {'role': 'system', 'content' : CREATE_NEXT_ACTION_ERROR},
                                    {'role': 'user', 'content': f"current_web_page_url : {curr_page_url}, \n page_content : {page_content} \n sub_task :{subtask.description} \n  previously_execute_subtask : {subtask.previously_executed_task} \n {vars(subtask)} \n executed_actions : {subtask.executed_tasks}"},
                                    {'role': "user", 'content': f"error encountered while trying to generate output last time : {error}\n your previous response full of error : {subtask.previously_executed_task}"},
                                    {'role': 'user', 'content': f"OUTPUT FORMAT : {NextAction.model_json_schema()}"},
                                    {'role':'user', 'content': f"curr_page visual text content : {extract_visible_text(curr_subtask_page)}, users_original_query : {main_task.query}currently_opened_tab_ids with urls currently opeend : {current_browser_state(browser_window)}"}
                            ]
                            output = ask_chatgpt(messages)
                            raw_response = output.replace(r'\_', '_')
                        error = ''
                        print(f"ERROR IN NEXT SUBTASK ACTION #DEBUG {error}")
                else:
                        if use_local_llm:
                            res = client.chat(model=MODEL, messages=[
                                    {'role': 'system', 'content' : CREATE_NEXT_ACTION},
                                    {'role': 'user', 'content': f"current_web_page_url : {curr_page_url}, \n page_content : {page_content} \n sub_task :{subtask.description} \n  previously_execute_subtask : {subtask.previously_executed_task} \n {vars(subtask)} \n executed_actions : {subtask.executed_tasks}"}
                            ],
                            format = NextAction.model_json_schema())
                            raw_response = res['message']['content']
                            print(raw_response)
                            
                        else:
                            messages=[
                                    {'role': 'system', 'content' : CREATE_NEXT_ACTION},
                                    {'role': 'user', 'content': f"current_web_page_url : {curr_page_url}, \n page_content : {page_content} \n sub_task :{subtask.description} \n  previously_execute_subtask : {subtask.previously_executed_task} \n {vars(subtask)} \n executed_actions : {subtask.executed_tasks} currently_opened_tab_ids with urls currently opeend : {current_browser_state(browser_window)}"},
                                    {'role': 'user', 'content': f"OUTPUT FORMAT : {NextAction.model_json_schema()}"},
                                    {'role':'user', 'content': f"curr_page visual text content : {extract_visible_text(curr_subtask_page)}, main_user query : {main_task.query}\n currently_opened_tab_ids with urls currently opeend : {current_browser_state(browser_window)}"}
                            ]
                            output = ask_chatgpt(messages)
                            raw_response = output.replace(r'\_', '_')
                try:
                        #pydantic validation 
                        subtask.previously_executed_task = raw_response
                        next_action = NextAction.model_validate_json(raw_response)
                        #semantic error validation 
                        validate_action_compatibility(next_action, page_content)
                except (ValidationError, ValueError) as e:
                        print(e)
                        error = str(e)
                        continue
                print(next_action)

                # automation using playwright
                if next_action.action == "switch":
                    curr_subtask_page = browser_window.switch_tab(int(next_action.text))
                    subtask.previously_executed_task = f"Sucessfully switched to the tab with id {next_action.text}"
                    subtask.executed_tasks.append(subtask.previously_executed_task)
                if next_action.action == "locate":
                        curr_subtask_page = browser_window.create_new_tab()
                        navigate_url(next_action.text, curr_subtask_page)
                        subtask.previously_executed_task = f"Sucessfully located the page {next_action.text}"
                        subtask.executed_tasks.append(subtask.previously_executed_task)
                        curr_page_url = next_action.text
                elif next_action.action in ["click", "fill"]:
                        target_elem = page_content[next_action.selected_element_id]
                        locator_elem = curr_subtask_page.locator(
                                f'[data_agent_id="{next_action.selected_element_id}"]'
                        )
                        if locator_elem.count() < 1:
                           error = "Page rerendered and thus selected element is not found on the page."
                           print(error)
                           error = "Page rerendered and thus selected element is not found on the page."
                           continue

                        if next_action.action == "click":
                                locator_elem.click()
                                subtask.previously_executed_task = f"Sucessfully click on the element {target_elem} the page {curr_page_url}"
                                subtask.executed_tasks.append(subtask.previously_executed_task)
                        else:
                                locator_elem.fill(next_action.text)
                                subtask.previously_executed_task = f"Sucessfully filled the text {next_action.text} on the element {target_elem}"
                                subtask.executed_tasks.append(subtask.previously_executed_task)
                
                
                # decide whether the subtask is completed or whether there is still action remaining 
                messages=[
                    {'role':'system', 'content':SUBTASK_COMPLETION_DECIDER},
                    {'role': 'user', 'content': f"subtask Description : {subtask.description} \n subtask expected endgoal : {subtask.endgoal} \n executed tasks list : {subtask.executed_tasks}, previously_executed task taken towards subtask : {subtask.previously_executed_task}"},
                    {'role':'user', 'content': f"curr_url : {curr_page_url} curr_page visual text content : {extract_visible_text(curr_subtask_page)}, original query : {main_task.query} \n currently_opened_tab_ids with urls currently opeend : {current_browser_state(browser_window)}"}
                 ]
                if use_local_llm:
                    output = client.chat(model=MODEL, messages=messages, format= Decision_format.model_json_schema(),options={"temperature": 0})
                    result = output['message']['content']
                    print(result)
                    result = Decision_format.model_validate_json(result).decision
                    subtask.completed = result == True
                else:
                    result = ask_chatgpt(messages).strip().lower()
                    if result not in ("true", "false"): 
                        raise ValueError("Invalid completion response")
                    subtask.completed = result == "true"
                if subtask.completed:
                    messages=[
                        {'role':'system', 'content':SUBTASK_OUTPUT_FEEDER},
                        {'role': 'user', 'content': f"subtask Description : {subtask.description} \n subtask expected endgoal : {subtask.endgoal} \n executed tasks list : {subtask.executed_tasks}, previously_executed task taken towards subtask : {subtask.previously_executed_task}"},
                        {'role':'user', 'content': f"curr_url : {curr_page_url} curr_page visual text content : {extract_visible_text(curr_subtask_page)}, original query : {main_task.query} currently_opened_tab_ids with urls currently opeend : {current_browser_state(browser_window)}"}
                    ]
                    if use_local_llm:
                        output = client.chat(model=MODEL, messages=messages,options={"temperature": 0})
                        res = output['message']['content']
                        print(res)
                        subtask.sub_task_execution_output = res
                    else:
                        subtask.sub_task_execution_output = ask_chatgpt(messages)
                    main_task.tasks.append(subtask)