"""Manager dry-run logic for the GitHub Issues → draft PR loop.

This module intentionally performs read-only classification. It can fetch issues
and labels from GitHub, but it never applies labels, posts comments, creates
branches, opens PRs, or edits code.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence, cast


@dataclass(frozen=True)
class Issue:
    number: int
    title: str
    body: str
    labels: list[str]
    url: str


@dataclass(frozen=True)
class Classification:
    issue_number: int
    issue_title: str
    risk: str
    issue_type: str
    agent_ready: bool
    confidence: float
    reason: str
    required_verification: str
    human_question: str
    apply_mode_labels: list[str]


MANAGED_LABELS = [
    "risk:low",
    "risk:medium",
    "risk:high",
    "type:bug",
    "type:feature",
    "type:docs",
    "type:test",
    "type:refactor",
    "type:chore",
    "agent:ready",
    "agent:blocked",
    "agent:complete",
    "agent:in-progress",
    "needs:human",
]

BLOCKED_SCOPE_PATTERNS = {
    "auth": "auth",
    "authentication": "auth",
    "billing": "billing",
    "payment": "payment",
    "permissions": "permissions",
    "permission": "permissions",
    "security": "security",
    "secret": "secrets",
    "migration": "migration",
    "deploy": "deployment",
    "production": "production deployment",
    "architecture": "architecture",
    "air scoring": "AI Navigator AIR scoring",
    "air assessment": "AIR assessment behavior",
    "air coaching": "AIR coaching behavior",
    "privacy": "privacy controls",
    "employer visibility": "employer visibility",
    "role-data": "role-data surfaces",
    "role data": "role-data surfaces",
}


def expected_managed_labels() -> list[str]:
    """Return the managed label taxonomy expected by v1."""
    return list(MANAGED_LABELS)


def classify_issue(issue: Issue) -> Classification:
    """Classify an issue for dry-run reporting.

    The smoke-test classifier is intentionally conservative. Hard-blocked
    scopes and missing acceptance criteria override otherwise useful work.
    """
    text = f"{issue.title}\n\n{issue.body}".lower()
    title = issue.title.lower()

    blocked_scopes = _blocked_scopes(text)
    vague = _has_missing_acceptance_criteria(text) or _is_vague_request(title, text)
    issue_type = _classify_type(title, text)

    if "auth" in blocked_scopes:
        return _blocked(
            issue,
            risk="risk:high",
            issue_type=issue_type,
            confidence=0.98,
            reason="Authentication architecture is a blocked v1 scope and the requested change requires human technical/product judgment.",
            human_question="What specific auth behavior, constraint, or failure mode should be addressed first?",
            required_verification="Human-defined architecture decision and verification plan required before any agent work.",
        )

    if {"payment", "billing", "permissions"} & blocked_scopes:
        return _blocked(
            issue,
            risk="risk:high",
            issue_type=issue_type,
            confidence=0.98,
            reason="Payment/billing/permission logic is a blocked v1 scope and may affect security-sensitive behavior.",
            human_question="What exact payment permission behavior should change, and what tests define correctness?",
            required_verification="Human-defined payment/permissions test plan required before any agent work.",
        )

    if blocked_scopes:
        scopes = ", ".join(sorted(blocked_scopes))
        return _blocked(
            issue,
            risk="risk:high",
            issue_type=issue_type,
            confidence=0.94,
            reason=f"Issue touches blocked v1 scope(s): {scopes}.",
            human_question="What specific low-risk, non-sensitive change should be separated from this request?",
            required_verification="Human-defined verification required after narrowing scope.",
        )

    if "onboarding" in text and vague:
        return _blocked(
            issue,
            risk="risk:medium",
            issue_type=issue_type,
            confidence=0.88,
            reason="The onboarding request is too broad; it does not identify a specific document, behavior, or acceptance criteria.",
            human_question="What specific onboarding behavior or document should be changed?",
            required_verification="Human must define the target artifact and expected outcome.",
        )

    if vague:
        return _blocked(
            issue,
            risk="risk:medium",
            issue_type=issue_type,
            confidence=0.84,
            reason="The issue lacks specific acceptance criteria or verification instructions.",
            human_question="What specific behavior, file, or outcome should change?",
            required_verification="Human must define acceptance criteria and verification method.",
        )

    if issue_type == "type:docs":
        return Classification(
            issue_number=issue.number,
            issue_title=issue.title,
            risk="risk:low",
            issue_type=issue_type,
            agent_ready=True,
            confidence=0.95,
            reason="Documentation-only work with clear scope and acceptance criteria.",
            required_verification="Inspect documentation diff and confirm referenced file/link target exists.",
            human_question="",
            apply_mode_labels=["risk:low", issue_type, "agent:ready"],
        )

    if issue_type == "type:test":
        return Classification(
            issue_number=issue.number,
            issue_title=issue.title,
            risk="risk:low",
            issue_type=issue_type,
            agent_ready=True,
            confidence=0.94,
            reason="Test-only task with explicit expected behavior and verification command.",
            required_verification="Run `python -m pytest` and record pass/fail output.",
            human_question="",
            apply_mode_labels=["risk:low", issue_type, "agent:ready"],
        )

    return _blocked(
        issue,
        risk="risk:medium",
        issue_type=issue_type,
        confidence=0.75,
        reason="The issue is not in the first-worker docs/test allowlist for v1.",
        human_question="Should this be narrowed to a docs/test-only task or held for a later expansion stage?",
        required_verification="Human approval required before expanding worker scope.",
    )


def render_dry_run_report(
    *,
    repo: str,
    issues: Sequence[Issue],
    classifications: Sequence[Classification],
    existing_labels: Sequence[str],
    run_time: str | None = None,
) -> str:
    """Render a manager dry-run report as Markdown."""
    run_time = run_time or datetime.now(timezone.utc).isoformat()
    managed = set(expected_managed_labels())
    existing = set(existing_labels)
    missing_labels = sorted(managed - existing)
    unexpected_managed_prefix_labels = sorted(
        label
        for label in existing
        if label.startswith(("risk:", "type:", "agent:", "needs:")) and label not in managed
    )
    ready_count = sum(1 for c in classifications if c.agent_ready)
    needs_human_count = sum(1 for c in classifications if not c.agent_ready)
    false_ready_risks = [
        c for c in classifications if c.agent_ready and c.risk in {"risk:medium", "risk:high"}
    ]

    lines: list[str] = [
        "# Manager Dry-Run Report",
        "",
        "## Summary",
        f"- Repo: `{repo}`",
        f"- Run time: {run_time}",
        f"- Issues inspected: {len(issues)}",
        f"- Recommended agent-ready count: {ready_count}",
        f"- Recommended needs-human count: {needs_human_count}",
        f"- False-ready risks: {'none detected' if not false_ready_risks else ', '.join(f'#{c.issue_number}' for c in false_ready_risks)}",
        "- Mutation status: No GitHub mutations were performed. This report is read-only.",
        "",
        "## Issue classifications",
        "| Issue | Current labels | Recommended risk | Recommended type | Agent-ready? | Confidence | Reason | Human question | Apply-mode labels |",
        "|---|---|---|---|---|---:|---|---|---|",
    ]

    issue_by_number = {issue.number: issue for issue in issues}
    for c in classifications:
        issue = issue_by_number[c.issue_number]
        lines.append(
            "| "
            + " | ".join(
                [
                    _md(f"#{c.issue_number} {c.issue_title}"),
                    _md(", ".join(issue.labels) if issue.labels else "none"),
                    c.risk,
                    c.issue_type,
                    "yes" if c.agent_ready else "no",
                    f"{c.confidence:.2f}",
                    _md(c.reason),
                    _md(c.human_question or "—"),
                    _md(", ".join(c.apply_mode_labels)),
                ]
            )
            + " |"
        )

    lines.extend(["", "## Missing labels"])
    if missing_labels:
        lines.extend(f"- `{label}`" for label in missing_labels)
    else:
        lines.append("- none")

    lines.extend(["", "## Unexpected managed-prefix labels"])
    if unexpected_managed_prefix_labels:
        lines.extend(f"- `{label}`" for label in unexpected_managed_prefix_labels)
    else:
        lines.append("- none")

    lines.extend(["", "## Apply-mode actions proposed"])
    for c in classifications:
        lines.append(
            f"- Issue #{c.issue_number}: apply labels `{', '.join(c.apply_mode_labels)}` and post/update an Agent Assessment comment."
        )

    lines.extend(["", "## Proposed Agent Assessment comments"])
    for c in classifications:
        lines.extend(
            [
                f"### Issue #{c.issue_number} — {c.issue_title}",
                "",
                "```markdown",
                "## Agent Assessment",
                "",
                f"Risk: {c.risk.replace('risk:', '')}",
                f"Type: {c.issue_type.replace('type:', '')}",
                f"Agent-ready: {'yes' if c.agent_ready else 'no'}",
                f"Confidence: {c.confidence:.2f}",
                "",
                "Reason:",
                c.reason,
                "",
                "Required verification:",
                c.required_verification,
                "",
                "Allowed worker action:",
                _allowed_worker_action(c),
                "",
                "Forbidden:",
                "- No merge, deploy, publish, repo settings, permissions, secrets, or unrelated cleanup.",
                "- No work outside the issue and Agent Assessment scope.",
            ]
        )
        if c.human_question:
            lines.extend(["", "Human question:", c.human_question])
        lines.extend(["```", ""])

    lines.extend(["## Blockers / human questions"])
    blockers = [c for c in classifications if c.human_question]
    if blockers:
        lines.extend(f"- #{c.issue_number}: {c.human_question}" for c in blockers)
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Self-critique",
            "- This dry-run uses deterministic v1 policy heuristics rather than a general engineering judgment model.",
            "- It is intentionally conservative: unclear or non-docs/test work is blocked until a human narrows scope.",
            "- Michael/Calvin should verify that the two recommended `agent:ready` issues are truly safe before apply mode.",
            "- Auth, payment, permissions, security, migration, deployment, broad architecture, and AI Navigator product-critical surfaces remain blocked even if future issues include more detail.",
        ]
    )
    return "\n".join(lines) + "\n"


def fetch_issues(repo: str) -> list[Issue]:
    """Fetch open issues from GitHub using gh CLI."""
    data = cast(
        list[dict[str, Any]],
        _gh_json(
            [
                "issue",
                "list",
                "--repo",
                repo,
                "--state",
                "open",
                "--limit",
                "100",
                "--json",
                "number,title,body,labels,url",
            ]
        ),
    )
    return [
        Issue(
            number=item["number"],
            title=item["title"],
            body=item.get("body") or "",
            labels=[label["name"] for label in item.get("labels", [])],
            url=item["url"],
        )
        for item in sorted(data, key=lambda row: row["number"])
    ]


def fetch_labels(repo: str) -> list[str]:
    """Fetch repository labels from GitHub using gh CLI."""
    data = cast(
        list[dict[str, Any]],
        _gh_json(["label", "list", "--repo", repo, "--limit", "100", "--json", "name"]),
    )
    return sorted(item["name"] for item in data)


def run_dry_run(repo: str, output: Path | None = None) -> str:
    """Fetch GitHub state, classify issues, render, and optionally write report."""
    issues = fetch_issues(repo)
    labels = fetch_labels(repo)
    classifications = [classify_issue(issue) for issue in issues]
    report = render_dry_run_report(
        repo=repo,
        issues=issues,
        classifications=classifications,
        existing_labels=labels,
    )
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report, encoding="utf-8")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a non-mutating manager dry-run over GitHub Issues.")
    parser.add_argument("--repo", required=True, help="GitHub repository in OWNER/REPO form")
    parser.add_argument("--output", help="Optional markdown report output path")
    args = parser.parse_args(argv)

    output = Path(args.output) if args.output else None
    report = run_dry_run(args.repo, output)
    if output is None:
        print(report, end="")
    else:
        print(f"Wrote dry-run report to {output}")
    return 0


def _blocked(
    issue: Issue,
    *,
    risk: str,
    issue_type: str,
    confidence: float,
    reason: str,
    human_question: str,
    required_verification: str,
) -> Classification:
    return Classification(
        issue_number=issue.number,
        issue_title=issue.title,
        risk=risk,
        issue_type=issue_type,
        agent_ready=False,
        confidence=confidence,
        reason=reason,
        required_verification=required_verification,
        human_question=human_question,
        apply_mode_labels=[risk, issue_type, "needs:human", "agent:blocked"],
    )


def _classify_type(title: str, text: str) -> str:
    if any(word in text for word in ["readme", "docs", "documentation", "link"]):
        return "type:docs"
    if any(word in text for word in ["test", "pytest", "regression"]):
        return "type:test"
    if any(word in text for word in ["refactor", "cleanup"]):
        return "type:refactor"
    if any(word in text for word in ["bug", "error", "failure", "broken"]):
        return "type:bug"
    if any(re.search(pattern, text) for pattern in [r"\bchore\b", r"\bmaintenance\b", r"\bci\b"]):
        return "type:chore"
    return "type:feature"


def _blocked_scopes(text: str) -> set[str]:
    policy_text = _remove_negated_scope_disclaimers(text)
    return {scope for pattern, scope in BLOCKED_SCOPE_PATTERNS.items() if pattern in policy_text}


def _remove_negated_scope_disclaimers(text: str) -> str:
    """Ignore fixture disclaimers such as 'No auth, billing ... changes'.

    Safe smoke issues explicitly say they do *not* touch sensitive areas. Those
    disclaimers should not trigger blocked-scope detection.
    """
    policy_text = re.sub(
        r"no\s+(auth|authentication|billing|payment|payments|permissions?|security|migration|deployment|deploy|product behavior)(?:[^.\n]*)(?:changes?)?",
        "",
        text,
        flags=re.IGNORECASE,
    )
    return re.sub(
        r"no\s+production\s+behavior\s+is\s+changed(?:[^.\n]*)",
        "",
        policy_text,
        flags=re.IGNORECASE,
    )


def _has_missing_acceptance_criteria(text: str) -> bool:
    undefined_markers = [
        "to be defined",
        "tbd",
        "as needed",
        "figure out",
        "make onboarding better",
        "improve onboarding",
    ]
    return any(marker in text for marker in undefined_markers)


def _is_vague_request(title: str, text: str) -> bool:
    vague_verbs = ["improve", "redesign", "make better", "more scalable", "as needed"]
    return any(verb in title or verb in text for verb in vague_verbs)


def _allowed_worker_action(classification: Classification) -> str:
    if not classification.agent_ready:
        return "- None. Worker must not select this issue until human input resolves the blocker."
    if classification.issue_type == "type:docs":
        return "- Documentation-only edit within the issue scope."
    if classification.issue_type == "type:test":
        return "- Test-only edit within the issue scope; production behavior changes only if required to satisfy documented behavior."
    return "- Bounded edit within the issue scope."


def _md(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


def _gh_json(args: Sequence[str]) -> Any:
    completed = subprocess.run(
        ["gh", *args],
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(completed.stdout)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
