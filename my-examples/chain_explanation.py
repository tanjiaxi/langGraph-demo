"""
LangChain 链式调用详解
适合 JS/Go 开发者理解
"""

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import os

# 假设已设置 API Key
os.environ["DEEPSEEK_API_KEY"] = "sk-test"

# ============================================
# 第一部分：理解 prompt 模板
# ============================================

# 创建提示模板
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个有帮助的AI助手。"),
    ("human", "{question}")  # {question} 是占位符
])

# 测试：查看模板如何工作
print("=== 1. Prompt 模板测试 ===")
formatted = prompt.invoke({"question": "什么是AI？"})
print(f"类型: {type(formatted)}")
print(f"内容: {formatted}")
print()

# ============================================
# 第二部分：理解 llm 模型
# ============================================

llm = ChatOpenAI(
    model="deepseek-chat",
    openai_api_key=os.environ["DEEPSEEK_API_KEY"],
    openai_api_base="https://api.deepseek.com",
)

print("=== 2. LLM 模型测试 ===")
print(f"模型类型: {type(llm)}")
print(f"模型名称: {llm.model_name}")
print()

# ============================================
# 第三部分：理解 | 管道操作符
# ============================================

print("=== 3. 管道操作符 | ===")

# 方式 1：使用管道（推荐）
chain = prompt | llm
print(f"链类型: {type(chain)}")

# 方式 2：手动调用（等价，但繁琐）
def manual_chain(input_data):
    # 步骤 1：格式化提示词
    formatted_prompt = prompt.invoke(input_data)
    # 步骤 2：调用模型
    response = llm.invoke(formatted_prompt)
    return response

print()

# ============================================
# 第四部分：对比不同的调用方式
# ============================================

print("=== 4. 三种等价的调用方式 ===")

input_data = {"question": "1+1等于几？"}

# 方式 1：使用链（最简洁）
print("方式 1: 使用链")
print("代码: chain.invoke(input_data)")
# response1 = chain.invoke(input_data)
# print(f"结果: {response1.content}\n")

# 方式 2：分步调用
print("方式 2: 分步调用")
print("代码:")
print("  step1 = prompt.invoke(input_data)")
print("  step2 = llm.invoke(step1)")
# step1 = prompt.invoke(input_data)
# step2 = llm.invoke(step1)
# print(f"结果: {step2.content}\n")

# 方式 3：完全手动
print("方式 3: 完全手动")
print("代码:")
print("  messages = [")
print("    {'role': 'system', 'content': '你是一个有帮助的AI助手。'},")
print("    {'role': 'user', 'content': '1+1等于几？'}")
print("  ]")
print("  response = llm.invoke(messages)")
# response3 = llm.invoke([
#     {"role": "system", "content": "你是一个有帮助的AI助手。"},
#     {"role": "user", "content": "1+1等于几？"}
# ])
# print(f"结果: {response3.content}\n")

# ============================================
# 第五部分：对比 JS/Go 的类似概念
# ============================================

print("=== 5. 跨语言对比 ===")
print("""
Python (LangChain):
    chain = prompt | llm
    result = chain.invoke(data)

JavaScript (函数组合):
    const chain = compose(llm, prompt);
    const result = chain(data);
    
    // 或者 Promise 链
    prompt(data)
        .then(formatted => llm(formatted))
        .then(result => console.log(result));

Go (显式调用):
    formatted := prompt.Invoke(data)
    result := llm.Invoke(formatted)
    
    // 或者封装
    chain := NewChain(prompt, llm)
    result := chain.Invoke(data)
""")

# ============================================
# 第六部分：更复杂的链
# ============================================

print("=== 6. 复杂链示例 ===")
print("""
# 可以链接多个组件
from langchain_core.output_parsers import StrOutputParser

chain = (
    prompt           # 步骤 1: 格式化
    | llm            # 步骤 2: 调用模型
    | StrOutputParser()  # 步骤 3: 解析输出
)

# 等价于
def complex_chain(input_data):
    step1 = prompt.invoke(input_data)
    step2 = llm.invoke(step1)
    step3 = StrOutputParser().invoke(step2)
    return step3
""")

# ============================================
# 第七部分：为什么用管道？
# ============================================

print("=== 7. 管道的优势 ===")
print("""
1. 可读性：
   ❌ result = parser(llm(prompt(data)))  # 难读
   ✅ chain = prompt | llm | parser       # 清晰

2. 可组合性：
   base_chain = prompt | llm
   full_chain = base_chain | parser | validator
   
3. 可复用性：
   qa_chain = qa_prompt | llm
   summary_chain = summary_prompt | llm
   
4. 类似概念：
   - Unix: cat file.txt | grep "error" | wc -l
   - RxJS: observable.pipe(map(), filter(), reduce())
   - Go: io.Reader -> io.Writer (虽然不是操作符)
""")

print("\n=== 总结 ===")
print("""
chain = prompt | llm
response = chain.invoke({"question": "..."})

等价于：
1. 用 prompt 格式化输入
2. 把格式化结果传给 llm
3. 返回 llm 的响应

就像 Unix 管道：
  echo "hello" | tr '[:lower:]' '[:upper:]' | wc -c
  
或者 JavaScript Promise 链：
  fetch(url)
    .then(res => res.json())
    .then(data => process(data))
""")
