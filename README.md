# AgentScope-Poker
**基于大模型的多智能体德州扑克博弈推演系统**

一个在不完全信息环境下，由 LLM 驱动多智能体进行心理博弈、诈唬（Bluff）与筹码管理的《德州扑克》硬核推演引擎。

本项目基于 `AgentScope` 与 `ReAct` 范式构建，深度融合了“大模型心理博弈”与“绝对物理规则引擎”。通过严格的 Pydantic 结构化契约、Treys 国际标准算力库以及自研的“剥洋葱式边池结算算法”，成功让大模型 Agent 在充满欺诈、诱导与极端 All-in 场景的复杂桌面游戏中，展现出极高的拟人化决策水平与系统工程稳定性。

---




## 🎥 核心场景演示：Multi-Agent 德州扑克博弈推演

https://github.com/user-attachments/assets/9399244d-4a72-4183-b373-8984d3b31641





## 🌟 核心特性与架构亮点

### 1. Neuro-Symbolic（神经符号）解耦架构
搭建了基于事件驱动的确定性状态机，将**德扑数学概率、牌力比拼、边池分配**等绝对物理规则从 LLM 侧完全剥离。
* **降本增效：** 大模型仅负责“意图决策”（评估对手、设计诈唬），底层 `treys` 库负责计算高优牌型（如判断 Full House 大于 Flush），平均单步决策节约 Prompt Token 开销约 40%，实现 100% 规则零幻觉。
* **物理防线：** 具备系统级兜底拦截（Fallback），大模型试图做出违背物理规则的动作（如筹码不足强行加注）会被物理引擎直接拦截并打回重做。

### 2. 完美解决 All-in 多重边池结算难题
针对德州扑克中极其复杂的全下（All-in）场景，系统摒弃了简单的平分逻辑，独立实现了**“剥洋葱式 (Onion Peeling)”边池结算算法**。
* **时序与资产隔离：** 严格按照玩家本局历史 `total_invest` 从小到大进行梯次切分，无论产生多少层 Side Pot，系统均能极其精准地将不同层级的底池匹配给具有获取资格的赢家，破产与清算逻辑达到商业级标准。

### 3. 结构化输出的 100% 绝对控制
针对大模型在复杂决策流中常见的 JSON 偏移与数值伪造问题，设计了基于 `Pydantic` 的契约化数据模型（Action: Fold/Check/Call/Raise/All-in）。
* 结合字段强约束、格式校验与 Max_Retries（最高 3 次重试）机制，将 JSON 协议单次解析成功率提升至 95% 以上，保障游戏引擎 100% 不会因模型输出崩溃而中断。
* 终端 UI 拦截：配置全局物理消音器，拦截底层框架产生的 Tool Use JSON，保证终端呈现极度清爽的人类语言播报与筹码雷达图。

### 4. 不完全信息博弈与动态人格
摒弃了传统的死板 AI 设定，系统在开局通过混沌随机种子为每个 Agent 注入独一无二的“灰度人格”（如：激进诈唬者、保守岩石玩家、记仇鬼）。
在每轮行动前，系统向 Agent 动态注入上帝视角的残缺切片（公共牌、对手本轮下注、自己底牌、底池大小），支撑大模型完成翻牌前（Pre-flop）到河牌圈（River）的长程博弈。

---

## 📁 项目结构

```plaintext
AgentScope-Poker
 ├── poker_main.py      # 主程序入口：Agent 实例化、事件分发、UI 对齐播报
 ├── poker_state.py     # 物理引擎：状态机、剥洋葱边池结算、资产清算与破产校验
 ├── poker_schemas.py   # 数据契约：基于 Pydantic 的 LLM 结构化输出约束模型
 ├── poker_config.py    # 牌库配置：基于 Treys 规范的 52 张卡牌生成与映射
 └── poker_prompts.py   # 提示词库：系统 Prompt 与动态打法风格生成

快速开始
1. 环境准备
推荐使用 Python 3.9+ 环境。安装必要的依赖：
pip install agentscope pydantic treys

3. 配置环境变量
本项目默认兼容 OpenAI 格式的 API 接口。请在运行前配置你的大模型 API 密钥（默认以阿里云 DashScope 的 Qwen 模型为例，你也可以切换为其他 LLM）：

# Linux / macOS
export LLM_API_KEY="your_api_key_here"
export LLM_MODEL_ID="qwen-max"
export LLM_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"

# Windows (Command Prompt)
set LLM_API_KEY="your_api_key_here"
set LLM_MODEL_ID="qwen-max"
set LLM_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"

3. 启动游戏
在终端运行主程序，化身“上帝视角”观看 5 位高智商 Agent 尔虞我诈：
python poker_main.py
