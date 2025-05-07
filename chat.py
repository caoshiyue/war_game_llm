##
# Author:  
# Description:  
# LastEditors: Shiyuec
# LastEditTime: 2025-05-07 12:03:35
## 
##
# Author:  
# Description:  
# LastEditors: Shiyuec
# LastEditTime: 2025-04-02 08:59:40
## 
from response import *

msg= """
Tell me about youself
"""


prompt= [{'role': 'system', 'content': msg}]

response = openai_response_sync(
    model="qwen-max-latest",
    messages=prompt,
    max_tokens=4000,
    temperature=0.7,
    top_p=0.9,
    frequency_penalty=0,
    presence_penalty=0,
    stop=None
)
print(response)