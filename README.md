这是一个用于 B2B 销售 Agent 的最小可用 Harness，支持规则驱动对话、mock 工具调用、结构化输出、多轮状态、可观测性、自动评测和 prompt 版本对比。

## 运行方式

无需安装第三方依赖, 需要 Python。

```bash
python3 -m sales_agent_harness.cli --input examples/input.json
```

如果要从 stdin 传入 JSON：

```bash
cat examples/input.json | python3 -m sales_agent_harness.cli
```

## 多轮状态管理

支持两种多轮方式：

1. 直接把上一轮输出的 `state` 放入下一轮输入 JSON 的 `state` 字段。
2. 使用 CLI 的 `--state-file` 自动按 `session_id` 保存和读取状态。

示例：

```bash
python3 -m sales_agent_harness.cli \
  --input examples/multiturn_turn1.json \
  --state-file /tmp/sales-agent-state.json

python3 -m sales_agent_harness.cli \
  --input examples/multiturn_turn2.json \
  --state-file /tmp/sales-agent-state.json
```

第一轮会记录邮箱、时区、公司规模、行业、Demo 目的，并返回候选 slot；第二轮即使用户只说“选 slot_1”，也会从状态中恢复上下文，继续调用 `book_demo`，成功后再写 CRM。

## 最小可观测性

每次运行都会返回 `trace`：

- `run_id`：单次运行唯一 ID；
- `session_id` / `turn_index`：用于关联多轮会话；
- `started_at` / `duration_ms`：运行开始时间和耗时；
- `decision`：本轮进入的核心决策分支；
- `tool_call_count` / `trajectory`：工具调用数量和带结果的轨迹；
- `events`：结构化事件流，包括 `run_started`、`state_merged`、`policy_evaluated`、`decision_selected`、`run_completed`。

CLI 也支持 JSONL 日志：

```bash
python3 -m sales_agent_harness.cli \
  --input examples/input.json \
  --log-file /tmp/sales-agent-runs.jsonl
```

## Prompt 版本对比

支持 prompt 版本对比。当前内置两个策略版本：

- `v1`：模拟较宽松的初版 prompt，风险词、Demo 前置条件和事实查询覆盖较少；
- `v2`：当前严格版策略，覆盖完整状态机、风险转人工和防编造约束。

运行对比：

```bash
python3 -m sales_agent_harness.compare_prompts
```

也可以指定版本顺序，第一项作为 baseline：

```bash
python3 -m sales_agent_harness.compare_prompts --versions v1 v2
```

输出包含每个版本的通过率、失败 case、工具调用差异，以及候选版本相对 baseline 的 `newly_passed` / `regressed`。

## 运行 eval

```bash
python3 -m sales_agent_harness.eval_runner
```

eval runner 内置 27 个测试用例，覆盖：

- 政策遵守；
- 工具调用正确性；
- 不编造价格、客户案例或交付承诺；
- 合同、法务、安全审计、定制报价转人工；
- CRM 记录规则；
- Demo 预约流程；
- 多轮状态继承；
- prompt 版本对比；
- trace / run_id / JSONL 日志所需字段；
- 输出 JSON 稳定可解析。

## 输出格式

CLI 输出结构化 JSON：

```json
{
  "assistant_message": "...",
  "tool_calls": [
    {
      "tool_name": "write_crm_note",
      "arguments": {}
    }
  ],
  "state": {
    "qualification_level": "medium",
    "missing_info": [],
    "next_action": "...",
    "risk_flags": []
  },
  "trace": {
    "run_id": "...",
    "session_id": "...",
    "turn_index": 1,
    "started_at": "...",
    "duration_ms": 1.23,
    "prompt_version": "v2",
    "decision": "...",
    "tool_call_count": 1,
    "trajectory": [],
    "events": []
  }
}
```

## 架构说明

- `sales_agent_harness/agent.py`：核心 Agent Harness，负责信息抽取、风险识别、资格判断、Demo 流程和 CRM 更新决策。
- `sales_agent_harness/tools.py`：6 个 mock 工具，并记录工具调用轨迹。
- `sales_agent_harness/cli.py`：命令行入口，读取 JSON 输入并输出 JSON。
- `sales_agent_harness/eval_runner.py`：自动化评测入口，内置 27 个 case。
- `sales_agent_harness/compare_prompts.py`：prompt 版本对比入口，输出 v1/v2 通过率和差异。
- `examples/input.json`：示例输入。
- `examples/multiturn_turn1.json` / `examples/multiturn_turn2.json`：跨命令多轮状态示例。

## 已知问题

- 当前是规则型 mock Agent，中文/英文表达覆盖有限，真实上线前应替换或补充为 LLM + 更完整的结构化抽取器。
- 多轮状态已支持通过 `state` 字段或 CLI `--state-file` 保存；当前没有并发锁，多个进程同时写同一个 state file 时可能互相覆盖。
- mock 工具数据较小，只用于支撑评测，不代表真实 CRM、知识库和日历集成。

## 当前方案最大的 3 个风险

1. 规则抽取对复杂表达不够鲁棒，可能漏识别预算、时区或决策人。
2. mock KB 无法覆盖真实产品边界，接入真实 LLM 后仍需要严格引用知识库来源。
3. 评测集规模有限，能防住典型失败，但不足以代表生产流量。
