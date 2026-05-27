"""
三种等价的写法对比
"""

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

# 假设配置
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是助手"),
    ("human", "{question}")
])
llm = ChatOpenAI(model="deepseek-chat")

# ============================================
# 写法 1：管道（最 Pythonic）
# ============================================
print("=== 写法 1: 管道 ===")
chain = prompt | llm
# response = chain.invoke({"question": "你好"})

# ============================================
# 写法 2：分步调用（更明确）
# ============================================
print("=== 写法 2: 分步 ===")
def step_by_step(question):
    # 步骤 1
    formatted_messages = prompt.invoke({"question": question})
    print(f"步骤 1 输出: {formatted_messages}")
    
    # 步骤 2
    response = llm.invoke(formatted_messages)
    print(f"步骤 2 输出: {response.content}")
    
    return response

# ============================================
# 写法 3：完全手动（最底层）
# ============================================
print("=== 写法 3: 手动 ===")
def manual(question):
    # 手动构造消息
    messages = [
        {"role": "system", "content": "你是助手"},
        {"role": "user", "content": question}
    ]
    
    # 调用模型
    response = llm.invoke(messages)
    return response

# ============================================
# JavaScript 等价代码
# ============================================
print("\n=== JavaScript 等价 ===")
print("""
// 写法 1: 函数组合
const chain = compose(llm, prompt);
const response = await chain({question: "你好"});

// 写法 2: Promise 链
const response = await prompt({question: "你好"})
    .then(formatted => llm(formatted));

// 写法 3: async/await
async function manual(question) {
    const formatted = await prompt({question});
    const response = await llm(formatted);
    return response;
}
""")

# ============================================
# Go 等价代码
# ============================================
print("=== Go 等价 ===")
print("""
// 写法 1: 封装链
type Chain struct {
    prompt Prompt
    llm    LLM
}

func (c *Chain) Invoke(input map[string]string) Response {
    formatted := c.prompt.Invoke(input)
    return c.llm.Invoke(formatted)
}

// 写法 2: 显式调用
func stepByStep(question string) Response {
    formatted := prompt.Invoke(map[string]string{"question": question})
    response := llm.Invoke(formatted)
    return response
}

// 写法 3: 完全手动
func manual(question string) Response {
    messages := []Message{
        {Role: "system", Content: "你是助手"},
        {Role: "user", Content: question},
    }
    return llm.Invoke(messages)
}
""")

# ============================================
# 为什么 Python 用 | 操作符？
# ============================================
print("\n=== 为什么用 | ？ ===")
print("""
1. Python 的 | 操作符可以被重载
   
   class Prompt:
       def __or__(self, other):  # 重载 | 操作符
           return Chain(self, other)
   
   prompt | llm  # 实际调用 prompt.__or__(llm)

2. 类似 Unix 管道的直觉
   
   cat file.txt | grep "error" | wc -l
   prompt | llm | parser

3. 比嵌套调用更清晰
   
   ❌ parser(llm(prompt(data)))  # 从内到外读
   ✅ prompt | llm | parser      # 从左到右读
""")

# ============================================
# 实际例子：多步骤链
# ============================================
print("\n=== 多步骤链示例 ===")
print("""
from langchain_core.output_parsers import StrOutputParser

# 3 步链
chain = (
    prompt              # 步骤 1: 格式化输入
    | llm               # 步骤 2: 调用模型
    | StrOutputParser() # 步骤 3: 提取字符串
)

# 等价于
def three_step_chain(input_data):
    step1 = prompt.invoke(input_data)
    step2 = llm.invoke(step1)
    step3 = StrOutputParser().invoke(step2)
    return step3

# JavaScript 等价
const chain = compose(
    strOutputParser,
    llm,
    prompt
);

// Go 等价
formatted := prompt.Invoke(input)
response := llm.Invoke(formatted)
result := parser.Invoke(response)
""")
