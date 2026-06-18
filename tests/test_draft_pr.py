from pathlib import Path

from agent_looop.draft_pr import (
    DraftPrArtifacts,
    DraftPrGateInput,
    DraftPrResult,
    IssueState,
    find_worker_run_comment,
    render_issue_comment,
    render_pr_body,
    render_pr_creation_report,
    validate_gates,
)


def _issue(labels: list[str] | None = None) -> IssueState:
    return IssueState(
        number=1,
        title="Fix broken README link",
        labels=labels or ["risk:low", "type:docs", "agent:ready"],
        url="https://github.com/MichaelAtherton/agent-looop/issues/1",
    )


def _artifacts() -> DraftPrArtifacts:
    return DraftPrArtifacts(
        repo="MichaelAtherton/agent-looop",
        issue=_issue(),
        branch="agent/issue-1-fix-broken-readme-link",
        base="main",
        worker_plan_path=Path("reports/worker-plans/issue-1-plan.md"),
        worker_report_path=Path("reports/worker-runs/issue-1-worker-run.md"),
        reviewer_report_path=Path("reports/reviewer-runs/issue-1-reviewer-report.md"),
        changed_files=[
            "README.md",
            "reports/worker-plans/issue-1-plan.md",
            "reports/worker-runs/issue-1-worker-run.md",
            "reports/reviewer-runs/issue-1-reviewer-report.md",
        ],
        verification_command="test -f docs/getting-started.md && grep -q 'docs/getting-started.md' README.md && python -m pytest",
        reviewer_recommendation="pass",
    )


def _gate_input(**overrides) -> DraftPrGateInput:
    data = {
        "repo": "MichaelAtherton/agent-looop",
        "issue": _issue(),
        "branch": "agent/issue-1-fix-broken-readme-link",
        "base": "main",
        "worktree_exists": True,
        "worktree_clean": True,
        "diff_non_empty": True,
        "base_is_fresh": True,
        "branch_pushed": True,
        "existing_pr_url": "",
        "worker_plan_exists": True,
        "worker_report_exists": True,
        "worker_verification_passed": True,
        "reviewer_report_exists": True,
        "reviewer_recommendation": "pass",
    }
    data.update(overrides)
    return DraftPrGateInput(**data)


def test_render_pr_body_includes_required_sections_and_human_gate():
    body = render_pr_body(_artifacts())

    for heading in [
        "## Summary",
        "## Source issue",
        "## Task packet",
        "## Plan",
        "## Acceptance criteria",
        "## Verification",
        "## Reviewer result",
        "## Known limitations / follow-ups",
        "## Human gate",
    ]:
        assert heading in body
    assert "Refs #1" in body
    assert "reports/worker-runs/issue-1-worker-run.md" in body
    assert "reports/reviewer-runs/issue-1-reviewer-report.md" in body
    assert "Recommendation: pass" in body
    assert "This PR is draft-only. Human review/merge required." in body


def test_render_issue_comment_contains_pr_link_artifacts_and_human_gate():
    comment = render_issue_comment(
        _artifacts(),
        pr_url="https://github.com/MichaelAtherton/agent-looop/pull/7",
    )

    assert comment.startswith("## Worker Run Report")
    assert "https://github.com/MichaelAtherton/agent-looop/pull/7" in comment
    assert "agent/issue-1-fix-broken-readme-link" in comment
    assert "reports/worker-plans/issue-1-plan.md" in comment
    assert "reports/worker-runs/issue-1-worker-run.md" in comment
    assert "reports/reviewer-runs/issue-1-reviewer-report.md" in comment
    assert "Reviewer recommendation: pass" in comment
    assert "Human gate: PR is draft-only. Human review/merge required." in comment


def test_render_pr_creation_report_requires_pr_url_and_comment_url():
    report = render_pr_creation_report(
        _artifacts(),
        DraftPrResult(
            pr_url="https://github.com/MichaelAtherton/agent-looop/pull/7",
            issue_comment_url="https://github.com/MichaelAtherton/agent-looop/issues/1#issuecomment-1",
            report_path=Path("reports/pr-runs/issue-1-draft-pr.md"),
            dry_run=False,
        ),
    )

    assert "# Draft PR Creation Report — issue-1" in report
    assert "- Draft PR: https://github.com/MichaelAtherton/agent-looop/pull/7" in report
    assert "- Issue comment: https://github.com/MichaelAtherton/agent-looop/issues/1#issuecomment-1" in report
    assert "- PR created as draft: yes" in report
    assert "- Merge performed: no" in report
    assert "- Reviewer recommendation: pass" in report


def test_validate_gates_allows_passed_eligible_reviewed_worker_run():
    result = validate_gates(_gate_input())

    assert result.ok is True
    assert result.errors == []


def test_validate_gates_allows_unpushed_branch_because_create_path_pushes_it():
    result = validate_gates(_gate_input(branch_pushed=False))

    assert result.ok is True
    assert result.errors == []


def test_validate_gates_blocks_reviewer_revise():
    result = validate_gates(_gate_input(reviewer_recommendation="revise"))

    assert result.ok is False
    assert "Reviewer requested revise. No PR created." in result.errors[0]


def test_validate_gates_blocks_reviewer_human_escalation():
    result = validate_gates(_gate_input(reviewer_recommendation="human_escalation"))

    assert result.ok is False
    assert "Reviewer requested human escalation. No PR created." in result.errors[0]


def test_validate_gates_blocks_missing_reports_and_failed_verification():
    result = validate_gates(
        _gate_input(
            worker_report_exists=False,
            worker_verification_passed=False,
            reviewer_report_exists=False,
        )
    )

    assert result.ok is False
    assert "Missing worker run report" in "\n".join(result.errors)
    assert "Worker verification did not pass" in "\n".join(result.errors)
    assert "Missing reviewer report" in "\n".join(result.errors)


def test_validate_gates_blocks_ineligible_issue_labels():
    issue = _issue(["risk:high", "type:feature", "agent:blocked", "needs:human"])

    result = validate_gates(_gate_input(issue=issue))

    assert result.ok is False
    assert "Issue is no longer eligible" in "\n".join(result.errors)
    assert "risk:high" in "\n".join(result.errors)


def test_validate_gates_blocks_existing_pr_and_stale_base():
    result = validate_gates(
        _gate_input(
            existing_pr_url="https://github.com/MichaelAtherton/agent-looop/pull/6",
            base_is_fresh=False,
        )
    )

    assert result.ok is False
    assert "Open PR already exists" in "\n".join(result.errors)
    assert "rebase-required" in "\n".join(result.errors)


def test_find_worker_run_comment_returns_existing_stable_heading_comment():
    comments = [
        {"id": "1", "body": "Unrelated comment", "url": "https://example.com/1"},
        {"id": "2", "body": "## Worker Run Report\nPrevious run", "url": "https://example.com/2"},
    ]

    assert find_worker_run_comment(comments) == comments[1]
