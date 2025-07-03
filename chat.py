# -*- coding: utf-8 -*-

from response import *


msg= "你的模型名称是什么? gpt-4o, gpt-4, o1, o3?"

prompt= [{'role': 'system', 'content': msg}]

response = openai_response_sync(
    model="o3-mini",
    messages=prompt,
    max_tokens=8000,
    temperature=0.7,
    top_p=0.9,
    frequency_penalty=0,
    presence_penalty=0,
    stop=None
)
print(response)
