from agent_looop.manager_apply import build_apply_actions, render_agent_assessment_comment
from agent_looop.manager_dry_run import Classification, Issue


def test_render_agent_assessment_comment_for_ready_docs_issue():
    classification = Classification(
        issue_number=1,
        issue_title="Fix broken README link",
        risk="risk:low",
        issue_type="type:docs",
        agent_ready=True,
        confidence=0.95,
        reason="Documentation-only work with clear scope and acceptance criteria.",
        required_verification="Inspect documentation diff and confirm referenced file/link target exists.",
        human_question="",
        apply_mode_labels=["risk:low", "type:docs", "agent:ready"],
    )

    comment = render_agent_assessment_comment(classification)

    assert comment.startswith("## Agent Assessment")
    assert "Risk: low" in comment
    assert "Type: docs" in comment
    assert "Agent-ready: yes" in comment
    assert "Documentation-only edit within the issue scope" in comment
    assert "Human question:" not in comment


def test_render_agent_assessment_comment_for_blocked_issue_includes_question():
    classification = Classification(
        issue_number=2,
        issue_title="Redesign our auth architecture to be more scalable",
        risk="risk:high",
        issue_type="type:feature",
        agent_ready=False,
        confidence=0.98,
        reason="Authentication architecture is a blocked v1 scope.",
        required_verification="Human-defined architecture decision and verification plan required before any agent work.",
        human_question="What specific auth behavior, constraint, or failure mode should be addressed first?",
        apply_mode_labels=["risk:high", "type:feature", "needs:human", "agent:blocked"],
    )

    comment = render_agent_assessment_comment(classification)

    assert "Agent-ready: no" in comment
    assert "Worker must not select this issue" in comment
    assert "Human question:" in comment
    assert "What specific auth behavior" in comment


def test_build_apply_actions_adds_missing_labels_and_comments_without_removing_existing_labels():
    issues = [
        Issue(
            number=1,
            title="Fix broken README link",
            body="",
            labels=["documentation"],
            url="https://example.com/1",
        ),
        Issue(
            number=2,
            title="Redesign our auth architecture to be more scalable",
            body="",
            labels=["risk:high"],
            url="https://example.com/2",
        ),
    ]
    classifications = [
        Classification(
            issue_number=1,
            issue_title="Fix broken README link",
            risk="risk:low",
            issue_type="type:docs",
            agent_ready=True,
            confidence=0.95,
            reason="Documentation-only work with clear scope and acceptance criteria.",
            required_verification="Inspect documentation diff and confirm referenced file/link target exists.",
            human_question="",
            apply_mode_labels=["risk:low", "type:docs", "agent:ready"],
        ),
        Classification(
            issue_number=2,
            issue_title="Redesign our auth architecture to be more scalable",
            risk="risk:high",
            issue_type="type:feature",
            agent_ready=False,
            confidence=0.98,
            reason="Authentication architecture is a blocked v1 scope.",
            required_verification="Human-defined architecture decision and verification plan required before any agent work.",
            human_question="What specific auth behavior, constraint, or failure mode should be addressed first?",
            apply_mode_labels=["risk:high", "type:feature", "needs:human", "agent:blocked"],
        ),
    ]

    actions = build_apply_actions(issues, classifications)

    assert actions[0].labels_to_add == ["risk:low", "type:docs", "agent:ready"]
    assert actions[1].labels_to_add == ["type:feature", "needs:human", "agent:blocked"]
    assert all(action.comment_body.startswith("## Agent Assessment") for action in actions)


def test_build_apply_actions_rejects_false_ready_medium_or_high_risk():
    issue = Issue(9, "Unsafe ready", "", [], "https://example.com/9")
    classification = Classification(
        issue_number=9,
        issue_title="Unsafe ready",
        risk="risk:high",
        issue_type="type:feature",
        agent_ready=True,
        confidence=0.5,
        reason="bad classification",
        required_verification="",
        human_question="",
        apply_mode_labels=["risk:high", "type:feature", "agent:ready"],
    )

    try:
        build_apply_actions([issue], [classification])
    except ValueError as exc:
        assert "false-ready" in str(exc)
    else:
        raise AssertionError("expected false-ready classification to be rejected")
