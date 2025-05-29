# -*- coding: utf-8 -*-

from response import *

msg= "tell me about you self"

prompt= [{'role': 'system', 'content': msg}]

response = openai_response_sync(
    model="qwen-turbo",
    messages=prompt,
    max_tokens=8000,
    temperature=0.7,
    top_p=0.9,
    frequency_penalty=0,
    presence_penalty=0,
    stop=None
)
print(response)
