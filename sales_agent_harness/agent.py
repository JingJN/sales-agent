from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .tools import MockSalesTools


EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
NUMBER_PERSON_RE = re.compile(r"(\d{1,6})\s*(?:人|名|people|employees|员工)", re.I)


@dataclass
class ExtractedLeadInfo:
    company_size: int | None = None
    sales_team_size: int | None = None
    industry: str | None = None
    pain_points: list[str] | None = None
    budget: str | None = None
    decision_maker: str | None = None
    timeline: str | None = None
    email: str | None = None
    timezone: str | None = None
    demo_purpose: str | None = None
    selected_slot_id: str | None = None
    lead_type: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ExtractedLeadInfo":
        if not data:
            return cls()
        return cls(
            company_size=data.get("company_size"),
            sales_team_size=data.get("sales_team_size"),
            industry=data.get("industry"),
            pain_points=list(data.get("pain_points") or []),
            budget=data.get("budget"),
            decision_maker=data.get("decision_maker"),
            timeline=data.get("timeline"),
            email=data.get("email"),
            timezone=data.get("timezone"),
            demo_purpose=data.get("demo_purpose"),
            selected_slot_id=data.get("selected_slot_id"),
            lead_type=data.get("lead_type"),
        )

    def merge(self, newer: "ExtractedLeadInfo") -> "ExtractedLeadInfo":
        pain_points = []
        for value in (self.pain_points or []) + (newer.pain_points or []):
            if value not in pain_points:
                pain_points.append(value)
        return ExtractedLeadInfo(
            company_size=newer.company_size or self.company_size,
            sales_team_size=newer.sales_team_size or self.sales_team_size,
            industry=newer.industry or self.industry,
            pain_points=pain_points,
            budget=newer.budget or self.budget,
            decision_maker=newer.decision_maker or self.decision_maker,
            timeline=newer.timeline or self.timeline,
            email=newer.email or self.email,
            timezone=newer.timezone or self.timezone,
            demo_purpose=newer.demo_purpose or self.demo_purpose,
            selected_slot_id=newer.selected_slot_id or self.selected_slot_id,
            lead_type=newer.lead_type or self.lead_type,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "company_size": self.company_size,
            "sales_team_size": self.sales_team_size,
            "industry": self.industry,
            "pain_points": self.pain_points or [],
            "budget": self.budget,
            "decision_maker": self.decision_maker,
            "timeline": self.timeline,
            "email": self.email,
            "timezone": self.timezone,
            "demo_purpose": self.demo_purpose,
            "selected_slot_id": self.selected_slot_id,
            "lead_type": self.lead_type,
        }


class SalesAgentHarness:
    """Small deterministic harness for the sales-agent assignment."""

    risk_patterns = {
        "contract_or_legal": ["合同", "法务", "条款", "dpa", "msa", "legal", "contract"],
        "security_audit": ["安全审计", "安全评估", "渗透测试", "soc2", "iso27001", "security audit"],
        "data_compliance": ["数据合规", "隐私合规", "gdpr", "合规审查", "私有化部署", "私有化"],
        "custom_quote": ["定制报价", "custom quote", "采购流程", "采购条款", "付款条款", "折扣"],
        "sla_or_delivery_commitment": ["sla", "服务等级", "交付时间", "多久交付", "上线时间承诺"],
        "guarantee_claim": ["保证转化率", "保证成交", "替代销售", "保证提升", "提升50%"],
        "integration_or_delivery_commitment": ["复杂集成", "非标准集成", "两周打通", "两周内打通", "两周内完成", "两周完成", "交付承诺", "上线承诺"],
        "human_requested_or_complaint": ["要求真人", "真人联系", "转人工", "人工联系", "投诉", "不满意", "强烈不满"],
    }

    def __init__(self, prompt_version: str = "v2", tools: MockSalesTools | None = None) -> None:
        self.prompt_version = prompt_version
        self.tools = tools or MockSalesTools()

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        started_perf = time.perf_counter()
        started_at = self._utc_now()
        run_id = str(uuid.uuid4())
        lead_id = str(payload.get("lead_id") or "UNKNOWN")
        conversation = payload.get("conversation") or []
        text = self._conversation_text(conversation)
        last_user = self._last_user_message(conversation)
        previous_state = payload.get("state") or payload.get("previous_state") or {}
        session_id = str(payload.get("session_id") or previous_state.get("session_id") or lead_id)
        turn_index = int(previous_state.get("turn_index") or 0) + 1
        events = [
            self._trace_event(
                "run_started",
                run_id,
                session_id,
                turn_index,
                {"lead_id": lead_id, "input_turns": len(conversation), "has_previous_state": bool(previous_state)},
            )
        ]

        context = self.tools.get_lead_context(lead_id)
        current_info = self._extract_info(text)
        previous_info = ExtractedLeadInfo.from_dict(previous_state.get("extracted_info"))
        info = previous_info.merge(current_info)
        current_risk_flags = self._detect_risks(text)
        risk_flags = self._merge_lists(previous_state.get("risk_flags") or [], current_risk_flags)
        asks_demo = self._asks_for_demo(text) or self._demo_flow_is_active(previous_state)
        asks_product_or_price = self._asks_product_or_price(last_user)
        qualification_level = self._qualification_level(info, asks_demo)
        missing_info = self._missing_info(info, asks_demo)
        events.extend(
            [
                self._trace_event(
                    "state_merged",
                    run_id,
                    session_id,
                    turn_index,
                    {
                        "known_fields": [key for key, value in info.to_dict().items() if value],
                        "missing_info": missing_info,
                    },
                ),
                self._trace_event(
                    "policy_evaluated",
                    run_id,
                    session_id,
                    turn_index,
                    {
                        "current_risk_flags": current_risk_flags,
                        "risk_flags": risk_flags,
                        "asks_demo": asks_demo,
                        "asks_product_or_price": asks_product_or_price,
                    },
                ),
            ]
        )

        if self._asks_to_write_crm(text):
            decision = "crm_unverified_booking_note"
            qualification_level = qualification_level if qualification_level != "unknown" else "low"
            next_action = "confirm_demo_slot"
            self.tools.write_crm_note(
                lead_id=lead_id,
                summary=(
                    "pain_points=unknown; stage=pending_booking_confirmation; "
                    "next_action=confirm_demo_slot; confidence=low; booking_status=unverified"
                ),
                qualification_level=qualification_level,
                next_action=next_action,
            )
            message = "我可以先记录 CRM，但不会写成已成功预约；需要先核对 Demo 时间、邮箱、时区和预约是否真实完成。"
        elif "guarantee_claim" in current_risk_flags:
            decision = "reject_guarantee_claim"
            self.tools.search_knowledge_base(last_user)
            message = "不能承诺固定转化率或保证提升 50%。我可以说明产品通常支持的线索跟进能力，并根据你们场景建议是否安排 Demo 评估。"
            next_action = "explain_capabilities_and_clarify_fit"
        elif current_risk_flags:
            decision = "human_handoff_for_risk"
            if self._risk_requires_knowledge_lookup(current_risk_flags):
                self.tools.search_knowledge_base(last_user)
            reason = ", ".join(current_risk_flags)
            self.tools.handoff_to_human(lead_id, reason=reason, urgency=self._handoff_urgency(current_risk_flags))
            self.tools.write_crm_note(
                lead_id=lead_id,
                summary=self._crm_summary(info, stage="human_handoff_required", next_action="human_follow_up"),
                qualification_level=qualification_level,
                next_action="human_follow_up",
            )
            message = "这个问题需要销售或相关专员确认，我已经为你转人工跟进，避免给出未经确认的承诺。"
            next_action = "human_follow_up"
        elif asks_demo:
            decision = "demo_flow"
            message, next_action = self._handle_demo_flow(lead_id, info, qualification_level, missing_info)
        elif asks_product_or_price:
            decision = "knowledge_response"
            kb = self.tools.search_knowledge_base(last_user)
            if info.pain_points or info.company_size or info.industry:
                next_action_for_crm = self._next_sales_action(info)
                self.tools.write_crm_note(
                    lead_id=lead_id,
                    summary=self._crm_summary(info, stage="product_discovery", next_action=next_action_for_crm),
                    qualification_level=qualification_level,
                    next_action=next_action_for_crm,
                )
                message = self._knowledge_response(last_user, kb["answer"], info) + " " + self._discovery_response(info)
            else:
                message = self._knowledge_response(last_user, kb["answer"], info)
            next_action = "clarify_needs"
        elif info.pain_points or info.company_size or info.industry:
            decision = "qualified_discovery"
            next_action = self._next_sales_action(info)
            summary = self._crm_summary(info, stage="qualified_discovery", next_action=next_action)
            self.tools.write_crm_note(
                lead_id=lead_id,
                summary=summary,
                qualification_level=qualification_level,
                next_action=next_action,
            )
            message = self._discovery_response(info)
        else:
            decision = "collect_basic_info"
            message = "为了判断我们是否能帮上忙，想先了解你们的行业、销售团队规模，以及目前在线索跟进上的主要痛点。"
            next_action = "collect_basic_qualification_info"

        state = {
            "qualification_level": qualification_level,
            "missing_info": missing_info,
            "next_action": next_action,
            "risk_flags": risk_flags,
            "extracted_info": info.to_dict(),
            "lead_context": context,
            "session_id": session_id,
            "turn_index": turn_index,
            "memory": {
                "known_fields": info.to_dict(),
                "demo": self._demo_memory(next_action, missing_info),
            },
        }
        duration_ms = round((time.perf_counter() - started_perf) * 1000, 3)
        events.extend(
            [
                self._trace_event(
                    "decision_selected",
                    run_id,
                    session_id,
                    turn_index,
                    {
                        "decision": decision,
                        "next_action": next_action,
                        "qualification_level": qualification_level,
                    },
                ),
                self._trace_event(
                    "run_completed",
                    run_id,
                    session_id,
                    turn_index,
                    {
                        "duration_ms": duration_ms,
                        "tool_call_count": len(self.tools.calls),
                        "output_state_keys": list(state.keys()),
                    },
                ),
            ]
        )
        return {
            "assistant_message": message,
            "tool_calls": self.tools.public_calls(),
            "state": state,
            "trace": {
                "run_id": run_id,
                "session_id": session_id,
                "turn_index": turn_index,
                "started_at": started_at,
                "duration_ms": duration_ms,
                "prompt_version": self.prompt_version,
                "decision": decision,
                "tool_call_count": len(self.tools.calls),
                "trajectory": self.tools.trajectory(),
                "events": events,
            },
        }

    def _handle_demo_flow(
        self,
        lead_id: str,
        info: ExtractedLeadInfo,
        qualification_level: str,
        missing_info: list[str],
    ) -> tuple[str, str]:
        demo_required_fields = ["email", "timezone"] if self._is_v1() else ["email", "timezone", "demo_purpose"]
        required = [item for item in demo_required_fields if item in missing_info]
        if required:
            return (
                "可以安排 Demo。预约前我需要先确认：邮箱、时区和本次参会目的。"
                + self._specific_missing_suffix(required),
                "collect_demo_required_info",
            )

        calendar = self.tools.check_calendar(info.timezone or "Asia/Singapore", duration_minutes=30)
        slots = calendar["slots"]
        if not info.selected_slot_id:
            slot_text = "；".join(f"{slot['slot_id']}: {slot['label']}" for slot in slots)
            return (
                f"我查到以下可选时间：{slot_text}。请告诉我你想选择哪个 slot，我再正式预约。",
                "ask_user_to_choose_demo_slot",
            )

        slot_ids = {slot["slot_id"] for slot in slots}
        selected_slot_id = info.selected_slot_id if info.selected_slot_id in slot_ids else slots[0]["slot_id"]
        booking = self.tools.book_demo(
            lead_id=lead_id,
            slot_id=selected_slot_id,
            attendee_email=info.email or "",
            summary=info.demo_purpose or "Sales AI lead follow-up demo",
        )
        if booking["status"] != "confirmed":
            return ("我还不能确认预约，邮箱或时间信息需要再核对一下。", "repair_demo_booking_info")

        summary = self._crm_summary(info, stage="demo_booked", next_action="demo_booked")
        self.tools.write_crm_note(
            lead_id=lead_id,
            summary=summary,
            qualification_level=qualification_level,
            next_action="demo_booked",
        )
        return ("Demo 已预约成功，我会把参会目的和关键背景同步给销售顾问。", "demo_booked")

    def _extract_info(self, text: str) -> ExtractedLeadInfo:
        lower = text.lower()
        numbers = [int(match.group(1)) for match in NUMBER_PERSON_RE.finditer(text)]
        company_size = numbers[0] if numbers else None
        sales_team_size = None
        sales_team_match = re.search(r"销售团队\s*(\d{1,5})\s*(?:人|名)?", text)
        if sales_team_match:
            sales_team_size = int(sales_team_match.group(1))
        elif len(numbers) >= 2:
            sales_team_size = numbers[1]

        industry = None
        industry_map = {
            "制造": "manufacturing",
            "manufacturing": "manufacturing",
            "金融": "finance",
            "医疗": "healthcare",
            "教育": "education",
            "saas": "saas",
            "电商": "ecommerce",
        }
        for key, value in industry_map.items():
            if key in lower:
                industry = value
                break

        pain_points = []
        pain_map = {
            "漏跟进": "missed_follow_up",
            "漏掉客户": "missed_follow_up",
            "不及时": "slow_follow_up",
            "线索": "lead_management",
            "转化率": "conversion_rate",
            "人工": "manual_work",
        }
        for key, value in pain_map.items():
            if key in text and value not in pain_points:
                pain_points.append(value)

        budget = None
        if "还没定" in text or "没有预算" in text or "预算未定" in text:
            budget = "not_decided"
        elif re.search(r"(预算|budget).{0,12}(\d+[万kK]?)", text):
            budget = "provided"

        decision_maker = None
        if any(term in text for term in ["老板", "CEO", "负责人", "决策人", "采购"]):
            decision_maker = "mentioned"

        timeline = None
        if any(term in text for term in ["下周", "本周", "明天", "周二", "周三"]):
            timeline = "near_term"
        elif any(term in text for term in ["本季度", "这个季度", "一个月", "两个月"]):
            timeline = "this_quarter"

        email_match = EMAIL_RE.search(text)
        email = email_match.group(0) if email_match else None
        timezone = self._extract_timezone(text)
        demo_purpose = self._extract_demo_purpose(text, pain_points)
        selected_slot_id = self._extract_selected_slot(text)
        lead_type = self._extract_lead_type(text)

        return ExtractedLeadInfo(
            company_size=company_size,
            sales_team_size=sales_team_size,
            industry=industry,
            pain_points=pain_points,
            budget=budget,
            decision_maker=decision_maker,
            timeline=timeline,
            email=email,
            timezone=timezone,
            demo_purpose=demo_purpose,
            selected_slot_id=selected_slot_id,
            lead_type=lead_type,
        )

    def _extract_timezone(self, text: str) -> str | None:
        timezone_markers = {
            "新加坡": "Asia/Singapore",
            "singapore": "Asia/Singapore",
            "上海": "Asia/Shanghai",
            "北京": "Asia/Shanghai",
            "中国": "Asia/Shanghai",
            "伦敦": "Europe/London",
            "london": "Europe/London",
            "英国": "Europe/London",
            "美西": "America/Los_Angeles",
            "加州": "America/Los_Angeles",
        }
        lower = text.lower()
        for marker, timezone in timezone_markers.items():
            if marker in lower:
                return timezone
        explicit = re.search(r"(Asia/[A-Za-z_]+|Europe/[A-Za-z_]+|America/[A-Za-z_]+)", text)
        return explicit.group(1) if explicit else None

    def _extract_demo_purpose(self, text: str, pain_points: list[str]) -> str | None:
        if pain_points:
            return "understand AI-assisted lead follow-up for current sales pain points"
        if any(term in text for term in ["参会目的", "看看", "想看", "了解", "评估", "试用", "场景"]):
            return "evaluate product fit"
        return None

    def _extract_lead_type(self, text: str) -> str | None:
        if any(term in text for term in ["学生", "做调研", "学习", "课程", "论文"]):
            return "student_research"
        return None

    def _extract_selected_slot(self, text: str) -> str | None:
        slot_match = re.search(r"slot[_\s-]?([12])", text, re.I)
        if slot_match:
            return f"slot_{slot_match.group(1)}"
        if "周二" in text or "tuesday" in text.lower():
            return "slot_1"
        if "周三" in text or "wednesday" in text.lower():
            return "slot_2"
        return None

    def _detect_risks(self, text: str) -> list[str]:
        lower = text.lower()
        flags = []
        for flag, patterns in self._active_risk_patterns().items():
            if any(pattern in lower for pattern in patterns):
                flags.append(flag)
        return flags

    def _missing_info(self, info: ExtractedLeadInfo, asks_demo: bool) -> list[str]:
        missing = []
        if not info.company_size:
            missing.append("company_size")
        if not info.industry:
            missing.append("industry")
        if not info.pain_points:
            missing.append("pain_points")
        if not info.budget:
            missing.append("budget")
        if not info.decision_maker:
            missing.append("decision_maker")
        if not info.timeline:
            missing.append("timeline")
        if asks_demo:
            if not info.email:
                missing.append("email")
            if not info.timezone:
                missing.append("timezone")
            if not info.demo_purpose:
                missing.append("demo_purpose")
        return missing

    def _qualification_level(self, info: ExtractedLeadInfo, asks_demo: bool) -> str:
        if info.lead_type == "student_research" and not self._is_v1():
            return "low"
        score = 0
        if info.company_size and info.company_size >= 200:
            score += 2
        elif info.company_size and info.company_size >= 50:
            score += 1
        elif info.company_size:
            score += 1
        if info.sales_team_size and info.sales_team_size >= 10:
            score += 1
        if info.industry:
            score += 1
        if info.pain_points:
            score += 2
        if info.timeline:
            score += 1
        if asks_demo:
            score += 2
        if info.budget == "provided":
            score += 1
        if score >= 6:
            return "high"
        if score >= 3:
            return "medium"
        if score > 0:
            return "low"
        return "unknown"

    def _next_sales_action(self, info: ExtractedLeadInfo) -> str:
        if info.pain_points and info.company_size:
            return "ask_budget_decision_maker_and_timeline"
        return "collect_missing_qualification_info"

    def _crm_summary(self, info: ExtractedLeadInfo, stage: str, next_action: str) -> str:
        pain = ", ".join(info.pain_points or ["unknown"])
        confidence = "medium"
        if info.company_size and info.industry and info.pain_points:
            confidence = "high"
        return (
            f"pain_points={pain}; stage={stage}; next_action={next_action}; "
            f"confidence={confidence}; company_size={info.company_size}; "
            f"industry={info.industry}; budget={info.budget or 'unknown'}"
        )

    def _discovery_response(self, info: ExtractedLeadInfo) -> str:
        questions = []
        if not info.budget:
            questions.append("预算范围")
        if not info.decision_maker:
            questions.append("决策人或评估负责人")
        if not info.timeline:
            questions.append("希望上线或评估的时间")
        budget_prefix = "预算暂未确定也可以继续评估。 " if info.budget == "not_decided" else ""
        if questions:
            return budget_prefix + "你们的线索跟进痛点比较明确。为了判断是否适合销售继续跟进，我还想确认：" + "、".join(questions) + "。"
        return budget_prefix + "这些信息已经足够进入销售跟进，我会记录当前痛点并建议安排下一步沟通。"

    def _knowledge_response(self, user_message: str, kb_answer: str, info: ExtractedLeadInfo) -> str:
        if any(term in user_message for term in ["价格", "报价", "多少钱", "price", "pricing"]):
            return "价格会受席位、集成和部署范围影响，我不能直接编造报价；可以由销售同事基于你们情况确认。"
        return f"根据知识库：{kb_answer} 想更准确判断匹配度的话，我还需要了解你们的行业、团队规模和主要痛点。"

    def _specific_missing_suffix(self, missing: list[str]) -> str:
        labels = {
            "email": "可接收邀请的邮箱",
            "timezone": "你所在时区",
            "demo_purpose": "希望在 Demo 中重点看的内容",
        }
        return " 目前还缺：" + "、".join(labels[item] for item in missing) + "。"

    def _conversation_text(self, conversation: list[dict[str, str]]) -> str:
        return "\n".join(str(turn.get("content", "")) for turn in conversation)

    def _last_user_message(self, conversation: list[dict[str, str]]) -> str:
        for turn in reversed(conversation):
            if turn.get("role") == "user":
                return str(turn.get("content", ""))
        return ""

    def _demo_flow_is_active(self, previous_state: dict[str, Any]) -> bool:
        next_action = previous_state.get("next_action")
        return next_action in {
            "collect_demo_required_info",
            "ask_user_to_choose_demo_slot",
            "repair_demo_booking_info",
        }

    def _asks_for_demo(self, text: str) -> bool:
        lower = text.lower()
        return any(term in lower for term in ["demo", "演示", "预约", "安排一个"])

    def _asks_product_or_price(self, text: str) -> bool:
        lower = text.lower()
        if self._is_v1():
            return any(
                term in lower
                for term in [
                    "能做什么",
                    "功能",
                    "产品",
                    "价格",
                    "报价",
                    "多少钱",
                    "crm",
                    "集成",
                    "自动跟进",
                    "ai 销售",
                    "ai销售",
                    "price",
                    "pricing",
                ]
            )
        return any(
            term in lower
            for term in [
                "能做什么",
                "功能",
                "功能边界",
                "产品",
                "客户案例",
                "案例",
                "roi",
                "ROI",
                "转化率",
                "sla",
                "SLA",
                "交付时间",
                "交付",
                "价格",
                "报价",
                "多少钱",
                "crm",
                "集成",
                "自动跟进",
                "ai 销售",
                "ai销售",
                "price",
                "pricing",
            ]
        )

    def _asks_to_write_crm(self, text: str) -> bool:
        return "写crm" in text.lower().replace(" ", "") or "写入crm" in text.lower().replace(" ", "")

    def _is_v1(self) -> bool:
        return self.prompt_version.lower() == "v1"

    def _active_risk_patterns(self) -> dict[str, list[str]]:
        if not self._is_v1():
            return self.risk_patterns
        return {
            "contract_or_legal": self.risk_patterns["contract_or_legal"],
            "security_audit": self.risk_patterns["security_audit"],
            "custom_quote": self.risk_patterns["custom_quote"],
        }

    def _merge_lists(self, older: list[str], newer: list[str]) -> list[str]:
        merged = []
        for value in older + newer:
            if value not in merged:
                merged.append(value)
        return merged

    def _risk_requires_knowledge_lookup(self, risk_flags: list[str]) -> bool:
        kb_backed_risks = {
            "security_audit",
            "data_compliance",
            "sla_or_delivery_commitment",
            "integration_or_delivery_commitment",
            "custom_quote",
        }
        return any(flag in kb_backed_risks for flag in risk_flags)

    def _handoff_urgency(self, risk_flags: list[str]) -> str:
        high_urgency = {
            "contract_or_legal",
            "security_audit",
            "data_compliance",
            "human_requested_or_complaint",
        }
        if any(flag in high_urgency for flag in risk_flags):
            return "high"
        return "medium"

    def _demo_memory(self, next_action: str, missing_info: list[str]) -> dict[str, Any]:
        calendar_calls = [
            call for call in self.tools.trajectory() if call["tool_name"] == "check_calendar"
        ]
        latest_calendar = calendar_calls[-1]["result"] if calendar_calls else None
        return {
            "status": next_action if "demo" in next_action or "slot" in next_action else "not_active",
            "missing_required_info": [
                item for item in missing_info if item in {"email", "timezone", "demo_purpose"}
            ],
            "last_calendar": latest_calendar,
        }

    def _utc_now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _trace_event(
        self,
        event: str,
        run_id: str,
        session_id: str,
        turn_index: int,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "timestamp": self._utc_now(),
            "event": event,
            "run_id": run_id,
            "session_id": session_id,
            "turn_index": turn_index,
            "data": data,
        }
