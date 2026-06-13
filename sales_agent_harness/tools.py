from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolCall:
    tool_name: str
    arguments: dict[str, Any]
    result: Any
    call_index: int
    timestamp: str


@dataclass
class MockSalesTools:
    """Deterministic mock tools with a trajectory record."""

    calls: list[ToolCall] = field(default_factory=list)
    crm_notes: list[dict[str, Any]] = field(default_factory=list)
    bookings: list[dict[str, Any]] = field(default_factory=list)

    def _record(self, tool_name: str, arguments: dict[str, Any], result: Any) -> Any:
        self.calls.append(
            ToolCall(
                tool_name=tool_name,
                arguments=arguments,
                result=result,
                call_index=len(self.calls) + 1,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        )
        return result

    def public_calls(self) -> list[dict[str, Any]]:
        return [
            {"tool_name": call.tool_name, "arguments": call.arguments}
            for call in self.calls
        ]

    def trajectory(self) -> list[dict[str, Any]]:
        return [
            {
                "call_index": call.call_index,
                "timestamp": call.timestamp,
                "tool_name": call.tool_name,
                "arguments": call.arguments,
                "result": call.result,
            }
            for call in self.calls
        ]

    def get_lead_context(self, lead_id: str) -> dict[str, Any]:
        mock_context = {
            "L123": {
                "source": "website",
                "known_company": "Demo Manufacturing",
                "existing_stage": "new",
                "owner": "sales-apac",
            },
            "LEGAL-1": {
                "source": "enterprise inbound",
                "existing_stage": "legal_review",
                "owner": "sales-enterprise",
            },
        }
        result = mock_context.get(
            lead_id,
            {"source": "unknown", "existing_stage": "new", "owner": "unassigned"},
        )
        return self._record("get_lead_context", {"lead_id": lead_id}, result)

    def search_knowledge_base(self, query: str) -> dict[str, Any]:
        normalized = query.lower()
        if any(term in normalized for term in ["price", "pricing", "价格", "报价", "多少钱", "折扣"]):
            answer = "Pricing depends on seats, integrations, and deployment scope. A sales teammate must confirm the quote."
        elif any(term in normalized for term in ["case", "客户案例", "案例"]):
            answer = "Customer references must be confirmed by sales because availability depends on permission and industry fit."
        elif any(term in normalized for term in ["roi", "转化率", "提升"]):
            answer = "ROI and conversion impact vary by funnel quality, process, and implementation. Do not guarantee a fixed percentage."
        elif any(term in normalized for term in ["sla", "服务等级", "交付时间", "交付", "上线时间"]):
            answer = "SLA and delivery timelines depend on contract scope, integrations, and deployment requirements. Sales or delivery must confirm."
        elif any(term in normalized for term in ["security", "安全", "审计", "合同", "法务", "合规", "dpa", "私有化"]):
            answer = "Security, audit, legal, and contract questions require human sales or legal confirmation."
        elif any(term in normalized for term in ["crm", "集成", "integration", "salesforce"]):
            answer = "The product can sync lead notes and next actions into common CRM systems via configured integrations."
        elif any(term in normalized for term in ["功能边界", "功能", "feature", "capability"]):
            answer = "Supported capabilities include lead qualification, basic product Q&A, follow-up summaries, and CRM note preparation. Boundary details should be checked against the current product scope."
        else:
            answer = "The product helps qualify leads, answer basic product questions, and prepare follow-up actions for sales teams."
        result = {"query": query, "answer": answer, "source": "mock_kb_v1"}
        return self._record("search_knowledge_base", {"query": query}, result)

    def check_calendar(self, timezone: str, duration_minutes: int) -> dict[str, Any]:
        slots_by_timezone = {
            "Asia/Singapore": [
                {"slot_id": "slot_1", "label": "Tuesday 10:00 SGT"},
                {"slot_id": "slot_2", "label": "Wednesday 15:00 SGT"},
            ],
            "Asia/Shanghai": [
                {"slot_id": "slot_1", "label": "Tuesday 10:00 CST"},
                {"slot_id": "slot_2", "label": "Wednesday 15:00 CST"},
            ],
            "Europe/London": [
                {"slot_id": "slot_1", "label": "Tuesday 09:30 BST"},
                {"slot_id": "slot_2", "label": "Thursday 14:00 BST"},
            ],
            "America/Los_Angeles": [
                {"slot_id": "slot_1", "label": "Tuesday 11:00 PT"},
                {"slot_id": "slot_2", "label": "Thursday 13:30 PT"},
            ],
        }
        result = {
            "timezone": timezone,
            "duration_minutes": duration_minutes,
            "slots": slots_by_timezone.get(timezone, slots_by_timezone["Asia/Singapore"]),
        }
        return self._record(
            "check_calendar",
            {"timezone": timezone, "duration_minutes": duration_minutes},
            result,
        )

    def book_demo(
        self,
        lead_id: str,
        slot_id: str,
        attendee_email: str,
        summary: str,
    ) -> dict[str, Any]:
        ok = bool(slot_id and "@" in attendee_email and "." in attendee_email)
        result = {
            "booking_id": f"booking_{len(self.bookings) + 1}" if ok else None,
            "status": "confirmed" if ok else "failed",
            "slot_id": slot_id,
        }
        if ok:
            self.bookings.append(
                {
                    "lead_id": lead_id,
                    "slot_id": slot_id,
                    "attendee_email": attendee_email,
                    "summary": summary,
                }
            )
        return self._record(
            "book_demo",
            {
                "lead_id": lead_id,
                "slot_id": slot_id,
                "attendee_email": attendee_email,
                "summary": summary,
            },
            result,
        )

    def write_crm_note(
        self,
        lead_id: str,
        summary: str,
        qualification_level: str,
        next_action: str,
    ) -> dict[str, Any]:
        note = {
            "lead_id": lead_id,
            "summary": summary,
            "qualification_level": qualification_level,
            "next_action": next_action,
        }
        self.crm_notes.append(note)
        result = {"status": "written", "note_id": f"crm_note_{len(self.crm_notes)}"}
        return self._record("write_crm_note", note, result)

    def handoff_to_human(self, lead_id: str, reason: str, urgency: str) -> dict[str, Any]:
        result = {"status": "queued", "owner": "human_sales", "urgency": urgency}
        return self._record(
            "handoff_to_human",
            {"lead_id": lead_id, "reason": reason, "urgency": urgency},
            result,
        )


TOOL_NAMES: dict[str, Callable[..., Any]] = {
    "get_lead_context": MockSalesTools.get_lead_context,
    "search_knowledge_base": MockSalesTools.search_knowledge_base,
    "check_calendar": MockSalesTools.check_calendar,
    "book_demo": MockSalesTools.book_demo,
    "write_crm_note": MockSalesTools.write_crm_note,
    "handoff_to_human": MockSalesTools.handoff_to_human,
}
