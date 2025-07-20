##
# Author:  
# Description:  
# LastEditors: Shiyuec
# LastEditTime: 2025-07-04 10:38:42
## 
import openai
import asyncio
import functools
import time
from api_key import *
import traceback
import random
client = openai.OpenAI(
    base_url=url,
    # sk-xxx替换为自己的key
    api_key=key
)

aclient = openai.AsyncOpenAI(
    base_url=url,
    # sk-xxx替换为自己的key
    api_key=key
)

api_instances = [
    openai.AsyncOpenAI(base_url=url, api_key=key_1),
    openai.AsyncOpenAI(base_url=url, api_key=key_2),
    openai.AsyncOpenAI(base_url=url, api_key=key_3),
    openai.AsyncOpenAI(base_url=url, api_key=key_4),
    openai.AsyncOpenAI(base_url=url, api_key=key_5),
    # 可以添加更多的实例
]


client_o1 = openai.OpenAI(
    base_url=url,
    # sk-xxx替换为自己的key
    api_key=o1_key
)

client_o3 = openai.OpenAI(
    base_url=url,
    # sk-xxx替换为自己的key
    api_key=o3_key
)

aclient_o1 = openai.AsyncOpenAI(
    base_url=url,
    # sk-xxx替换为自己的key
    api_key=o1_key
)

aclient_o3 = openai.AsyncOpenAI(
    base_url=url,
    # sk-xxx替换为自己的key
    api_key=o3_key
)


client_ds = openai.OpenAI(
    base_url=ds_url,
    # sk-xxx替换为自己的key
    api_key=ds_key
)

aclient_ds = openai.AsyncOpenAI(
    base_url=ds_url,
    # sk-xxx替换为自己的key
    api_key=ds_key
)

client_os = openai.OpenAI(
    base_url=openrouter_url,
    # sk-xxx替换为自己的key
    api_key=openrouter_key
)

aclient_os = openai.AsyncOpenAI(
    base_url=openrouter_url,
    # sk-xxx替换为自己的key
    api_key=openrouter_key
)




# 异步适配器
def async_adapter(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                return func(*args, **kwargs)  # 异步调用
        except RuntimeError:
            pass
        return asyncio.run(func(*args, **kwargs))  # 同步调用
    return wrapper

# 重试装饰器
def retry(max_retries=3, delay=1, exceptions=(Exception,)):
    """
    装饰器，用于捕获异常并重试函数。
    
    参数:
    - max_retries: 最大重试次数
    - delay: 每次重试之间的等待时间（秒）
    - exceptions: 捕获的异常类型（默认为 Exception）
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)  # 尝试执行被装饰函数
                except exceptions as e:
                    retries += 1
                    print(f"函数 {func.__name__} 请求失败，第 {retries} 次重试: {e}")
                    if retries < max_retries:
                        time.sleep(delay)  # 等待指定时间后重试
                    else:
                        print(f"函数 {func.__name__} 达到最大重试次数，退出。")
                        raise  # 超过最大重试次数后抛出异常
        return wrapper
    return decorator


#异步函数难用装饰器
async def openai_response_async(**kwargs):
    retries = 0

    # 修改 kwargs 中的 messages，将 role 为 'system' 改为 'user'
    thinking=""
    while retries < 2: #! 注意，外部还需要再次retry
        try:
            #completion = await aclient.chat.completions.create(timeout=30,**kwargs)
            aclient_i = random.choice(api_instances)
            if kwargs.get('model').startswith("o1"):
                kwargs['messages'] = [
                    {**msg, 'role': 'user'} if msg.get('role') == 'system' else msg
                    for msg in kwargs['messages']
                ]
                kwargs['temperature'] =1
                kwargs['max_tokens'] =8000
                if 'top_p' in kwargs:
                    kwargs.pop('top_p')
                completion = await asyncio.wait_for(aclient_o1.chat.completions.create(**kwargs), timeout=120)
            elif kwargs.get('model').startswith("o3"):
                kwargs['messages'] = [
                    {**msg, 'role': 'user'} if msg.get('role') == 'system' else msg
                    for msg in kwargs['messages']
                ]
                kwargs['temperature'] =1
                kwargs['max_tokens'] =8000
                if 'top_p' in kwargs:
                    kwargs.pop('top_p')
                completion = await asyncio.wait_for(aclient_o3.chat.completions.create(**kwargs), timeout=120)
            elif kwargs.get('model').startswith("deepseek-r"):
                completion = await asyncio.wait_for(aclient_ds.chat.completions.create(**kwargs), timeout=300)
                thinking ="<Thinking>" + completion.choices[0].message.model_extra['reasoning_content'] +"</Thinking>\n"
            elif kwargs.get('model').startswith("deepseek-v") :
                completion = await asyncio.wait_for(aclient_ds.chat.completions.create(**kwargs), timeout=120)
            elif kwargs.get('model').startswith("qwen3"):
                kwargs['extra_body'] ={
                                        "enable_thinking": True,
                                        "thinking_budget": 16000
                                        }
                kwargs['stream'] = True
                completion = await asyncio.wait_for(aclient_ds.chat.completions.create(**kwargs), timeout=30)
                reasoning_content = ""  # 完整思考过程
                answer_content = ""  # 完整回复
                async for chunk in completion:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    if hasattr(delta, "reasoning_content") and delta.reasoning_content is not None:
                        reasoning_content += delta.reasoning_content
                    if hasattr(delta, "content") and delta.content:
                        answer_content += delta.content
                return "<Thinking>" + reasoning_content +"</Thinking>\n" +answer_content
            elif kwargs.get('model').startswith("klusterai") or kwargs.get('model').startswith("mistralai"):
                completion = await asyncio.wait_for(aclient_os.chat.completions.create(**kwargs), timeout=120)
            else:
                completion = await asyncio.wait_for(aclient.chat.completions.create(**kwargs), timeout=120)
            return thinking + completion.choices[0].message.content


        except Exception as e:
            print(e)
            #traceback.print_exc()  # 打印栈跟踪
            print(f"API retry {retries}")
            #traceback.print_exc()  # 打印栈跟踪
            retries += 1
            await asyncio.sleep(random.uniform(2, 3))

@retry(max_retries=5, delay=2, exceptions=(Exception,))
def openai_response_sync(**kwargs):
    thinking=""
    if kwargs.get('model').startswith("o1"):
        kwargs['messages'] = [
            {**msg, 'role': 'user'} if msg.get('role') == 'system' else msg
            for msg in kwargs['messages']
        ]
        kwargs['temperature'] =1
        kwargs['max_tokens'] =8000
        if 'top_p' in kwargs:
            kwargs.pop('top_p')
        completion = client_o1.chat.completions.create(timeout=120,**kwargs)
    elif kwargs.get('model').startswith("o3"):
        kwargs['messages'] = [
            {**msg, 'role': 'user'} if msg.get('role') == 'system' else msg
            for msg in kwargs['messages']
        ]
        kwargs['temperature'] =1
        kwargs['max_tokens'] =8000
        if 'top_p' in kwargs:
            kwargs.pop('top_p')
        completion = client_o3.chat.completions.create(timeout=120,**kwargs)
    elif kwargs.get('model').startswith("deepseek-r"):
        completion = client_ds.chat.completions.create(timeout=180,**kwargs)
        thinking ="<Thinking>" + completion.choices[0].message.model_extra['reasoning_content'] +"</Thinking>\n"
    elif  kwargs.get('model').startswith("deepseek-v") :
        completion = client_ds.chat.completions.create(timeout=120,**kwargs)
    elif kwargs.get('model').startswith("qwen3"):
        kwargs['extra_body'] ={
                                "enable_thinking": True,
                                "thinking_budget": 16000
                                }
        kwargs['stream'] = True
        completion = client_ds.chat.completions.create(timeout=30,**kwargs)
        reasoning_content = ""  # 完整思考过程
        answer_content = ""  # 完整回复
        for chunk in completion:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if hasattr(delta, "reasoning_content") and delta.reasoning_content is not None:
                reasoning_content += delta.reasoning_content
            if hasattr(delta, "content") and delta.content:
                answer_content += delta.content
        return "<Thinking>" + reasoning_content +"</Thinking>\n" +answer_content
    elif kwargs.get('model').startswith("klusterai") or kwargs.get('model').startswith("mistralai") or kwargs.get('model').startswith("google"):
                completion = client_os.chat.completions.create(**kwargs)
    else:
        completion = client.chat.completions.create(timeout=120,**kwargs)
    return thinking + completion.choices[0].message.content


async def openai_response(**kwargs):
    """
    根据当前上下文选择同步或异步调用 openai API。
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # 异步上下文
        return await openai_response_async(**kwargs)
    else:
        # 同步上下文
        return openai_response_sync(**kwargs)

    