from pathlib import Path

from agent_looop.manager_dry_run import Issue
from agent_looop.worker_prototype import (
    TaskPacket,
    _changed_files,
    _verify,
    build_task_packet,
    select_oldest_eligible_issue,
    write_worker_plan,
)


def test_selects_oldest_low_risk_agent_ready_docs_or_test_issue():
    issues = [
        Issue(1, "Fix broken README link", "body", ["risk:low", "type:docs", "agent:ready"], "https://example.com/1"),
        Issue(2, "Blocked auth", "body", ["risk:high", "type:feature", "agent:blocked", "needs:human"], "https://example.com/2"),
        Issue(4, "Add parser test", "body", ["risk:low", "type:test", "agent:ready"], "https://example.com/4"),
    ]

    selected = select_oldest_eligible_issue(issues)

    assert selected is not None
    assert selected.number == 1


def test_skips_blocked_medium_high_and_non_allowed_types():
    issues = [
        Issue(1, "Feature ready but not allowed", "body", ["risk:low", "type:feature", "agent:ready"], "https://example.com/1"),
        Issue(2, "Medium docs", "body", ["risk:medium", "type:docs", "agent:ready"], "https://example.com/2"),
        Issue(3, "Blocked test", "body", ["risk:low", "type:test", "agent:blocked", "agent:ready"], "https://example.com/3"),
    ]

    assert select_oldest_eligible_issue(issues) is None


def test_build_task_packet_for_docs_issue_has_allowed_and_forbidden_actions():
    issue = Issue(
        1,
        "Fix broken README link",
        "Update README.md link from docs/quickstart.md to docs/getting-started.md.",
        ["risk:low", "type:docs", "agent:ready"],
        "https://example.com/1",
    )

    packet = build_task_packet(issue)

    assert packet.task_id == "issue-1"
    assert packet.issue_url == "https://example.com/1"
    assert packet.allowed_actions == ["Edit documentation files only"]
    assert "No code changes" in packet.forbidden_actions
    assert packet.verification_method == "Inspect README diff and confirm docs/getting-started.md exists"


def test_write_worker_plan_persists_plan_before_editing(tmp_path: Path):
    packet = TaskPacket(
        task_id="issue-1",
        issue_url="https://example.com/1",
        goal="Fix broken README link",
        source_evidence="Issue body",
        agent_assessment="risk:low type:docs agent:ready",
        allowed_actions=["Edit documentation files only"],
        forbidden_actions=["No code changes"],
        expected_output="README link fixed",
        acceptance_criteria=["README.md links to docs/getting-started.md"],
        verification_method="Inspect README diff and confirm docs/getting-started.md exists",
        escalation_rules=["Stop if the target file does not exist"],
    )

    plan_path = write_worker_plan(tmp_path, packet)

    assert plan_path.exists()
    text = plan_path.read_text()
    assert "Objective:" in text
    assert "Fix broken README link" in text
    assert "Files expected to touch:" in text
    assert "README.md" in text
    assert "Stop conditions:" in text


def test_changed_files_reports_untracked_files_inside_directories(tmp_path: Path):
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "tracked.txt").write_text("before\n")
    subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-m", "init"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / "tracked.txt").write_text("after\n")
    (tmp_path / "reports" / "worker-plans").mkdir(parents=True)
    (tmp_path / "reports" / "worker-plans" / "issue-1-plan.md").write_text("plan\n")

    assert _changed_files(tmp_path) == ["tracked.txt", "reports/worker-plans/issue-1-plan.md"]


def test_docs_verification_command_checks_target_file_and_readme_link(tmp_path: Path):
    packet = TaskPacket(
        task_id="issue-1",
        issue_url="https://example.com/1",
        goal="Fix broken README link",
        source_evidence="Issue body",
        agent_assessment="risk:low type:docs agent:ready",
        allowed_actions=["Edit documentation files only"],
        forbidden_actions=["No code changes"],
        expected_output="README link fixed",
        acceptance_criteria=["README.md links to docs/getting-started.md"],
        verification_method="Inspect README diff and confirm docs/getting-started.md exists",
        escalation_rules=["Stop if the target file does not exist"],
    )
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "getting-started.md").write_text("# Getting Started\n")
    (tmp_path / "README.md").write_text("See docs/getting-started.md\n")
    (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\ntestpaths = ['tests']\n")
    (tmp_path / "tests").mkdir()

    command, _, _ = _verify(tmp_path, packet)

    assert "test -f docs/getting-started.md" in command
    assert "grep -q 'docs/getting-started.md' README.md" in command
