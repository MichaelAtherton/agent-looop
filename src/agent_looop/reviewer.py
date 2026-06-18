"""Separate reviewer/checker pass for worker output.

The reviewer is a deterministic gate before draft PR creation. It returns one of:
- pass: draft PR may be opened;
- revise: one in-scope repair attempt is allowed;
- human_escalation: stop, no PR, human decision required.
"""

from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from agent_looop.manager_dry_run import fetch_issues
from agent_looop.worker_prototype import REQUIRED_LABELS, SKIP_LABELS


@dataclass(frozen=True)
class ReviewInput:
    issue_number: int
    issue_title: str
    issue_labels: list[str]
    changed_files: list[str]
    verification_passed: bool
    plan_exists: bool
    run_report_exists: bool
    diff_text: str


@dataclass(frozen=True)
class ReviewResult:
    issue_number: int
    issue_title: str
    recommendation: str
    repair_attempt_allowed: bool
    critical_issues: list[str]
    warnings: list[str]
    suggestions: list[str]
    human_question: str
    reviewed_files: list[str]


def review_worker_output(review_input: ReviewInput) -> ReviewResult:
    critical: list[str] = []
    warnings: list[str] = []
    suggestions: list[str] = []

    labels = set(review_input.issue_labels)
    if not REQUIRED_LABELS.issubset(labels) or labels & SKIP_LABELS:
        critical.append(
            "Worker output is for an ineligible issue; required labels are risk:low + agent:ready with no skip labels."
        )

    allowed_files = _allowed_files_for_labels(labels, review_input.issue_number)
    out_of_scope = [
        file for file in review_input.changed_files if not _is_allowed_file(file, allowed_files)
    ]
    if out_of_scope:
        critical.append(f"Out-of-scope file changes detected: {', '.join(out_of_scope)}")

    if not review_input.plan_exists:
        critical.append("Worker plan is missing; plan-before-edit is a hard gate.")

    if not review_input.verification_passed:
        warnings.append("Verification did not pass; worker may make one in-scope repair attempt if scope remains valid.")

    if not review_input.run_report_exists:
        warnings.append("Worker run report is missing or was not changed; add/update the run report before PR.")

    if "type:docs" in labels:
        if "docs/getting-started.md" not in review_input.diff_text:
            warnings.append("Docs diff does not show the expected getting-started link target.")
        if any(file.startswith("src/") or file.startswith("tests/") for file in review_input.changed_files):
            critical.append("Docs task changed code/test files, which is out-of-scope for this issue.")

    if critical:
        return ReviewResult(
            issue_number=review_input.issue_number,
            issue_title=review_input.issue_title,
            recommendation="human_escalation",
            repair_attempt_allowed=False,
            critical_issues=critical,
            warnings=warnings,
            suggestions=suggestions,
            human_question="Should this worker run be discarded, repaired manually, or should policy be tightened before retrying?",
            reviewed_files=review_input.changed_files,
        )

    if warnings:
        return ReviewResult(
            issue_number=review_input.issue_number,
            issue_title=review_input.issue_title,
            recommendation="revise",
            repair_attempt_allowed=True,
            critical_issues=[],
            warnings=warnings,
            suggestions=suggestions,
            human_question="",
            reviewed_files=review_input.changed_files,
        )

    suggestions.append("Draft PR may be opened with this reviewer result included in the PR body.")
    return ReviewResult(
        issue_number=review_input.issue_number,
        issue_title=review_input.issue_title,
        recommendation="pass",
        repair_attempt_allowed=False,
        critical_issues=[],
        warnings=[],
        suggestions=suggestions,
        human_question="",
        reviewed_files=review_input.changed_files,
    )


def build_review_input(repo: str, root: Path, issue_number: int) -> ReviewInput:
    issues = fetch_issues(repo)
    issue = next((item for item in issues if item.number == issue_number), None)
    if issue is None:
        raise RuntimeError(f"Issue #{issue_number} not found in {repo}")

    changed_files = _changed_files(root)
    plan_exists = (root / "reports" / "worker-plans" / f"issue-{issue_number}-plan.md").exists()
    run_report_exists = (root / "reports" / "worker-runs" / f"issue-{issue_number}-worker-run.md").exists()
    diff_text = _run(["git", "diff", "main...HEAD", "--"], cwd=root).stdout
    verification_passed = "Result: pass" in (
        (root / "reports" / "worker-runs" / f"issue-{issue_number}-worker-run.md").read_text(encoding="utf-8")
        if run_report_exists
        else ""
    )
    return ReviewInput(
        issue_number=issue.number,
        issue_title=issue.title,
        issue_labels=issue.labels,
        changed_files=changed_files,
        verification_passed=verification_passed,
        plan_exists=plan_exists,
        run_report_exists=run_report_exists,
        diff_text=diff_text,
    )


def write_review_report(root: Path, review: ReviewResult) -> Path:
    report_dir = root / "reports" / "reviewer-runs"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"issue-{review.issue_number}-reviewer-report.md"
    report_path.write_text(render_review_report(review), encoding="utf-8")
    return report_path


def render_review_report(review: ReviewResult) -> str:
    lines = [
        "# Reviewer Report",
        "",
        "## Summary",
        f"- Run time: {datetime.now(timezone.utc).isoformat()}",
        f"- Issue: #{review.issue_number} {review.issue_title}",
        f"- Recommendation: {review.recommendation}",
        f"- Repair attempt allowed: {'yes' if review.repair_attempt_allowed else 'no'}",
        "",
        "## Reviewed files",
        *(f"- `{file}`" for file in review.reviewed_files),
        "",
        "## Critical issues",
        *(_list_or_none(review.critical_issues)),
        "",
        "## Warnings",
        *(_list_or_none(review.warnings)),
        "",
        "## Suggestions",
        *(_list_or_none(review.suggestions)),
    ]
    if review.human_question:
        lines.extend(["", "## Human question", review.human_question])
    lines.extend(["", "## Next gate", _next_gate(review), ""])
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run separate reviewer/checker pass over worker output.")
    parser.add_argument("--repo", required=True, help="GitHub repository in OWNER/REPO form")
    parser.add_argument("--worktree", required=True, help="Worker worktree path")
    parser.add_argument("--issue", type=int, required=True, help="Issue number under review")
    args = parser.parse_args(argv)

    root = Path(args.worktree).resolve()
    review_input = build_review_input(args.repo, root, args.issue)
    review = review_worker_output(review_input)
    report_path = write_review_report(root, review)
    print(f"Recommendation: {review.recommendation}")
    print(f"Repair attempt allowed: {'yes' if review.repair_attempt_allowed else 'no'}")
    print(f"Report: {report_path}")
    if review.critical_issues:
        print("Critical issues:")
        for item in review.critical_issues:
            print(f"- {item}")
    if review.warnings:
        print("Warnings:")
        for item in review.warnings:
            print(f"- {item}")
    return 0 if review.recommendation == "pass" else 1


def _allowed_files_for_labels(labels: set[str], issue_number: int) -> list[str]:
    report_prefixes = [
        f"reports/worker-plans/issue-{issue_number}-plan.md",
        f"reports/worker-runs/issue-{issue_number}-worker-run.md",
        f"reports/reviewer-runs/issue-{issue_number}-reviewer-report.md",
    ]
    if "type:docs" in labels:
        return ["README.md", *report_prefixes]
    if "type:test" in labels:
        return ["tests/test_parser.py", *report_prefixes]
    return report_prefixes


def _is_allowed_file(file: str, allowed_files: Sequence[str]) -> bool:
    return file in allowed_files


def _changed_files(root: Path) -> list[str]:
    tracked = _run(["git", "diff", "--name-only", "main...HEAD"], cwd=root).stdout.splitlines()
    untracked = [
        line[3:].strip()
        for line in _run(["git", "status", "--short", "--untracked-files=all"], cwd=root).stdout.splitlines()
        if line.startswith("?? ")
    ]
    return sorted(set(tracked + untracked))


def _list_or_none(items: Sequence[str]) -> list[str]:
    return [f"- {item}" for item in items] if items else ["- none"]


def _next_gate(review: ReviewResult) -> str:
    if review.recommendation == "pass":
        return "Draft PR may be opened with this reviewer result included in the PR body."
    if review.recommendation == "revise":
        return "Worker may make one in-scope repair attempt, rerun verification, and request review again."
    return "Stop. Do not open a PR. Ask the human question and wait for direction."


def _run(args: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=True)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
