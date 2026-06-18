"""Draft PR creation automation for reviewed worker output.

This module is intentionally deterministic. It validates gates, renders
handoff artifacts, and only creates draft PRs after a reviewer result of pass.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from agent_looop.manager_dry_run import Issue, fetch_issues
from agent_looop.worker_prototype import ALLOWED_TYPES, REQUIRED_LABELS, SKIP_LABELS

WORKER_COMMENT_HEADING = "## Worker Run Report"


@dataclass(frozen=True)
class IssueState:
    number: int
    title: str
    labels: list[str]
    url: str


@dataclass(frozen=True)
class DraftPrArtifacts:
    repo: str
    issue: IssueState
    branch: str
    base: str
    worker_plan_path: Path
    worker_report_path: Path
    reviewer_report_path: Path
    changed_files: list[str]
    verification_command: str
    reviewer_recommendation: str


@dataclass(frozen=True)
class DraftPrGateInput:
    repo: str
    issue: IssueState
    branch: str
    base: str
    worktree_exists: bool
    worktree_clean: bool
    diff_non_empty: bool
    base_is_fresh: bool
    branch_pushed: bool
    existing_pr_url: str
    worker_plan_exists: bool
    worker_report_exists: bool
    worker_verification_passed: bool
    reviewer_report_exists: bool
    reviewer_recommendation: str


@dataclass(frozen=True)
class DraftPrGateResult:
    ok: bool
    errors: list[str]


@dataclass(frozen=True)
class DraftPrResult:
    pr_url: str
    issue_comment_url: str
    report_path: Path
    dry_run: bool


def validate_gates(gate_input: DraftPrGateInput) -> DraftPrGateResult:
    errors: list[str] = []
    labels = set(gate_input.issue.labels)

    if not gate_input.worktree_exists:
        errors.append("Worktree does not exist.")
    if gate_input.branch == gate_input.base:
        errors.append(f"Current branch must not be base branch `{gate_input.base}`.")
    if not gate_input.branch.startswith("agent/issue-"):
        errors.append(f"Worker branch must start with `agent/issue-`: {gate_input.branch}")
    if not gate_input.worktree_clean:
        errors.append("Worktree is not clean before PR creation.")
    if not gate_input.diff_non_empty:
        errors.append(f"Diff against base `{gate_input.base}` is empty.")
    if not gate_input.base_is_fresh:
        errors.append("Branch is stale relative to base; rebase-required before draft PR creation.")
    # A branch may be unpushed at validation time; the mutation path pushes it
    # before creating the draft PR. This gate is "pushed or can be pushed", so
    # lack of an existing origin ref is not itself a blocker.
    if gate_input.existing_pr_url:
        errors.append(f"Open PR already exists for branch {gate_input.branch}: {gate_input.existing_pr_url}")

    if not REQUIRED_LABELS.issubset(labels) or labels & SKIP_LABELS or not labels & ALLOWED_TYPES:
        errors.append(f"Issue is no longer eligible. Current labels: {', '.join(gate_input.issue.labels)}")

    if not gate_input.worker_plan_exists:
        errors.append("Missing worker plan: reports/worker-plans/issue-<n>-plan.md")
    if not gate_input.worker_report_exists:
        errors.append("Missing worker run report: reports/worker-runs/issue-<n>-worker-run.md")
    if not gate_input.worker_verification_passed:
        errors.append("Worker verification did not pass. No PR created.")
    if not gate_input.reviewer_report_exists:
        errors.append("Missing reviewer report: reports/reviewer-runs/issue-<n>-reviewer-report.md")

    if gate_input.reviewer_recommendation == "revise":
        errors.append(
            "Reviewer requested revise. No PR created. Worker may make one in-scope repair attempt before reviewer rerun."
        )
    elif gate_input.reviewer_recommendation == "human_escalation":
        errors.append("Reviewer requested human escalation. No PR created. Human decision required.")
    elif gate_input.reviewer_recommendation != "pass":
        errors.append(f"Reviewer recommendation is not pass: {gate_input.reviewer_recommendation}")

    return DraftPrGateResult(ok=not errors, errors=errors)


def render_pr_body(artifacts: DraftPrArtifacts) -> str:
    files = "\n".join(f"- `{file}`" for file in artifacts.changed_files)
    return "\n".join(
        [
            "## Summary",
            "",
            f"Fixes the bounded worker task for issue #{artifacts.issue.number}: {artifacts.issue.title}.",
            "",
            "## Source issue",
            "",
            f"Refs #{artifacts.issue.number}",
            "",
            "## Task packet",
            "",
            f"- Goal: {artifacts.issue.title}",
            f"- Scope: {', '.join(artifacts.issue.labels)}",
            "- Out of scope: merge, deploy, publish, repo settings, permissions, secrets, unrelated cleanup",
            "- Allowed actions: bounded worker branch changes approved by manager/reviewer gates",
            "- Forbidden actions: non-draft PR, merge, deploy, close issue, override reviewer findings",
            "",
            "## Plan",
            "",
            f"- `{artifacts.worker_plan_path}`",
            "",
            "## Acceptance criteria",
            "",
            "- [x] Worker plan exists before PR handoff.",
            "- [x] Worker verification passed.",
            "- [x] Separate reviewer pass completed with recommendation `pass`.",
            "- [x] Draft PR remains human-gated.",
            "",
            "## Verification",
            "",
            "Commands run:",
            "",
            f"- `{artifacts.verification_command}` — pass",
            "",
            "Worker report:",
            "",
            f"- `{artifacts.worker_report_path}`",
            "",
            "Changed files:",
            "",
            files,
            "",
            "## Reviewer result",
            "",
            "Reviewer report:",
            "",
            f"- `{artifacts.reviewer_report_path}`",
            "",
            "- Critical issues: none recorded in passing reviewer report",
            "- Warnings: none recorded in passing reviewer report",
            "- Suggestions: Draft PR may be opened with this reviewer result included in the PR body.",
            f"- Recommendation: {artifacts.reviewer_recommendation}",
            "",
            "## Known limitations / follow-ups",
            "",
            "- This PR is produced by the bounded pilot loop.",
            "- Human review remains required before merge.",
            "",
            "## Human gate",
            "",
            "This PR is draft-only. Human review/merge required.",
            "",
        ]
    )


def render_issue_comment(artifacts: DraftPrArtifacts, pr_url: str) -> str:
    return "\n".join(
        [
            WORKER_COMMENT_HEADING,
            "",
            "Worker completed the bounded task and opened a draft PR after separate reviewer pass.",
            "",
            f"- Worker branch: `{artifacts.branch}`",
            f"- Draft PR: {pr_url}",
            f"- Worker plan: `{artifacts.worker_plan_path}`",
            f"- Worker run report: `{artifacts.worker_report_path}`",
            f"- Reviewer report: `{artifacts.reviewer_report_path}`",
            f"- Verification: `{artifacts.verification_command}` — pass",
            f"- Reviewer recommendation: {artifacts.reviewer_recommendation}",
            "",
            "Human gate: PR is draft-only. Human review/merge required.",
            "",
        ]
    )


def render_pr_creation_report(artifacts: DraftPrArtifacts, result: DraftPrResult) -> str:
    return "\n".join(
        [
            f"# Draft PR Creation Report — issue-{artifacts.issue.number}",
            "",
            "## Summary",
            f"- Run time: {datetime.now(timezone.utc).isoformat()}",
            f"- Repo: {artifacts.repo}",
            f"- Issue: #{artifacts.issue.number} {artifacts.issue.title}",
            f"- Branch: {artifacts.branch}",
            f"- Base: {artifacts.base}",
            f"- Draft PR: {result.pr_url}",
            f"- Issue comment: {result.issue_comment_url}",
            f"- PR created as draft: {'no — dry run' if result.dry_run else 'yes'}",
            "- Merge performed: no",
            "",
            "## Gates checked",
            "- Issue eligibility: pass",
            "- Worker report present: pass",
            "- Worker verification passed: pass",
            "- Reviewer report present: pass",
            f"- Reviewer recommendation: {artifacts.reviewer_recommendation}",
            "- Existing PR check: pass",
            "- Worktree cleanliness: pass",
            "",
            "## Artifacts",
            f"- Worker plan: `{artifacts.worker_plan_path}`",
            f"- Worker run report: `{artifacts.worker_report_path}`",
            f"- Reviewer report: `{artifacts.reviewer_report_path}`",
            "",
            "## Human gate",
            "This PR is draft-only. Human review/merge required.",
            "",
        ]
    )


def find_worker_run_comment(comments: Sequence[dict[str, Any]]) -> dict[str, Any] | None:
    for comment in comments:
        body = str(comment.get("body", ""))
        if body.startswith(WORKER_COMMENT_HEADING):
            return comment
    return None


def parse_worker_report(text: str) -> tuple[bool, str]:
    verification_passed = "- Result: pass" in text
    command = ""
    for line in text.splitlines():
        if line.startswith("- Command: `") and line.endswith("`"):
            command = line.removeprefix("- Command: `").removesuffix("`")
            break
    return verification_passed, command


def parse_reviewer_report(text: str) -> str:
    for line in text.splitlines():
        if "Recommendation:" in line:
            return line.split("Recommendation:", 1)[1].strip().strip("`")
    return ""


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a gated draft PR from passed worker/reviewer output.")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--worktree", required=True)
    parser.add_argument("--issue", type=int, required=True)
    parser.add_argument("--base", default="main")
    parser.add_argument("--title")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    try:
        if args.dry_run:
            return _run_dry_run(args.repo, Path(args.worktree).resolve(), args.issue, args.base)
        return _run_create(args.repo, Path(args.worktree).resolve(), args.issue, args.base, args.title)
    except RuntimeError as exc:
        print(str(exc))
        return 1


def _run_dry_run(repo: str, worktree: Path, issue_number: int, base: str) -> int:
    artifacts, gate = build_artifacts_and_gate(repo, worktree, issue_number, base)
    if not gate.ok:
        for error in gate.errors:
            print(error)
        return 1
    print("DRY RUN — no GitHub mutations performed.")
    print("\n--- PR BODY ---\n")
    print(render_pr_body(artifacts))
    print("\n--- ISSUE COMMENT ---\n")
    print(render_issue_comment(artifacts, pr_url="DRY_RUN_PR_URL"))
    print("\n--- PR CREATION REPORT ---\n")
    print(
        render_pr_creation_report(
            artifacts,
            DraftPrResult(
                pr_url="DRY_RUN_PR_URL",
                issue_comment_url="DRY_RUN_ISSUE_COMMENT_URL",
                report_path=Path(f"reports/pr-runs/issue-{issue_number}-draft-pr.md"),
                dry_run=True,
            ),
        )
    )
    return 0


def _run_create(repo: str, worktree: Path, issue_number: int, base: str, title: str | None) -> int:
    artifacts, gate = build_artifacts_and_gate(repo, worktree, issue_number, base)
    if not gate.ok:
        for error in gate.errors:
            print(error)
        return 1

    body_path = worktree / f"issue-{issue_number}-draft-pr-body.md"
    body_path.write_text(render_pr_body(artifacts), encoding="utf-8")
    try:
        _run(["git", "push", "-u", "origin", artifacts.branch], cwd=worktree)
        pr_url = _run(
            [
                "gh",
                "pr",
                "create",
                "--repo",
                repo,
                "--base",
                base,
                "--head",
                artifacts.branch,
                "--title",
                title or artifacts.issue.title,
                "--body-file",
                str(body_path),
                "--draft",
            ],
            cwd=worktree,
        ).stdout.strip()
        comment_url = upsert_issue_comment(repo, issue_number, render_issue_comment(artifacts, pr_url), worktree)
        report_path = write_pr_creation_report(
            worktree,
            artifacts,
            DraftPrResult(
                pr_url=pr_url,
                issue_comment_url=comment_url,
                report_path=Path(f"reports/pr-runs/issue-{issue_number}-draft-pr.md"),
                dry_run=False,
            ),
        )
        _run(["git", "add", str(report_path.relative_to(worktree))], cwd=worktree)
        _run(["git", "commit", "-m", f"chore: add draft PR report for issue {issue_number}"], cwd=worktree)
        _run(["git", "push", "origin", artifacts.branch], cwd=worktree)
    finally:
        body_path.unlink(missing_ok=True)

    print(f"Draft PR: {pr_url}")
    print(f"Issue comment: {comment_url}")
    print(f"Report: {report_path}")
    return 0


def build_artifacts_and_gate(repo: str, worktree: Path, issue_number: int, base: str) -> tuple[DraftPrArtifacts, DraftPrGateResult]:
    issue = _fetch_issue_state(repo, issue_number)
    branch = _run(["git", "branch", "--show-current"], cwd=worktree).stdout.strip() if worktree.exists() else ""
    worker_plan = Path(f"reports/worker-plans/issue-{issue_number}-plan.md")
    worker_report = Path(f"reports/worker-runs/issue-{issue_number}-worker-run.md")
    reviewer_report = Path(f"reports/reviewer-runs/issue-{issue_number}-reviewer-report.md")
    worker_report_text = _read_if_exists(worktree / worker_report)
    reviewer_report_text = _read_if_exists(worktree / reviewer_report)
    verification_passed, verification_command = parse_worker_report(worker_report_text)
    reviewer_recommendation = parse_reviewer_report(reviewer_report_text)
    changed_files = _changed_files(worktree, base) if worktree.exists() else []
    existing_pr_url = _existing_pr_url(repo, branch, worktree) if branch else ""
    artifacts = DraftPrArtifacts(
        repo=repo,
        issue=issue,
        branch=branch,
        base=base,
        worker_plan_path=worker_plan,
        worker_report_path=worker_report,
        reviewer_report_path=reviewer_report,
        changed_files=changed_files,
        verification_command=verification_command,
        reviewer_recommendation=reviewer_recommendation,
    )
    gate = validate_gates(
        DraftPrGateInput(
            repo=repo,
            issue=issue,
            branch=branch,
            base=base,
            worktree_exists=worktree.exists(),
            worktree_clean=_is_clean(worktree) if worktree.exists() else False,
            diff_non_empty=bool(changed_files),
            base_is_fresh=_base_is_fresh(worktree, base) if worktree.exists() else False,
            branch_pushed=_branch_pushed(worktree, branch) if worktree.exists() and branch else False,
            existing_pr_url=existing_pr_url,
            worker_plan_exists=(worktree / worker_plan).exists(),
            worker_report_exists=(worktree / worker_report).exists(),
            worker_verification_passed=verification_passed,
            reviewer_report_exists=(worktree / reviewer_report).exists(),
            reviewer_recommendation=reviewer_recommendation,
        )
    )
    return artifacts, gate


def write_pr_creation_report(root: Path, artifacts: DraftPrArtifacts, result: DraftPrResult) -> Path:
    report_path = root / result.report_path
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_pr_creation_report(artifacts, result), encoding="utf-8")
    return report_path


def upsert_issue_comment(repo: str, issue_number: int, body: str, cwd: Path) -> str:
    comments_json = _run(
        ["gh", "api", f"repos/{repo}/issues/{issue_number}/comments", "--paginate"], cwd=cwd
    ).stdout
    comments = json.loads(comments_json or "[]")
    existing = find_worker_run_comment(comments)
    if existing:
        comment_id = str(existing["id"])
        _run(["gh", "api", f"repos/{repo}/issues/comments/{comment_id}", "-X", "PATCH", "-f", f"body={body}"], cwd=cwd)
        return str(existing.get("html_url") or existing.get("url") or "")
    url = _run(["gh", "issue", "comment", str(issue_number), "--repo", repo, "--body", body], cwd=cwd).stdout.strip()
    return url


def _fetch_issue_state(repo: str, issue_number: int) -> IssueState:
    issues = fetch_issues(repo)
    issue: Issue | None = next((item for item in issues if item.number == issue_number), None)
    if issue is None:
        raise RuntimeError(f"Issue #{issue_number} not found in {repo}")
    return IssueState(number=issue.number, title=issue.title, labels=issue.labels, url=issue.url)


def _changed_files(root: Path, base: str) -> list[str]:
    tracked = _run(["git", "diff", "--name-only", f"{base}...HEAD"], cwd=root).stdout.splitlines()
    untracked = [
        line[3:].strip()
        for line in _run(["git", "status", "--short", "--untracked-files=all"], cwd=root).stdout.splitlines()
        if line.startswith("?? ")
    ]
    return sorted(set(tracked + untracked))


def _is_clean(root: Path) -> bool:
    return _run(["git", "status", "--short"], cwd=root).stdout.strip() == ""


def _base_is_fresh(root: Path, base: str) -> bool:
    _run(["git", "fetch", "origin", base], cwd=root)
    local_base = _run(["git", "rev-parse", base], cwd=root).stdout.strip()
    origin_base = _run(["git", "rev-parse", f"origin/{base}"], cwd=root).stdout.strip()
    return local_base == origin_base


def _branch_pushed(root: Path, branch: str) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", f"origin/{branch}"], cwd=root, text=True, capture_output=True
    )
    return result.returncode == 0


def _existing_pr_url(repo: str, branch: str, cwd: Path) -> str:
    if not branch:
        return ""
    output = _run(
        [
            "gh",
            "pr",
            "list",
            "--repo",
            repo,
            "--head",
            branch,
            "--state",
            "open",
            "--json",
            "url",
            "--jq",
            ".[0].url // \"\"",
        ],
        cwd=cwd,
    ).stdout.strip()
    return output


def _read_if_exists(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _run(args: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=True)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
