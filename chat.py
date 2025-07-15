# -*- coding: utf-8 -*-

from response import *


msg= "what is your name" #你的模型名称是什么？

prompt= [{'role': 'system', 'content': msg},
         {'role': 'user', 'content': " "} #有些模型不能没有user
         ]

response = openai_response_sync(
    model="google/gemma-3-27b-it",
    messages=prompt,
    max_tokens=1000,
    temperature=0.7,
    top_p=0.9,
    frequency_penalty=0,
    presence_penalty=0,
    stop=None
)
print(response)
