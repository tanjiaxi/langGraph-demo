# DeepSeek 模型配置说明

## 1. 获取 DeepSeek API Key

访问 [DeepSeek 开放平台](https://platform.deepseek.com/)：
1. 注册/登录账号
2. 进入 API Keys 页面
3. 创建新的 API Key
4. 复制保存（只显示一次）

## 2. 配置方式

### 方式 1：运行时输入（当前配置）
```bash
python examples2.py
# 会提示输入：Enter your DeepSeek API key:
```

### 方式 2：环境变量（推荐）
```bash
# macOS/Linux
export DEEPSEEK_API_KEY="sk-xxxxxxxxxxxxxxxx"
python examples2.py

# 或者添加到 ~/.zshrc
echo 'export DEEPSEEK_API_KEY="sk-xxxxxxxxxxxxxxxx"' >> ~/.zshrc
source ~/.zshrc
```

### 方式 3：.env 文件
创建 `.env` 文件：
```bash
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
```

然后在代码中使用：
```python
from dotenv import load_dotenv
load_dotenv()
```

## 3. DeepSeek 模型列表

| 模型名称 | 说明 | 价格 |
|---------|------|------|
| `deepseek-chat` | 通用对话模型（推荐） | ¥1/百万tokens |
| `deepseek-coder` | 代码专用模型 | ¥1/百万tokens |

## 4. 与 OpenAI 的对比

```python
# OpenAI
llm = ChatOpenAI(
    model="gpt-4",
    openai_api_key="sk-...",
)

# DeepSeek（兼容 OpenAI API）
llm = ChatOpenAI(
    model="deepseek-chat",
    openai_api_key="sk-...",
    openai_api_base="https://api.deepseek.com",  # 唯一区别
)
```

## 5. 运行示例

```bash
cd /Users/t/ServerProjects/classic/langgraph/examples/my-examples
python examples2.py
```

## 6. 常见问题

### Q: 为什么用 ChatOpenAI 而不是 ChatDeepSeek？
A: DeepSeek API 完全兼容 OpenAI 格式，使用 `ChatOpenAI` + 自定义 `openai_api_base` 即可。

### Q: 如何切换回 OpenAI？
A: 修改三处：
```python
# 1. API Key
os.environ["OPENAI_API_KEY"] = ...

# 2. 模型配置
llm = ChatOpenAI(
    model="gpt-4",  # 或 gpt-3.5-turbo
    openai_api_key=os.environ["OPENAI_API_KEY"],
    # 删除 openai_api_base 参数
)
```

### Q: 支持流式输出吗？
A: 支持！
```python
for chunk in llm.stream("你好"):
    print(chunk.content, end="", flush=True)
```

## 7. 价格对比（参考）

| 模型 | 输入价格 | 输出价格 |
|------|---------|---------|
| DeepSeek Chat | ¥1/M tokens | ¥2/M tokens |
| GPT-4 Turbo | ¥70/M tokens | ¥210/M tokens |
| GPT-3.5 Turbo | ¥3.5/M tokens | ¥7/M tokens |

DeepSeek 性价比极高！🚀
