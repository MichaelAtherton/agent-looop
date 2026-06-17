from agent_looop.manager_dry_run import (
    Issue,
    classify_issue,
    expected_managed_labels,
    render_dry_run_report,
)


def test_classifies_broken_readme_link_as_agent_ready_docs():
    issue = Issue(
        number=1,
        title="Fix broken README link",
        body="""
        ## Goal
        Fix the broken Getting Started link in README.md.

        ## Acceptance criteria
        - README.md links to docs/getting-started.md.
        - No code files are changed.

        ## Expected verification
        - Inspect the README diff.
        - Confirm the target file exists.

        ## Known risks / sensitive areas
        Documentation-only. No auth, billing, permissions, security, migration, deployment, or product behavior changes.
        """,
        labels=[],
        url="https://example.com/1",
    )

    result = classify_issue(issue)

    assert result.risk == "risk:low"
    assert result.issue_type == "type:docs"
    assert result.agent_ready is True
    assert result.apply_mode_labels == ["risk:low", "type:docs", "agent:ready"]
    assert result.human_question == ""


def test_blocks_auth_architecture_as_high_risk_with_specific_question():
    issue = Issue(
        number=2,
        title="Redesign our auth architecture to be more scalable",
        body="""
        ## Goal
        Redesign our auth architecture so it can scale better.

        ## Acceptance criteria
        _To be defined._
        """,
        labels=[],
        url="https://example.com/2",
    )

    result = classify_issue(issue)

    assert result.risk == "risk:high"
    assert result.agent_ready is False
    assert "needs:human" in result.apply_mode_labels
    assert "agent:blocked" in result.apply_mode_labels
    assert "auth behavior" in result.human_question


def test_blocks_payment_permission_logic_as_high_risk():
    issue = Issue(
        number=3,
        title="Update payment permission logic",
        body="""
        ## Goal
        Update payment permission logic.

        ## Acceptance criteria
        _To be defined by a human owner._
        """,
        labels=[],
        url="https://example.com/3",
    )

    result = classify_issue(issue)

    assert result.risk == "risk:high"
    assert result.agent_ready is False
    assert "needs:human" in result.apply_mode_labels
    assert "agent:blocked" in result.apply_mode_labels
    assert "payment permission behavior" in result.human_question


def test_classifies_parser_regression_as_agent_ready_test():
    issue = Issue(
        number=4,
        title="Add missing test for parser error on empty input",
        body="""
        ## Goal
        Add a regression test for empty parser input.

        ## Acceptance criteria
        - tests/test_parser.py includes a test for empty input.
        - The test asserts that parse_input(\"\") raises ValueError.
        - No production behavior is changed unless required to make the documented behavior true.

        ## Expected verification
        - python -m pytest passes.

        ## Known risks / sensitive areas
        Test-only task. No auth, billing, permissions, security, migration, deployment, or product behavior changes.
        """,
        labels=[],
        url="https://example.com/4",
    )

    result = classify_issue(issue)

    assert result.risk == "risk:low"
    assert result.issue_type == "type:test"
    assert result.agent_ready is True
    assert result.apply_mode_labels == ["risk:low", "type:test", "agent:ready"]


def test_blocks_vague_onboarding_with_expected_question():
    issue = Issue(
        number=5,
        title="Improve onboarding",
        body="""
        ## Goal
        Improve onboarding.

        ## Acceptance criteria
        _To be defined._
        """,
        labels=[],
        url="https://example.com/5",
    )

    result = classify_issue(issue)

    assert result.agent_ready is False
    assert "needs:human" in result.apply_mode_labels
    assert "agent:blocked" in result.apply_mode_labels
    assert result.human_question == "What specific onboarding behavior or document should be changed?"


def test_report_includes_summary_blockers_and_no_mutation_language():
    issues = [
        Issue(1, "Fix broken README link", "README.md link acceptance criteria", [], "https://example.com/1"),
        Issue(2, "Redesign our auth architecture to be more scalable", "Acceptance criteria: _To be defined._", [], "https://example.com/2"),
    ]
    classifications = [classify_issue(issue) for issue in issues]

    report = render_dry_run_report(
        repo="MichaelAtherton/agent-looop",
        issues=issues,
        classifications=classifications,
        existing_labels=expected_managed_labels(),
        run_time="2026-06-17T00:00:00Z",
    )

    assert "# Manager Dry-Run Report" in report
    assert "No GitHub mutations were performed" in report
    assert "Recommended agent-ready count: 1" in report
    assert "Recommended needs-human count: 1" in report
    assert "#1 Fix broken README link" in report
    assert "#2 Redesign our auth architecture to be more scalable" in report
    assert "What specific auth behavior, constraint, or failure mode should be addressed first?" in report
