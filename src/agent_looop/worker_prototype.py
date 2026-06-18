"""Worker prototype for one eligible docs/test issue.

The worker is intentionally narrow:
- selects exactly one oldest eligible issue;
- allows only `type:docs` and `type:test` in this prototype;
- writes a plan before editing;
- makes deterministic fixture changes for the smoke-test tasks;
- runs verification;
- stops before reviewer/PR/merge.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from agent_looop.manager_dry_run import Issue, fetch_issues

REQUIRED_LABELS = {"risk:low", "agent:ready"}
SKIP_LABELS = {"needs:human", "agent:blocked", "risk:medium", "risk:high"}
ALLOWED_TYPES = {"type:docs", "type:test"}


@dataclass(frozen=True)
class TaskPacket:
    task_id: str
    issue_url: str
    goal: str
    source_evidence: str
    agent_assessment: str
    allowed_actions: list[str]
    forbidden_actions: list[str]
    expected_output: str
    acceptance_criteria: list[str]
    verification_method: str
    escalation_rules: list[str]


@dataclass(frozen=True)
class WorkerResult:
    issue_number: int
    branch: str
    worktree_path: Path
    plan_path: Path
    report_path: Path
    changed_files: list[str]
    verification_command: str
    verification_passed: bool
    verification_output: str


def select_oldest_eligible_issue(issues: Sequence[Issue]) -> Issue | None:
    """Return the oldest eligible issue, or None if none are safe for worker."""
    for issue in sorted(issues, key=lambda item: item.number):
        labels = set(issue.labels)
        if not REQUIRED_LABELS.issubset(labels):
            continue
        if labels & SKIP_LABELS:
            continue
        if not labels & ALLOWED_TYPES:
            continue
        return issue
    return None


def build_task_packet(issue: Issue) -> TaskPacket:
    labels = set(issue.labels)
    if "type:docs" in labels:
        return TaskPacket(
            task_id=f"issue-{issue.number}",
            issue_url=issue.url,
            goal=issue.title,
            source_evidence=issue.body,
            agent_assessment=", ".join(issue.labels),
            allowed_actions=["Edit documentation files only"],
            forbidden_actions=[
                "No code changes",
                "No unrelated cleanup",
                "No merge/deploy/publish/repo settings/secrets/permissions changes",
            ],
            expected_output="README link corrected to the existing getting-started document",
            acceptance_criteria=[
                "README.md links to docs/getting-started.md",
                "No code files are changed",
                "The target documentation file exists",
            ],
            verification_method="Inspect README diff and confirm docs/getting-started.md exists",
            escalation_rules=[
                "Stop if docs/getting-started.md does not exist",
                "Stop if requested change requires code edits",
            ],
        )
    if "type:test" in labels:
        return TaskPacket(
            task_id=f"issue-{issue.number}",
            issue_url=issue.url,
            goal=issue.title,
            source_evidence=issue.body,
            agent_assessment=", ".join(issue.labels),
            allowed_actions=["Edit tests only unless documented behavior is false"],
            forbidden_actions=[
                "No unrelated production code changes",
                "No unrelated cleanup",
                "No merge/deploy/publish/repo settings/secrets/permissions changes",
            ],
            expected_output="Regression test added for empty parser input",
            acceptance_criteria=[
                "tests/test_parser.py includes a test for empty input",
                'The test asserts that parse_input("") raises ValueError',
                "python -m pytest passes",
            ],
            verification_method="Run python -m pytest",
            escalation_rules=[
                "Stop if production behavior must change beyond documented parser behavior",
                "Stop if tests fail after one focused fix attempt",
            ],
        )
    raise ValueError(f"Issue #{issue.number} is not an allowed worker type: {issue.labels}")


def write_worker_plan(root: Path, packet: TaskPacket) -> Path:
    """Persist the worker plan before any implementation edits."""
    plan_dir = root / "reports" / "worker-plans" if (root / "reports").exists() else root
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_path = plan_dir / f"{packet.task_id}-plan.md"
    expected_files = _expected_files(packet)
    plan_path.write_text(
        "\n".join(
            [
                f"# Worker Plan — {packet.task_id}",
                "",
                "Objective:",
                packet.goal,
                "",
                "Scope:",
                "; ".join(packet.allowed_actions),
                "",
                "Out of scope:",
                "\n".join(f"- {item}" for item in packet.forbidden_actions),
                "",
                "Files expected to touch:",
                "\n".join(f"- {item}" for item in expected_files),
                "",
                "Steps:",
                "1. Re-read task packet and stop conditions.",
                "2. Make the smallest complete change.",
                "3. Run the stated verification.",
                "4. Write a worker run report.",
                "5. Stop before reviewer/PR/merge.",
                "",
                "Verification command:",
                packet.verification_method,
                "",
                "Stop conditions:",
                "\n".join(f"- {item}" for item in packet.escalation_rules),
                "",
            ]
        ),
        encoding="utf-8",
    )
    return plan_path


def run_worker(repo: str, repo_root: Path, worktrees_root: Path | None = None) -> WorkerResult:
    issues = fetch_issues(repo)
    issue = select_oldest_eligible_issue(issues)
    if issue is None:
        raise RuntimeError("No eligible issue found. Worker requires risk:low + agent:ready and type:docs/type:test.")
    packet = build_task_packet(issue)
    _ensure_clean(repo_root)

    branch = f"agent/issue-{issue.number}-{_slug(issue.title)}"
    worktrees_root = worktrees_root or repo_root.parent / "agent-looop-worktrees"
    worktrees_root.mkdir(parents=True, exist_ok=True)
    worktree_path = worktrees_root / f"issue-{issue.number}"
    if worktree_path.exists():
        shutil.rmtree(worktree_path)

    _run(["git", "worktree", "add", "-b", branch, str(worktree_path), "main"], cwd=repo_root)
    plan_path = write_worker_plan(worktree_path, packet)
    _implement_packet(worktree_path, packet)
    verification_command, verification_passed, verification_output = _verify(worktree_path, packet)
    changed_files = _changed_files(worktree_path)
    report_path = _write_worker_report(
        worktree_path,
        issue,
        packet,
        branch,
        plan_path,
        changed_files,
        verification_command,
        verification_passed,
        verification_output,
    )
    return WorkerResult(
        issue_number=issue.number,
        branch=branch,
        worktree_path=worktree_path,
        plan_path=plan_path,
        report_path=report_path,
        changed_files=changed_files,
        verification_command=verification_command,
        verification_passed=verification_passed,
        verification_output=verification_output,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the v1 worker prototype on one eligible docs/test issue.")
    parser.add_argument("--repo", required=True, help="GitHub repository in OWNER/REPO form")
    parser.add_argument("--repo-root", default=".", help="Local repository root")
    parser.add_argument("--worktrees-root", help="Directory where worker worktrees are created")
    args = parser.parse_args(argv)

    result = run_worker(
        repo=args.repo,
        repo_root=Path(args.repo_root).resolve(),
        worktrees_root=Path(args.worktrees_root).resolve() if args.worktrees_root else None,
    )
    print(f"Selected issue: #{result.issue_number}")
    print(f"Branch: {result.branch}")
    print(f"Worktree: {result.worktree_path}")
    print(f"Plan: {result.plan_path}")
    print(f"Report: {result.report_path}")
    print(f"Changed files: {', '.join(result.changed_files)}")
    print(f"Verification: {'passed' if result.verification_passed else 'failed'}")
    return 0 if result.verification_passed else 1


def _implement_packet(root: Path, packet: TaskPacket) -> None:
    if packet.task_id == "issue-1" or "README link" in packet.goal:
        target = root / "docs" / "getting-started.md"
        if not target.exists():
            raise RuntimeError("Stop condition hit: docs/getting-started.md does not exist")
        readme = root / "README.md"
        text = readme.read_text(encoding="utf-8")
        if "docs/quickstart.md" not in text:
            raise RuntimeError("Expected broken README link not found; stopping instead of guessing")
        readme.write_text(text.replace("docs/quickstart.md", "docs/getting-started.md"), encoding="utf-8")
        return

    if packet.task_id == "issue-4" or "parser error on empty input" in packet.goal:
        test_file = root / "tests" / "test_parser.py"
        text = test_file.read_text(encoding="utf-8")
        snippet = '''\n\ndef test_parse_input_raises_value_error_on_empty_input():\n    import pytest\n\n    with pytest.raises(ValueError):\n        parse_input("")\n'''
        if "test_parse_input_raises_value_error_on_empty_input" not in text:
            test_file.write_text(text.rstrip() + snippet + "\n", encoding="utf-8")
        return

    raise RuntimeError(f"No deterministic worker implementation exists for {packet.task_id}")


def _verify(root: Path, packet: TaskPacket) -> tuple[str, bool, str]:
    if "docs" in packet.allowed_actions[0].lower():
        command = "test -f docs/getting-started.md && grep -q 'docs/getting-started.md' README.md && python -m pytest"
    else:
        command = "python -m pytest"
    completed = subprocess.run(command, cwd=root, shell=True, text=True, capture_output=True)
    output = (completed.stdout + completed.stderr).strip()
    return command, completed.returncode == 0, output


def _write_worker_report(
    root: Path,
    issue: Issue,
    packet: TaskPacket,
    branch: str,
    plan_path: Path,
    changed_files: list[str],
    verification_command: str,
    verification_passed: bool,
    verification_output: str,
) -> Path:
    reports_dir = root / "reports" / "worker-runs"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"{packet.task_id}-worker-run.md"
    report_path.write_text(
        "\n".join(
            [
                f"# Worker Run Report — {packet.task_id}",
                "",
                "## Summary",
                f"- Run time: {datetime.now(timezone.utc).isoformat()}",
                f"- Issue: #{issue.number} {issue.title}",
                f"- Issue URL: {issue.url}",
                f"- Branch: `{branch}`",
                "- Worker mode: prototype docs/test only",
                "- PR opened: no — reviewer/draft PR gate has not been implemented yet",
                "- Merge performed: no",
                "",
                "## Plan",
                f"- Plan path: `{plan_path.relative_to(root)}`",
                "",
                "## Changed files",
                *(f"- `{path}`" for path in changed_files),
                "",
                "## Verification",
                f"- Command: `{verification_command}`",
                f"- Result: {'pass' if verification_passed else 'fail'}",
                "",
                "```text",
                verification_output,
                "```",
                "",
                "## Next gate",
                "Run a separate reviewer/checker pass before opening a draft PR.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return report_path


def _changed_files(root: Path) -> list[str]:
    completed = _run(["git", "status", "--short"], cwd=root)
    files: list[str] = []
    for line in completed.stdout.splitlines():
        if not line.strip():
            continue
        files.append(line[3:].strip())
    return files


def _expected_files(packet: TaskPacket) -> list[str]:
    if "documentation" in " ".join(packet.allowed_actions).lower():
        return ["README.md"]
    if "test" in " ".join(packet.allowed_actions).lower():
        return ["tests/test_parser.py"]
    return ["Unknown until task packet is narrowed"]


def _ensure_clean(repo_root: Path) -> None:
    status = _run(["git", "status", "--short"], cwd=repo_root).stdout.strip()
    if status:
        raise RuntimeError(f"Repository must be clean before worker run. Dirty state:\n{status}")


def _slug(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:50]


def _run(args: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=True)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
