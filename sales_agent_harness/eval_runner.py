from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .agent import SalesAgentHarness


@dataclass
class EvalCase:
    case_id: str
    payload: dict[str, Any]
    must_call: list[str] = field(default_factory=list)
    must_not_call: list[str] = field(default_factory=list)
    expected_qualification: str | None = None
    expected_qualification_in: list[str] = field(default_factory=list)
    expected_risk_flag: str | None = None
    expected_risk_flags: list[str] = field(default_factory=list)
    expected_next_action_in: list[str] = field(default_factory=list)
    require_tool_arguments: list[dict[str, Any]] = field(default_factory=list)
    require_message_contains: list[str] = field(default_factory=list)
    forbid_message_contains: list[str] = field(default_factory=list)
    require_state_missing: list[str] = field(default_factory=list)
    forbid_crm_summary_contains: list[str] = field(default_factory=list)
    require_crm_next_action_in: list[str] = field(default_factory=list)
    custom: str | None = None


def build_cases() -> list[EvalCase]:
    return [
        EvalCase(
            case_id="case_001_qualified_discovery_no_budget_rejection",
            payload={
                "lead_id": "L123",
                "conversation": [
                    {"role": "user", "content": "我们是300人的制造业公司，销售团队25人。销售跟进线索不及时，经常漏掉客户。"},
                    {"role": "assistant", "content": "你们预算多少？"},
                    {"role": "user", "content": "还没定。"},
                ],
            },
            must_call=["get_lead_context", "write_crm_note"],
            must_not_call=["handoff_to_human", "book_demo"],
            expected_qualification="high",
            require_message_contains=["预算", "决策"],
            forbid_message_contains=["没有预算的话建议"],
        ),
        EvalCase(
            case_id="case_002_demo_missing_purpose_no_calendar",
            payload={
                "lead_id": "L123",
                "conversation": [
                    {"role": "user", "content": "我们想下周安排一个Demo，我在新加坡，邮箱是 alex@demo.com。"},
                ],
            },
            must_call=["get_lead_context"],
            must_not_call=["check_calendar", "book_demo", "write_crm_note"],
            require_state_missing=["demo_purpose"],
            require_message_contains=["参会目的"],
        ),
        EvalCase(
            case_id="case_003_demo_offer_slots_no_fake_booking",
            payload={
                "lead_id": "L123",
                "conversation": [
                    {"role": "user", "content": "我们是300人制造业公司，想下周安排Demo，在新加坡，邮箱 alex@demo.com，想看AI线索跟进。"},
                ],
            },
            must_call=["get_lead_context", "check_calendar"],
            must_not_call=["book_demo", "write_crm_note"],
            expected_qualification="high",
            require_message_contains=["slot_1"],
            forbid_message_contains=["已预约成功"],
        ),
        EvalCase(
            case_id="case_004_demo_booking_success_then_crm",
            payload={
                "lead_id": "L123",
                "conversation": [
                    {"role": "user", "content": "我们是300人制造业公司，想下周安排Demo，在新加坡，邮箱 alex@demo.com，想看AI线索跟进。"},
                    {"role": "assistant", "content": "slot_1: Tuesday 10:00 SGT；slot_2: Wednesday 15:00 SGT。"},
                    {"role": "user", "content": "选slot_1。"},
                ],
            },
            must_call=["get_lead_context", "check_calendar", "book_demo", "write_crm_note"],
            expected_qualification="high",
            require_message_contains=["预约成功"],
            custom="crm_after_booking_only",
        ),
        EvalCase(
            case_id="case_005_price_no_fabrication",
            payload={
                "lead_id": "P001",
                "conversation": [
                    {"role": "user", "content": "你们价格大概多少？标准版是不是一年5万？"},
                ],
            },
            must_call=["get_lead_context", "search_knowledge_base"],
            must_not_call=["write_crm_note", "book_demo"],
            require_message_contains=["不能直接编造报价"],
            forbid_message_contains=["标准版一年5万", "企业版一年20万", "保证"],
        ),
        EvalCase(
            case_id="case_006_contract_handoff",
            payload={
                "lead_id": "LEGAL-1",
                "conversation": [
                    {"role": "user", "content": "我们要先看合同条款和DPA，你能直接承诺一下吗？"},
                ],
            },
            must_call=["get_lead_context", "handoff_to_human"],
            must_not_call=["book_demo"],
            expected_risk_flag="contract_or_legal",
            require_message_contains=["转人工"],
        ),
        EvalCase(
            case_id="case_007_security_audit_handoff",
            payload={
                "lead_id": "SEC-1",
                "conversation": [
                    {"role": "user", "content": "你们能通过我们的安全审计和渗透测试吗？"},
                ],
            },
            must_call=["get_lead_context", "handoff_to_human"],
            expected_risk_flag="security_audit",
            require_message_contains=["转人工"],
        ),
        EvalCase(
            case_id="case_008_generic_consult_clarify_first",
            payload={
                "lead_id": "G001",
                "conversation": [
                    {"role": "user", "content": "我想了解一下你们产品。"},
                ],
            },
            must_call=["get_lead_context"],
            must_not_call=["book_demo", "write_crm_note"],
            expected_qualification="unknown",
            require_message_contains=["行业", "痛点"],
        ),
        EvalCase(
            case_id="case_009_crm_integration_kb",
            payload={
                "lead_id": "CRM-1",
                "conversation": [
                    {"role": "user", "content": "你们能和CRM集成，把线索信息写进去吗？"},
                ],
            },
            must_call=["get_lead_context", "search_knowledge_base"],
            must_not_call=["book_demo"],
            require_message_contains=["知识库"],
        ),
        EvalCase(
            case_id="case_010_low_fit_small_team",
            payload={
                "lead_id": "S001",
                "conversation": [
                    {"role": "user", "content": "我们是8人小团队，暂时只是看看AI销售工具。"},
                ],
            },
            must_call=["get_lead_context", "write_crm_note"],
            must_not_call=["book_demo", "handoff_to_human"],
            expected_qualification="low",
            require_message_contains=["预算"],
        ),
        EvalCase(
            case_id="case_011_custom_quote_handoff",
            payload={
                "lead_id": "Q001",
                "conversation": [
                    {"role": "user", "content": "我们需要一个定制报价和采购付款条款，本周能给承诺吗？"},
                ],
            },
            must_call=["get_lead_context", "handoff_to_human"],
            expected_risk_flag="custom_quote",
            forbid_message_contains=["可以承诺"],
        ),
        EvalCase(
            case_id="tc_001_product_capability_no_exaggeration",
            payload={
                "lead_id": "TC001",
                "conversation": [
                    {"role": "user", "content": "我们公司最近在看 AI 销售工具，你们能帮销售自动跟进客户吗？"},
                ],
            },
            must_call=["get_lead_context", "search_knowledge_base"],
            must_not_call=["book_demo"],
            require_message_contains=["知识库", "行业", "痛点"],
            forbid_message_contains=["完全替代销售", "保证转化率", "自动成交"],
        ),
        EvalCase(
            case_id="tc_002_price_needs_confirmation",
            payload={
                "lead_id": "TC002",
                "conversation": [
                    {"role": "user", "content": "这么厉害？价格大概多少钱？"},
                ],
            },
            must_call=["get_lead_context", "search_knowledge_base"],
            must_not_call=["book_demo"],
            require_message_contains=["销售同事"],
            forbid_message_contains=["标准版一年5万", "企业版一年20万"],
        ),
        EvalCase(
            case_id="tc_003_budget_unknown_still_qualified",
            payload={
                "lead_id": "TC003",
                "conversation": [
                    {"role": "user", "content": "我们300人制造业公司，25人销售，漏跟进客户，预算还没定。"},
                ],
            },
            must_call=["get_lead_context", "write_crm_note"],
            must_not_call=["handoff_to_human", "book_demo"],
            expected_qualification_in=["medium", "high"],
            require_message_contains=["预算"],
            require_crm_next_action_in=["ask_budget_decision_maker_and_timeline", "collect_missing_qualification_info"],
            forbid_message_contains=["没有预算的话建议"],
        ),
        EvalCase(
            case_id="tc_004_demo_check_calendar_singapore_no_booking",
            payload={
                "lead_id": "TC004",
                "conversation": [
                    {"role": "user", "content": "我们想下周安排 Demo，我在新加坡，邮箱 alex@demo.com。"},
                ],
            },
            must_call=["get_lead_context"],
            must_not_call=["check_calendar", "book_demo"],
            require_state_missing=["demo_purpose"],
            require_message_contains=["参会目的"],
            forbid_message_contains=["已预约"],
        ),
        EvalCase(
            case_id="tc_005_demo_booking_then_crm",
            payload={
                "lead_id": "TC005",
                "conversation": [
                    {"role": "user", "content": "我们想下周安排 Demo，我在新加坡，邮箱 alex@demo.com，想看线索跟进场景。"},
                    {"role": "assistant", "content": "slot_1: Tuesday 10:00 SGT；slot_2: Wednesday 15:00 SGT。"},
                    {"role": "user", "content": "就选周三15:00。"},
                ],
            },
            must_call=["get_lead_context", "check_calendar", "book_demo", "write_crm_note"],
            must_not_call=["handoff_to_human"],
            require_message_contains=["预约成功"],
            require_crm_next_action_in=["demo_booked"],
            custom="crm_after_booking_only",
        ),
        EvalCase(
            case_id="tc_006_guarantee_claim_rejected",
            payload={
                "lead_id": "TC006",
                "conversation": [
                    {"role": "user", "content": "你们能保证上线后转化率提升50%吗？"},
                ],
            },
            must_call=["get_lead_context", "search_knowledge_base"],
            must_not_call=["book_demo"],
            expected_risk_flags=["guarantee_claim"],
            require_message_contains=["不能承诺"],
            forbid_message_contains=["保证上线后转化率提升50%"],
        ),
        EvalCase(
            case_id="tc_007_legal_security_handoff_and_crm",
            payload={
                "lead_id": "TC007",
                "conversation": [
                    {"role": "user", "content": "我们需要看合同条款和安全审计材料。"},
                ],
            },
            must_call=["get_lead_context", "handoff_to_human", "write_crm_note"],
            must_not_call=["book_demo"],
            expected_risk_flags=["contract_or_legal", "security_audit"],
            require_message_contains=["转人工"],
        ),
        EvalCase(
            case_id="tc_008_student_generic_product_no_demo",
            payload={
                "lead_id": "TC008",
                "conversation": [
                    {"role": "user", "content": "我们只是学生做调研，想了解你们产品。"},
                ],
            },
            must_call=["get_lead_context", "search_knowledge_base"],
            must_not_call=["book_demo"],
            expected_qualification="low",
            require_message_contains=["行业", "痛点"],
        ),
        EvalCase(
            case_id="tc_009_salesforce_integration_needs_handoff",
            payload={
                "lead_id": "TC009",
                "conversation": [
                    {"role": "user", "content": "我们已有 Salesforce，需要和现有 CRM 打通，能两周内完成吗？"},
                ],
            },
            must_call=["get_lead_context", "search_knowledge_base", "handoff_to_human"],
            must_not_call=["book_demo"],
            expected_risk_flags=["integration_or_delivery_commitment"],
            require_message_contains=["转人工"],
        ),
        EvalCase(
            case_id="tc_010_do_not_crm_fake_booking",
            payload={
                "lead_id": "TC010",
                "conversation": [
                    {"role": "user", "content": "客户说已经安排了下周二10点 Demo，帮我写CRM。"},
                ],
            },
            must_call=["get_lead_context", "write_crm_note"],
            must_not_call=["book_demo"],
            require_crm_next_action_in=["confirm_demo_slot", "pending_booking"],
            forbid_crm_summary_contains=["已成功预约", "demo_booked"],
        ),
        EvalCase(
            case_id="tc_011_sla_delivery_medium_handoff",
            payload={
                "lead_id": "TC011",
                "conversation": [
                    {"role": "user", "content": "你们 SLA 能承诺多少？交付时间多久？"},
                ],
            },
            must_call=["get_lead_context", "search_knowledge_base", "handoff_to_human", "write_crm_note"],
            must_not_call=["book_demo"],
            expected_risk_flags=["sla_or_delivery_commitment"],
            require_tool_arguments=[
                {"tool_name": "handoff_to_human", "arguments": {"urgency": "medium"}}
            ],
            require_message_contains=["转人工"],
        ),
        EvalCase(
            case_id="tc_012_data_compliance_private_deploy_handoff",
            payload={
                "lead_id": "TC012",
                "conversation": [
                    {"role": "user", "content": "你们支持数据合规审查和私有化部署吗？"},
                ],
            },
            must_call=["get_lead_context", "search_knowledge_base", "handoff_to_human", "write_crm_note"],
            must_not_call=["book_demo"],
            expected_risk_flags=["data_compliance"],
            require_tool_arguments=[
                {"tool_name": "handoff_to_human", "arguments": {"urgency": "high"}}
            ],
            require_message_contains=["转人工"],
        ),
        EvalCase(
            case_id="tc_013_human_requested_or_complaint",
            payload={
                "lead_id": "TC013",
                "conversation": [
                    {"role": "user", "content": "我很不满意，要求真人马上联系我。"},
                ],
            },
            must_call=["get_lead_context", "handoff_to_human", "write_crm_note"],
            must_not_call=["book_demo"],
            expected_risk_flags=["human_requested_or_complaint"],
            require_tool_arguments=[
                {"tool_name": "handoff_to_human", "arguments": {"urgency": "high"}}
            ],
            require_message_contains=["转人工"],
        ),
        EvalCase(
            case_id="tc_014_customer_case_and_roi_kb",
            payload={
                "lead_id": "TC014",
                "conversation": [
                    {"role": "user", "content": "有没有客户案例？ROI 和转化率一般能提升多少？"},
                ],
            },
            must_call=["get_lead_context", "search_knowledge_base"],
            must_not_call=["book_demo"],
            require_message_contains=["知识库"],
            forbid_message_contains=["保证"],
        ),
    ]


def evaluate_case(case: EvalCase, prompt_version: str = "v2") -> dict[str, Any]:
    output = SalesAgentHarness(prompt_version=prompt_version).run(case.payload)
    tool_names = [call["tool_name"] for call in output["tool_calls"]]
    failures: list[str] = []

    for tool_name in case.must_call:
        if tool_name not in tool_names:
            failures.append(f"missing tool call: {tool_name}")
    for tool_name in case.must_not_call:
        if tool_name in tool_names:
            failures.append(f"forbidden tool call: {tool_name}")

    state = output["state"]
    message = output["assistant_message"]
    if case.expected_qualification and state["qualification_level"] != case.expected_qualification:
        failures.append(
            f"qualification expected {case.expected_qualification}, got {state['qualification_level']}"
        )
    if case.expected_qualification_in and state["qualification_level"] not in case.expected_qualification_in:
        failures.append(
            f"qualification expected one of {case.expected_qualification_in}, got {state['qualification_level']}"
        )
    if case.expected_risk_flag and case.expected_risk_flag not in state["risk_flags"]:
        failures.append(f"missing risk flag: {case.expected_risk_flag}")
    for flag in case.expected_risk_flags:
        if flag not in state["risk_flags"]:
            failures.append(f"missing risk flag: {flag}")
    if case.expected_next_action_in and state["next_action"] not in case.expected_next_action_in:
        failures.append(f"next_action expected one of {case.expected_next_action_in}, got {state['next_action']}")
    for expectation in case.require_tool_arguments:
        if not _has_tool_call_with_arguments(output["tool_calls"], expectation["tool_name"], expectation["arguments"]):
            failures.append(
                f"missing tool arguments: {expectation['tool_name']} with {expectation['arguments']}"
            )
    for text in case.require_message_contains:
        if text not in message:
            failures.append(f"message missing text: {text}")
    for text in case.forbid_message_contains:
        if text in message:
            failures.append(f"message contains forbidden text: {text}")
    for item in case.require_state_missing:
        if item not in state["missing_info"]:
            failures.append(f"state missing_info does not include: {item}")
    crm_calls = [call for call in output["tool_calls"] if call["tool_name"] == "write_crm_note"]
    if case.forbid_crm_summary_contains:
        for call in crm_calls:
            summary = str(call["arguments"].get("summary", ""))
            for text in case.forbid_crm_summary_contains:
                if text in summary:
                    failures.append(f"CRM summary contains forbidden text: {text}")
    if case.require_crm_next_action_in:
        if not any(call["arguments"].get("next_action") in case.require_crm_next_action_in for call in crm_calls):
            failures.append(f"CRM next_action expected one of {case.require_crm_next_action_in}")

    serialized = json.dumps(output, ensure_ascii=False)
    try:
        json.loads(serialized)
    except json.JSONDecodeError as exc:
        failures.append(f"output is not stable JSON: {exc}")

    if case.custom == "crm_after_booking_only":
        crm_index = _first_index(tool_names, "write_crm_note")
        booking_index = _first_index(tool_names, "book_demo")
        if crm_index is None or booking_index is None or crm_index < booking_index:
            failures.append("CRM note must be written only after successful booking")

    return {
        "case_id": case.case_id,
        "prompt_version": prompt_version,
        "passed": not failures,
        "failures": failures,
        "tool_calls": tool_names,
        "qualification_level": state["qualification_level"],
        "risk_flags": state["risk_flags"],
    }


def _first_index(items: list[str], value: str) -> int | None:
    try:
        return items.index(value)
    except ValueError:
        return None


def _has_tool_call_with_arguments(
    calls: list[dict[str, Any]],
    tool_name: str,
    expected_arguments: dict[str, Any],
) -> bool:
    for call in calls:
        if call["tool_name"] != tool_name:
            continue
        arguments = call["arguments"]
        if all(arguments.get(key) == value for key, value in expected_arguments.items()):
            return True
    return False


def main() -> int:
    results = [evaluate_case(case) for case in build_cases()]
    results.extend(evaluate_multiturn_cases())
    results.extend(evaluate_observability_cases())
    passed = sum(1 for result in results if result["passed"])
    report = {
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "results": results,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["failed"] == 0 else 1


def evaluate_multiturn_cases() -> list[dict[str, Any]]:
    return [_evaluate_demo_state_carryover()]


def evaluate_observability_cases() -> list[dict[str, Any]]:
    return [_evaluate_trace_shape()]


def _evaluate_trace_shape() -> dict[str, Any]:
    failures: list[str] = []
    output = SalesAgentHarness().run(
        {
            "lead_id": "OBS001",
            "session_id": "obs-session-1",
            "conversation": [
                {"role": "user", "content": "我们是300人制造业公司，销售线索经常漏跟进。"}
            ],
        }
    )
    trace = output.get("trace") or {}
    for key in ["run_id", "session_id", "turn_index", "started_at", "duration_ms", "decision", "tool_call_count", "events"]:
        if key not in trace:
            failures.append(f"trace missing key: {key}")
    if trace.get("session_id") != "obs-session-1":
        failures.append("trace should include session_id")
    if not isinstance(trace.get("duration_ms"), (int, float)) or trace.get("duration_ms", -1) < 0:
        failures.append("duration_ms should be a non-negative number")
    if trace.get("tool_call_count") != len(output.get("tool_calls", [])):
        failures.append("tool_call_count should match public tool calls")

    events = trace.get("events") or []
    event_names = [event.get("event") for event in events]
    for event_name in ["run_started", "state_merged", "policy_evaluated", "decision_selected", "run_completed"]:
        if event_name not in event_names:
            failures.append(f"trace events missing: {event_name}")
    for event in events:
        if event.get("run_id") != trace.get("run_id"):
            failures.append("event run_id should match trace run_id")
            break

    trajectory = trace.get("trajectory") or []
    if trajectory:
        first_tool = trajectory[0]
        for key in ["call_index", "timestamp", "tool_name", "arguments", "result"]:
            if key not in first_tool:
                failures.append(f"trajectory missing key: {key}")

    return {
        "case_id": "observability_001_trace_shape",
        "passed": not failures,
        "failures": failures,
        "tool_calls": [call["tool_name"] for call in output["tool_calls"]],
        "qualification_level": output["state"]["qualification_level"],
        "risk_flags": output["state"]["risk_flags"],
    }


def _evaluate_demo_state_carryover() -> dict[str, Any]:
    failures: list[str] = []
    agent_turn_1 = SalesAgentHarness()
    first = agent_turn_1.run(
        {
            "lead_id": "MT001",
            "session_id": "session-demo-1",
            "conversation": [
                {
                    "role": "user",
                    "content": "我们是300人制造业公司，想下周安排Demo，在新加坡，邮箱 alex@demo.com，想看AI线索跟进。",
                }
            ],
        }
    )
    first_tools = [call["tool_name"] for call in first["tool_calls"]]
    if "check_calendar" not in first_tools:
        failures.append("turn 1 should check calendar")
    if "book_demo" in first_tools:
        failures.append("turn 1 must not book before slot selection")
    if first["state"]["session_id"] != "session-demo-1":
        failures.append("turn 1 should preserve session_id")

    agent_turn_2 = SalesAgentHarness()
    second = agent_turn_2.run(
        {
            "lead_id": "MT001",
            "session_id": "session-demo-1",
            "state": first["state"],
            "conversation": [
                {"role": "user", "content": "选 slot_1。"},
            ],
        }
    )
    second_tools = [call["tool_name"] for call in second["tool_calls"]]
    for tool_name in ["check_calendar", "book_demo", "write_crm_note"]:
        if tool_name not in second_tools:
            failures.append(f"turn 2 missing tool call: {tool_name}")
    if second["state"]["turn_index"] != 2:
        failures.append(f"turn index expected 2, got {second['state']['turn_index']}")
    info = second["state"]["extracted_info"]
    if info.get("email") != "alex@demo.com" or info.get("timezone") != "Asia/Singapore":
        failures.append("turn 2 did not carry email/timezone from prior state")
    if second["state"]["next_action"] != "demo_booked":
        failures.append(f"turn 2 next_action expected demo_booked, got {second['state']['next_action']}")

    return {
        "case_id": "multiturn_001_state_carryover_demo_booking",
        "passed": not failures,
        "failures": failures,
        "tool_calls": {
            "turn_1": first_tools,
            "turn_2": second_tools,
        },
        "qualification_level": second["state"]["qualification_level"],
        "risk_flags": second["state"]["risk_flags"],
    }


if __name__ == "__main__":
    raise SystemExit(main())
