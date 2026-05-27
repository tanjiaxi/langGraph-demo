"""
LangGraph Human-in-the-Loop 示例
适合 JS/Go 开发者

Human-in-the-Loop 是什么？
- AI 执行到某个节点时暂停
- 等待人工审核/修改
- 人工确认后继续执行

类似概念：
- 审批流程：提交 → 等待审批 → 继续
- Git: commit → review → merge
"""

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from typing_extensions import TypedDict, Annotated
from typing import List
import operator
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_openai import ChatOpenAI
import os

# ============================================
# 第一部分：理解 interrupt_before
# ============================================

print("="*60)
print("⏸️  第一部分：理解 interrupt_before")
print("="*60)

print("""
interrupt_before 是什么？
------------------------
在指定节点**之前**暂停执行，等待人工介入

类似概念：
---------
JavaScript:
  async function workflow() {
      await step1();
      await waitForApproval();  // 暂停，等待用户操作
      await step2();
  }

Go:
  func workflow() {
      step1()
      <-approvalChannel  // 阻塞，等待审批
      step2()
  }

使用场景：
---------
1. 敏感操作需要审批（删除数据、发送邮件）
2. AI 生成内容需要人工审核
3. 关键决策需要人工确认
4. 调试和测试
""")

# ============================================
# 第二部分：基础 Human-in-the-Loop 示例
# ============================================

print("\n" + "="*60)
print("🔧 第二部分：基础示例")
print("="*60)


class EmailState(TypedDict):
    """邮件发送状态"""
    recipient: str
    subject: str
    content: str
    approved: bool
    sent: bool


def draft_email(state: EmailState):
    """起草邮件"""
    print(f"\n📝 [起草邮件]")
    print(f"   收件人: {state['recipient']}")
    print(f"   主题: {state['subject']}")
    
    content = f"尊敬的 {state['recipient']}，\n\n这是一封自动生成的邮件。\n\n祝好！"
    
    return {"content": content}


def send_email(state: EmailState):
    """发送邮件（敏感操作）"""
    print(f"\n📧 [发送邮件]")
    print(f"   收件人: {state['recipient']}")
    print(f"   内容: {state['content'][:50]}...")
    print("   ✅ 邮件已发送！")
    
    return {"sent": True}


# 构建图
email_graph = StateGraph(EmailState)
email_graph.add_node("draft", draft_email)
email_graph.add_node("send", send_email)
email_graph.add_edge(START, "draft")
email_graph.add_edge("draft", "send")
email_graph.add_edge("send", END)

# ⭐ 关键：添加 interrupt_before
memory = MemorySaver()
email_app = email_graph.compile(
    checkpointer=memory,
    interrupt_before=["send"]  # 在 send 节点之前暂停
)

print("\n🧪 测试 1：邮件审批流程")

config = {"configurable": {"thread_id": "email_001"}}

# 第一步：起草邮件（会在 send 之前暂停）
print("\n--- 步骤 1: 起草邮件 ---")
result = email_app.invoke(
    {
        "recipient": "boss@company.com",
        "subject": "重要通知",
        "approved": False,
        "sent": False
    },
    config=config
)

print(f"\n⏸️  执行已暂停！")
print(f"   当前状态: {result}")
print(f"   下一个节点: send")
print(f"   等待人工审批...")

# 模拟人工审核
print("\n--- 人工审核 ---")
print("👤 审核人员查看邮件内容...")
print(f"   内容: {result['content']}")
approval = input("\n是否批准发送？(y/n): ")

if approval.lower() == 'y':
    # 第二步：继续执行（发送邮件）
    print("\n--- 步骤 2: 继续执行 ---")
    result = email_app.invoke(None, config=config)  # None 表示继续
    print(f"\n✅ 流程完成！邮件已发送: {result['sent']}")
else:
    print("\n❌ 审批被拒绝，邮件未发送")

# ============================================
# 第三部分：修改状态后继续
# ============================================

print("\n" + "="*60)
print("✏️  第三部分：修改状态后继续")
print("="*60)

print("""
人工介入时可以：
--------------
1. 直接继续（invoke(None, config)）
2. 修改状态后继续（update_state + invoke）
3. 取消执行

类似 Git 的 rebase：
-------------------
git rebase --interactive
# 修改 commit
git rebase --continue
""")

print("\n🧪 测试 2：修改邮件内容")

config2 = {"configurable": {"thread_id": "email_002"}}

# 起草邮件
print("\n--- 步骤 1: 起草邮件 ---")
result = email_app.invoke(
    {
        "recipient": "client@example.com",
        "subject": "产品更新",
        "approved": False,
        "sent": False
    },
    config=config2
)

print(f"\n⏸️  执行已暂停")
print(f"   原始内容: {result['content'][:50]}...")

# 人工修改内容
print("\n--- 人工修改 ---")
modified_content = result['content'] + "\n\nP.S. 这是人工添加的内容"

# 更新状态
email_app.update_state(
    config2,
    {"content": modified_content, "approved": True}
)

print("✅ 内容已修改")

# 继续执行
print("\n--- 步骤 2: 继续执行 ---")
result = email_app.invoke(None, config=config2)
print(f"✅ 邮件已发送（包含修改后的内容）")

# ============================================
# 第四部分：AI 内容审核系统
# ============================================

print("\n" + "="*60)
print("🤖 第四部分：AI 内容审核系统")
print("="*60)

os.environ["DEEPSEEK_API_KEY"] = "sk-1f1f27b8e0524422bab4b8517b1068ca"

llm = ChatOpenAI(
    model="deepseek-chat",
    openai_api_key=os.environ["DEEPSEEK_API_KEY"],
    openai_api_base="https://api.deepseek.com",
    temperature=0.7,
)


class ContentState(TypedDict):
    """内容生成状态"""
    topic: str
    draft_content: str
    reviewed: bool
    published: bool
    feedback: str


def generate_content(state: ContentState):
    """AI 生成内容"""
    print(f"\n🤖 [AI 生成内容]")
    print(f"   主题: {state['topic']}")
    
    prompt = f"写一篇关于 {state['topic']} 的简短文章（100字以内）"
    response = llm.invoke([HumanMessage(content=prompt)])
    
    print(f"   ✅ 内容已生成")
    
    return {"draft_content": response.content}


def publish_content(state: ContentState):
    """发布内容"""
    print(f"\n📢 [发布内容]")
    print(f"   内容: {state['draft_content'][:50]}...")
    print("   ✅ 内容已发布到网站！")
    
    return {"published": True}


# 构建内容审核图
content_graph = StateGraph(ContentState)
content_graph.add_node("generate", generate_content)
content_graph.add_node("publish", publish_content)
content_graph.add_edge(START, "generate")
content_graph.add_edge("generate", "publish")
content_graph.add_edge("publish", END)

# 在发布前暂停，等待审核
content_app = content_graph.compile(
    checkpointer=memory,
    interrupt_before=["publish"]
)

print("\n🧪 测试 3：内容审核流程")

config3 = {"configurable": {"thread_id": "content_001"}}

# 生成内容
print("\n--- 步骤 1: AI 生成内容 ---")
result = content_app.invoke(
    {
        "topic": "人工智能的未来",
        "reviewed": False,
        "published": False,
        "feedback": ""
    },
    config=config3
)

print(f"\n⏸️  等待人工审核")
print(f"\n📄 生成的内容:")
print("="*60)
print(result['draft_content'])
print("="*60)

# 人工审核
review = input("\n是否批准发布？(y/n/edit): ")

if review.lower() == 'y':
    # 批准发布
    print("\n--- 步骤 2: 发布内容 ---")
    result = content_app.invoke(None, config=config3)
    print(f"✅ 内容已发布")
    
elif review.lower() == 'edit':
    # 修改后发布
    print("\n--- 修改内容 ---")
    edited_content = input("输入修改后的内容: ")
    
    content_app.update_state(
        config3,
        {"draft_content": edited_content, "reviewed": True}
    )
    
    print("\n--- 步骤 2: 发布修改后的内容 ---")
    result = content_app.invoke(None, config=config3)
    print(f"✅ 修改后的内容已发布")
    
else:
    print("\n❌ 审核未通过，内容未发布")

# ============================================
# 第五部分：多步骤审批流程
# ============================================

print("\n" + "="*60)
print("🔄 第五部分：多步骤审批")
print("="*60)


class ApprovalState(TypedDict):
    """审批状态"""
    request: str
    manager_approved: bool
    director_approved: bool
    ceo_approved: bool
    final_status: str


def manager_review(state: ApprovalState):
    print(f"\n👔 [经理审批]")
    print(f"   请求: {state['request']}")
    return {"manager_approved": True}


def director_review(state: ApprovalState):
    print(f"\n👨‍💼 [总监审批]")
    return {"director_approved": True}


def ceo_review(state: ApprovalState):
    print(f"\n🎩 [CEO 审批]")
    return {"ceo_approved": True}


def finalize(state: ApprovalState):
    print(f"\n✅ [最终确认]")
    return {"final_status": "approved"}


# 构建多级审批图
approval_graph = StateGraph(ApprovalState)
approval_graph.add_node("manager", manager_review)
approval_graph.add_node("director", director_review)
approval_graph.add_node("ceo", ceo_review)
approval_graph.add_node("finalize", finalize)

approval_graph.add_edge(START, "manager")
approval_graph.add_edge("manager", "director")
approval_graph.add_edge("director", "ceo")
approval_graph.add_edge("ceo", "finalize")
approval_graph.add_edge("finalize", END)

# ⭐ 在每个审批节点前暂停
approval_app = approval_graph.compile(
    checkpointer=memory,
    interrupt_before=["manager", "director", "ceo"]
)

print("\n🧪 测试 4：三级审批流程")

config4 = {"configurable": {"thread_id": "approval_001"}}

# 提交请求
print("\n--- 提交审批请求 ---")
result = approval_app.invoke(
    {
        "request": "购买新服务器（预算 $10,000）",
        "manager_approved": False,
        "director_approved": False,
        "ceo_approved": False,
        "final_status": "pending"
    },
    config=config4
)

print(f"⏸️  等待经理审批...")

# 经理审批
input("\n按 Enter 键进行经理审批...")
result = approval_app.invoke(None, config=config4)
print(f"⏸️  等待总监审批...")

# 总监审批
input("\n按 Enter 键进行总监审批...")
result = approval_app.invoke(None, config=config4)
print(f"⏸️  等待 CEO 审批...")

# CEO 审批
input("\n按 Enter 键进行 CEO 审批...")
result = approval_app.invoke(None, config=config4)

print(f"\n✅ 审批流程完成！")
print(f"   最终状态: {result['final_status']}")

# ============================================
# 第六部分：对比 JavaScript/Go
# ============================================

print("\n" + "="*60)
print("🔄 跨语言对比")
print("="*60)

print("""
Python (LangGraph):
-------------------
app = graph.compile(
    checkpointer=memory,
    interrupt_before=["sensitive_node"]
)

# 第一次调用：执行到 interrupt 点
result = app.invoke(input, config)

# 人工审核...

# 继续执行
result = app.invoke(None, config)


JavaScript (类似实现):
---------------------
async function workflow(input, sessionId) {
    // 步骤 1
    const draft = await step1(input);
    
    // 保存状态，等待审批
    await saveState(sessionId, { draft, step: 'awaiting_approval' });
    return { status: 'paused', draft };
}

// 人工审批后
async function continueWorkflow(sessionId) {
    const state = await loadState(sessionId);
    
    // 步骤 2
    const result = await step2(state.draft);
    return result;
}


Go (类似实现):
-------------
type Workflow struct {
    State       State
    ApprovalCh  chan bool
}

func (w *Workflow) Run() {
    // 步骤 1
    draft := w.step1()
    
    // 等待审批
    approved := <-w.ApprovalCh
    
    if approved {
        // 步骤 2
        w.step2(draft)
    }
}

// 另一个 goroutine 处理审批
go func() {
    approval := getUserApproval()
    workflow.ApprovalCh <- approval
}()
""")

# ============================================
# 第七部分：最佳实践
# ============================================

print("\n" + "="*60)
print("📚 Human-in-the-Loop 最佳实践")
print("="*60)

print("""
1. 在敏感操作前暂停
   ✅ interrupt_before=["delete_data", "send_email"]
   - 删除数据
   - 发送邮件/通知
   - 金融交易
   - 发布内容

2. 提供清晰的审核信息
   ✅ 显示完整的操作内容
   ✅ 提供上下文信息
   ❌ 只显示 "是否继续？"

3. 支持修改和重试
   ✅ 允许修改状态后继续
   ✅ 允许取消操作
   ❌ 只能批准/拒绝

4. 设置超时机制
   - 审批请求不应无限期等待
   - 超时后自动拒绝或通知

5. 记录审批历史
   - 谁审批的
   - 什么时候审批的
   - 是否修改了内容

6. 权限控制
   - 不同级别的审批权限
   - 敏感操作需要更高权限

7. 通知机制
   - 邮件/短信通知审批人
   - 审批完成后通知提交人
""")

print("\n" + "="*60)
print("✅ Human-in-the-Loop 示例完成！")
print("="*60)
