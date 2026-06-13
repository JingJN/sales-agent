from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .agent import SalesAgentHarness


def load_payload(path: str | None) -> dict:
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return json.loads(sys.stdin.read())


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the minimal sales Agent Harness.")
    parser.add_argument("--input", "-i", help="Path to an input JSON file. Reads stdin if omitted.")
    parser.add_argument("--prompt-version", default="v2", help="Prompt/rules version label for trace output.")
    parser.add_argument("--session-id", help="Session id used for persistent multi-turn state.")
    parser.add_argument("--state-file", help="JSON file used to load and save session state.")
    parser.add_argument("--log-file", help="Append one structured JSONL observability record per run.")
    args = parser.parse_args()

    payload = load_payload(args.input)
    if args.session_id:
        payload["session_id"] = args.session_id
    if args.state_file:
        state_file = Path(args.state_file)
        sessions = _load_sessions(state_file)
        session_id = str(payload.get("session_id") or payload.get("lead_id") or "UNKNOWN")
        if "state" not in payload and session_id in sessions:
            payload["state"] = sessions[session_id]
    else:
        state_file = None
        sessions = {}

    result = SalesAgentHarness(prompt_version=args.prompt_version).run(payload)
    if state_file:
        session_id = result["state"]["session_id"]
        sessions[session_id] = result["state"]
        state_file.write_text(json.dumps(sessions, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.log_file:
        _append_log(Path(args.log_file), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _load_sessions(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _append_log(path: Path, result: dict) -> None:
    trace = result["trace"]
    record = {
        "schema_version": "observability.v1",
        "run_id": trace["run_id"],
        "session_id": trace["session_id"],
        "turn_index": trace["turn_index"],
        "started_at": trace["started_at"],
        "duration_ms": trace["duration_ms"],
        "prompt_version": trace["prompt_version"],
        "decision": trace["decision"],
        "qualification_level": result["state"]["qualification_level"],
        "next_action": result["state"]["next_action"],
        "risk_flags": result["state"]["risk_flags"],
        "tool_call_count": trace["tool_call_count"],
        "tool_names": [call["tool_name"] for call in result["tool_calls"]],
        "events": trace["events"],
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
