from pathlib import Path

from agent_looop.reviewer import ReviewInput, review_worker_output, write_review_report


def test_reviewer_passes_in_scope_docs_worker_output(tmp_path: Path):
    review = review_worker_output(
        ReviewInput(
            issue_number=1,
            issue_title="Fix broken README link",
            issue_labels=["risk:low", "type:docs", "agent:ready"],
            changed_files=[
                "README.md",
                "reports/worker-plans/issue-1-plan.md",
                "reports/worker-runs/issue-1-worker-run.md",
            ],
            verification_passed=True,
            plan_exists=True,
            run_report_exists=True,
            diff_text="- [Getting started](docs/quickstart.md)\n+ [Getting started](docs/getting-started.md)",
        )
    )

    assert review.recommendation == "pass"
    assert review.repair_attempt_allowed is False
    assert review.critical_issues == []


def test_reviewer_revises_missing_run_report_once():
    review = review_worker_output(
        ReviewInput(
            issue_number=1,
            issue_title="Fix broken README link",
            issue_labels=["risk:low", "type:docs", "agent:ready"],
            changed_files=["README.md", "reports/worker-plans/issue-1-plan.md"],
            verification_passed=True,
            plan_exists=True,
            run_report_exists=False,
            diff_text="+ [Getting started](docs/getting-started.md)",
        )
    )

    assert review.recommendation == "revise"
    assert review.repair_attempt_allowed is True
    assert "run report" in " ".join(review.warnings).lower()


def test_reviewer_escalates_out_of_scope_code_change():
    review = review_worker_output(
        ReviewInput(
            issue_number=1,
            issue_title="Fix broken README link",
            issue_labels=["risk:low", "type:docs", "agent:ready"],
            changed_files=["README.md", "src/agent_looop/parser.py"],
            verification_passed=True,
            plan_exists=True,
            run_report_exists=True,
            diff_text="+ code change",
        )
    )

    assert review.recommendation == "human_escalation"
    assert review.repair_attempt_allowed is False
    assert any("out-of-scope" in finding.lower() for finding in review.critical_issues)


def test_reviewer_escalates_ineligible_issue_labels():
    review = review_worker_output(
        ReviewInput(
            issue_number=2,
            issue_title="Redesign auth",
            issue_labels=["risk:high", "type:feature", "agent:blocked", "needs:human"],
            changed_files=["README.md"],
            verification_passed=True,
            plan_exists=True,
            run_report_exists=True,
            diff_text="+ change",
        )
    )

    assert review.recommendation == "human_escalation"
    assert any("ineligible" in finding.lower() for finding in review.critical_issues)


def test_write_review_report_contains_recommendation_and_next_gate(tmp_path: Path):
    review = review_worker_output(
        ReviewInput(
            issue_number=1,
            issue_title="Fix broken README link",
            issue_labels=["risk:low", "type:docs", "agent:ready"],
            changed_files=[
                "README.md",
                "reports/worker-plans/issue-1-plan.md",
                "reports/worker-runs/issue-1-worker-run.md",
            ],
            verification_passed=True,
            plan_exists=True,
            run_report_exists=True,
            diff_text="+ [Getting started](docs/getting-started.md)",
        )
    )

    report_path = write_review_report(tmp_path, review)

    text = report_path.read_text()
    assert "# Reviewer Report" in text
    assert "Recommendation: pass" in text
    assert "Draft PR may be opened" in text
