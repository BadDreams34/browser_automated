from chatgpt_client import ChatGPTClient
with ChatGPTClient(headless=True) as chatgpt:
   response = chatgpt.ask(
        "Explain Python decorators with examples."
    )

   print(response)