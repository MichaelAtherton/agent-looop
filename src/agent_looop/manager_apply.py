"""Manager apply mode for approved dry-run classifications.

Apply mode mutates only GitHub issue metadata/comments:
- adds approved labels from the dry-run classification;
- creates or updates one Agent Assessment comment per issue;
- writes a local apply report.

It does not write code, create branches, open PRs, close issues, merge, deploy,
or alter repository settings/secrets.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence, cast

from agent_looop.manager_dry_run import (
    Classification,
    Issue,
    classify_issue,
    fetch_issues,
)

COMMENT_MARKER = "## Agent Assessment"


@dataclass(frozen=True)
class ApplyAction:
    issue_number: int
    issue_title: str
    labels_to_add: list[str]
    comment_body: str


@dataclass(frozen=True)
class AppliedAction:
    issue_number: int
    issue_title: str
    labels_added: list[str]
    comment_action: str
    comment_url: str


def build_apply_actions(
    issues: Sequence[Issue], classifications: Sequence[Classification]
) -> list[ApplyAction]:
    """Build safe apply actions from dry-run classifications.

    This is the deterministic permission boundary for manager apply mode. It
    refuses to build actions if any medium/high-risk issue would be granted
    `agent:ready`.
    """
    issues_by_number = {issue.number: issue for issue in issues}
    actions: list[ApplyAction] = []

    for classification in classifications:
        if classification.agent_ready and classification.risk != "risk:low":
            raise ValueError(
                f"false-ready classification rejected for issue #{classification.issue_number}: "
                f"{classification.risk} cannot receive agent:ready"
            )
        if "agent:ready" in classification.apply_mode_labels and classification.risk != "risk:low":
            raise ValueError(
                f"false-ready labels rejected for issue #{classification.issue_number}: "
                f"{classification.apply_mode_labels}"
            )

        issue = issues_by_number[classification.issue_number]
        existing = set(issue.labels)
        labels_to_add = [
            label for label in classification.apply_mode_labels if label not in existing
        ]
        actions.append(
            ApplyAction(
                issue_number=classification.issue_number,
                issue_title=classification.issue_title,
                labels_to_add=labels_to_add,
                comment_body=render_agent_assessment_comment(classification),
            )
        )
    return actions


def render_agent_assessment_comment(classification: Classification) -> str:
    """Render the issue comment that apply mode creates/updates."""
    lines = [
        COMMENT_MARKER,
        "",
        f"Risk: {classification.risk.replace('risk:', '')}",
        f"Type: {classification.issue_type.replace('type:', '')}",
        f"Agent-ready: {'yes' if classification.agent_ready else 'no'}",
        f"Confidence: {classification.confidence:.2f}",
        "",
        "Reason:",
        classification.reason,
        "",
        "Required verification:",
        classification.required_verification,
        "",
        "Allowed worker action:",
        _allowed_worker_action(classification),
        "",
        "Forbidden:",
        "- No merge, deploy, publish, repo settings, permissions, secrets, or unrelated cleanup.",
        "- No work outside the issue and Agent Assessment scope.",
    ]
    if classification.human_question:
        lines.extend(["", "Human question:", classification.human_question])
    lines.extend(
        [
            "",
            "Apply-mode note:",
            "This comment was generated from an approved manager dry-run. Labels are permissions; `agent:ready` means the issue may be selected only if all deterministic eligibility rules still pass at worker runtime.",
        ]
    )
    return "\n".join(lines) + "\n"


def apply_actions(repo: str, actions: Sequence[ApplyAction]) -> list[AppliedAction]:
    """Apply labels and Agent Assessment comments to GitHub."""
    applied: list[AppliedAction] = []
    for action in actions:
        if action.labels_to_add:
            _run_gh(
                [
                    "issue",
                    "edit",
                    str(action.issue_number),
                    "--repo",
                    repo,
                    "--add-label",
                    ",".join(action.labels_to_add),
                ]
            )
        comment_action, comment_url = upsert_agent_assessment_comment(
            repo, action.issue_number, action.comment_body
        )
        applied.append(
            AppliedAction(
                issue_number=action.issue_number,
                issue_title=action.issue_title,
                labels_added=action.labels_to_add,
                comment_action=comment_action,
                comment_url=comment_url,
            )
        )
    return applied


def upsert_agent_assessment_comment(repo: str, issue_number: int, body: str) -> tuple[str, str]:
    """Create or update the Agent Assessment comment for an issue."""
    owner_repo = repo.strip()
    comments = cast(
        list[dict[str, Any]],
        _gh_json(["api", f"repos/{owner_repo}/issues/{issue_number}/comments"]),
    )
    existing = next(
        (comment for comment in comments if (comment.get("body") or "").startswith(COMMENT_MARKER)),
        None,
    )
    if existing:
        updated = cast(
            dict[str, Any],
            _gh_json(
                [
                    "api",
                    "--method",
                    "PATCH",
                    f"repos/{owner_repo}/issues/comments/{existing['id']}",
                    "-f",
                    f"body={body}",
                ]
            ),
        )
        return "updated", str(updated.get("html_url", ""))

    with tempfile.NamedTemporaryFile("w", delete=False) as tmp:
        tmp.write(body)
        tmp_path = tmp.name
    try:
        completed = _run_gh(
            [
                "issue",
                "comment",
                str(issue_number),
                "--repo",
                owner_repo,
                "--body-file",
                tmp_path,
            ]
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    return "created", completed.stdout.strip()


def render_apply_report(repo: str, applied: Sequence[AppliedAction], run_time: str | None = None) -> str:
    run_time = run_time or datetime.now(timezone.utc).isoformat()
    lines = [
        "# Manager Apply Report",
        "",
        "## Summary",
        f"- Repo: `{repo}`",
        f"- Run time: {run_time}",
        f"- Issues updated: {len(applied)}",
        "- Scope: labels and Agent Assessment comments only",
        "- Forbidden actions performed: none — no code, branches, PRs, merges, deployments, repo settings, permissions, or secrets were changed",
        "",
        "## Applied actions",
        "| Issue | Labels added | Comment action | Comment URL |",
        "|---|---|---|---|",
    ]
    for item in applied:
        labels = ", ".join(item.labels_added) if item.labels_added else "none"
        lines.append(
            f"| #{item.issue_number} {item.issue_title} | {labels} | {item.comment_action} | {item.comment_url} |"
        )
    lines.extend(
        [
            "",
            "## Next gate",
            "Michael/Calvin should inspect the issue labels/comments before enabling worker mode.",
        ]
    )
    return "\n".join(lines) + "\n"


def run_apply(repo: str, output: Path | None = None) -> str:
    issues = fetch_issues(repo)
    classifications = [classify_issue(issue) for issue in issues]
    actions = build_apply_actions(issues, classifications)
    applied = apply_actions(repo, actions)
    report = render_apply_report(repo, applied)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report, encoding="utf-8")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply approved manager dry-run labels/comments to GitHub Issues.")
    parser.add_argument("--repo", required=True, help="GitHub repository in OWNER/REPO form")
    parser.add_argument("--output", help="Optional markdown apply report output path")
    args = parser.parse_args(argv)

    output = Path(args.output) if args.output else None
    report = run_apply(args.repo, output)
    if output is None:
        print(report, end="")
    else:
        print(f"Wrote apply report to {output}")
    return 0


def _allowed_worker_action(classification: Classification) -> str:
    if not classification.agent_ready:
        return "- None. Worker must not select this issue until human input resolves the blocker."
    if classification.issue_type == "type:docs":
        return "- Documentation-only edit within the issue scope."
    if classification.issue_type == "type:test":
        return "- Test-only edit within the issue scope; production behavior changes only if required to satisfy documented behavior."
    return "- Bounded edit within the issue scope."


def _run_gh(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["gh", *args], text=True, capture_output=True, check=True)


def _gh_json(args: Sequence[str]) -> Any:
    completed = _run_gh(args)
    return json.loads(completed.stdout)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
