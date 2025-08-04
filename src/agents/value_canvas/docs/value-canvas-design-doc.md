# Design Doc

# Value-Canvas LangGraph MVP · Design Doc

---

## 0. 文档关系说明

**本设计文档与 AI Agent [Value Canvas]-prompts-and-instructions.pdf 的关系：**

- **PDF文档** = **Agent行为规范**（WHAT）：定义Value Canvas AI Agent应该如何与用户交互，包含系统prompt、引导技术、所有权建立方法等高层次的行为要求
- **本设计文档** = **技术实现架构**（HOW）：描述如何使用LangGraph多节点架构来实现PDF中定义的复杂Agent行为

**架构设计理念：**
- PDF中描述的是一个完整的Value Canvas咨询流程，需要复杂的对话引导、状态管理、回退机制
- 传统的单一LLM调用无法有效处理如此复杂的多阶段交互和状态管理
- 因此采用LangGraph的多节点架构：
  - **Router**: 管理section切换和流程控制
  - **Chat Agent**: 专注于基于PDF规范的对话引导，无工具干扰
  - **Memory Updater**: 处理数据持久化和状态更新
  - **Implementation**: 生成最终deliverable

**关键设计决策：**
- Chat Agent不使用工具，专注于实现PDF中要求的复杂对话引导和所有权建立技术
- 通过Router实现PDF中要求的section间导航和回退逻辑
- 通过结构化的section_states管理PDF中描述的复杂数据收集流程

---

...(原文其余内容保持不变)... 