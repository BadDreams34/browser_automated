import ollama
import playwright
import time

task_list = ''
current_page_url = ''
curr_state = []
next_task = ''
query = "Change my Leetcode profile picture to the one you might find from google."


async def extract_elements(pages):
    '''extract only meaningful information from the page, like give me clickable or interactable elements from the page at any instant and return a specific format output as dictionary'''

    # how to really work with it ? 
    # maybe work with Javascript okay firstly write a javascript 
    script = '''
() => {
let selectors = `button, textarea, radio, a, input, select, [role="button"],
        [role="link"],
        [role="checkbox"],
        [role="radio"],
        [role="switch"],
        [role="tab"],
        [role="menuitem"]`;
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
1. After generating the final answer reverify your answer by checking it again yourself and seeing if it is what is to be made.
2. Keep in mind that you are writing these tasks for an ai agent to perform a particular automation so be sure to include edge cases of making sure to be logged in and stuff like that.
'''

system_prompt_2 = '''You are an Next action thinker and structured output generator and your task is to select an element from a given list of elements : page_content. You are provided with a task_list and a curr_state. task_list contains the list of tasks in plain english. curr_state contains the performed actions till now along with additional information about whether the task is performed or if any error encountered during previous states and is of the following format : Structure of the output is like this : {next_element_id : action_description: , action : , performed_yet: Boolean, error: , error_solved: Boolean}
you can estimate the current state of where the script is currently from the curr_state. If curr_state is empty implies there is no action perfomed and it is the start of the script. Given the current state, you are provided with contents of the current page as a list of dictionary object where each object is of the form {id: which refers to the index, tagname, text, type, placeholder} and is a list of all the interactable elements of the current page along with the current_page_url your task is to select one of the interatactable element from the list page_content and return its id along with the action of click or type to be perfomed on that element, also provide that instruction in action_description: Click element 1, the output format should be like this :
>>> OUTPUT STRUCTURE START
{selected_element_id  , action_description, action: click or type  , performed_yet:  DEFAULT : False, error: "If you encounter any error ", error_solved: Default: None}
<<< OUTPUT STRUCTURE END

example output : 
{selected_element_id: 2,
action_description: Type in element 2,
action: type,
text : "hi how are you doing ",
performed_yet: False,
error: None,
error_solved: None}

Please make sure you take care of these conditions : 
1. you need to make sure you strictly follow the said output and it should be specific. Also if there is any error and the task is not performable or any other reason, please provide it in error field of the output and in that case keep the  selected_element_id as None  None action_description as String "E" None action_performed False error : The useful information which can help the program to rephrame its tasks list accordingly and provide the next actionable step clue or the change needing in task list. Make sure to be specific here .
2. It Might be worthy to rethink your own reponse before providing the final output to the user. Generate three different answers and then select one based on your own thinking. try to reason them. Also make sure the final output strictly follows the mentioned structure.
3. After generating the final answer reverify your answer by checking it again yourself and seeing if it is what is to be made.
4. In case of there is a need of typing a text provide the text which is to be typed in the text field. Make sure the output is correct.
'''

system_prompt_3 = '''Based on the given query Your task is to generate the initial_web_url on which browser should go to to start this automation. Be sure to provide the output with only a link to the initial weburl.
e.g. Query : Change my instagram profile. Output : https://www.instagram.com
e.g.2 Query : move my youtube playlist to spotify. Output : https://www.youtube.com/
Make sure the output format is as follows : 
>>>Output Start
https://www.example.com
<<<OUTPUT END
Be sure to just return the link which suits best as the initial link according to the given query and thus going to be first website to go on to.
'''

system_prompt_4 = '''You are given a curr_state which provides the current execution state of a browser automation script and a Task List which consists of list of items in plain words. Based on the given curr_state, extract the error from the curr_state, your task is to generate a new_task list based on the given error in order to fix the given error. 
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

ollama.create(model='task_list_generator', from_='deepseek-r1:14b',system = system_prompt)
ollama.create(model='next_task_generator', from_='deepseek-r1:14b', system = system_prompt_2)
ollama.create(model='initialiser', from_='deepseek-r1:14b', system=system_prompt_3)
ollama.create(model='error_addresser', from_='deepseek-r1:14b', system=system_prompt_4)

# Initialiser
output = ollama.generate(model='initialiser', prompt= query)
current_page_url = output['response']

# Tasks Generation
output = ollama.generate(model='task_list_generator', prompt= query)
task_list = output['response']
print(task_list)

# really just go to first page 
# check for error in the next_action 
# if there is error:
#       regenerate the task list with reference to the error using another model and thus another system_prompt# error_solved : True
#       now generate the next actionable step once again normally ! 
# perform the given action using playwright and if there is any error possibly rely it on yourself ! 


from playwright.sync_api import sync_playwright, Error as PlaywrightError
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    # Grab the existing default context and page
    default_context = browser.contexts[0]
    page = default_context.pages[0] if default_context.pages else default_context.new_page()

    while True: # Main while execution loop
        try:
            page.goto(current_page_url,wait_until="load", timeout=10000)
            print("Sucessfully Loaded the page")
            break
        except PlaywrightError as e:
            if e.name == "ERR_NETWORK_CHANGED" or e.name == "ERR_INTERNET_DISCONNECTED":
                print(f"Network error occurred. Retrying...")
                time.sleep(2)

        # next step generation
        page_content = extract_elements(current_page_url) 
        output = ollama.generate(model='next_task_generator', prompt = f" curr_state : {curr_state}, \n current_page_url : {current_page_url},  task_list : {task_list} page_content : {page_content}")
        next_task = output['response'] 
        print(next_task)
        

        if next_task['error'] != None:
            # error compensation
            output = ollama.generate(model='error_addresser', prompt= f"task_list: {task_list} curr_state : {curr_state} error_encountered: {next_task['error']}")
            task_list = output['response']
            next_task['error_solved'] = True
            continue
        
        for element in page_content:
            if page_content['id'] == next_task['selected_element_id']:
                target_element = element
                break
        
        curr_state.append(next_task)

        # really how to perform the action either click or type tbh 
        if next_task['action'] == "click":
            # will write more code later 
            pass