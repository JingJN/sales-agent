from __future__ import annotations

import argparse
import json
from typing import Any

from .eval_runner import build_cases, evaluate_case


def compare_prompt_versions(versions: list[str]) -> dict[str, Any]:
    cases = build_cases()
    by_version = {}
    for version in versions:
        results = [evaluate_case(case, prompt_version=version) for case in cases]
        passed_ids = {result["case_id"] for result in results if result["passed"]}
        failed = [result for result in results if not result["passed"]]
        by_version[version] = {
            "total": len(results),
            "passed": len(passed_ids),
            "failed": len(failed),
            "pass_rate": round(len(passed_ids) / len(results), 4) if results else 0.0,
            "failed_cases": [
                {
                    "case_id": result["case_id"],
                    "failures": result["failures"],
                    "tool_calls": result["tool_calls"],
                    "risk_flags": result["risk_flags"],
                    "qualification_level": result["qualification_level"],
                }
                for result in failed
            ],
            "passed_case_ids": sorted(passed_ids),
        }

    pairwise = []
    if len(versions) >= 2:
        baseline = versions[0]
        for candidate in versions[1:]:
            baseline_passed = set(by_version[baseline]["passed_case_ids"])
            candidate_passed = set(by_version[candidate]["passed_case_ids"])
            pairwise.append(
                {
                    "baseline": baseline,
                    "candidate": candidate,
                    "newly_passed": sorted(candidate_passed - baseline_passed),
                    "regressed": sorted(baseline_passed - candidate_passed),
                    "pass_delta": by_version[candidate]["passed"] - by_version[baseline]["passed"],
                    "pass_rate_delta": round(
                        by_version[candidate]["pass_rate"] - by_version[baseline]["pass_rate"],
                        4,
                    ),
                }
            )

    return {
        "comparison_type": "prompt_version",
        "versions": versions,
        "results": by_version,
        "pairwise": pairwise,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare prompt versions on the eval suite.")
    parser.add_argument(
        "--versions",
        nargs="+",
        default=["v1", "v2"],
        help="Prompt versions to compare. First version is the baseline.",
    )
    args = parser.parse_args()
    report = compare_prompt_versions(args.versions)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
