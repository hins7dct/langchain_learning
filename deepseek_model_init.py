from  config import settings
from langchain_deepseek import ChatDeepSeek

# 模型的调用分为个性化调用和通用方法调用
# 个性化就只写deepseek，其余具体使用的时候去查询即可

# llm_model = ChatDeepSeek(
#     api_key=settings.deepseek_api_key,
#     api_base=settings.deepseek_base_url,
#     model_name=settings.deepseek_model_name
# )
#
# print(llm_model.invoke("介绍一下你自己"))

# 通用方式调用init_chat_model()
from langchain.chat_models import init_chat_model

model = init_chat_model(
    model="deepseek:deepseek-flash",
    api_key=settings.deepseek_api_key,
    api_base=settings.deepseek_base_url
)

response = model.invoke("介绍一下你自己")
print(response)