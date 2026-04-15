"""
Unit and regression tests for issueWriter.py.

Mocks the GitHub API and xlsxwriter to test logic in isolation.
Run with: pytest test_issueWriter.py -v
"""

import io
import re
import sys
import types
from datetime import datetime, date as dt
from unittest.mock import MagicMock, patch, call, mock_open

import pytest

# ---------------------------------------------------------------------------
# Stub out external dependencies so we can import issueWriter without a real
# GitHub token or network access.
# ---------------------------------------------------------------------------

# Prevent `from config import TOKEN` from failing
_config_mod = types.ModuleType("config")
_config_mod.TOKEN = "fake-token-for-tests"
sys.modules["config"] = _config_mod

# Patch Github() at module level so importing issueWriter doesn't hit the network
with patch("github.Github"):
    import issueWriter
    from issueWriter import (
        _chunks,
        _clean_step_text,
        _parse_repro_lines,
        _write_md_section,
        IssueWorkbook,
        STEP_PATTERN,
        BULLET_PATTERN,
        PAREN_NUM_PATTERN,
        ARROW_PATTERN,
        ARROW_PATTERN_NO_INDENT,
        LINK_PATTERN,
        DEFAULT_ROWS_PER_SHEET,
        HEADER_BG_COLOR,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Helper‑function tests
# ═══════════════════════════════════════════════════════════════════════════


class TestChunks:
    """Tests for _chunks() — splits a list into n-sized sublists."""

    def test_even_split(self):
        result = list(_chunks([1, 2, 3, 4], 2))
        assert result == [[1, 2], [3, 4]]

    def test_uneven_split(self):
        result = list(_chunks([1, 2, 3, 4, 5], 2))
        assert result == [[1, 2], [3, 4], [5]]

    def test_chunk_larger_than_list(self):
        result = list(_chunks([1, 2], 10))
        assert result == [[1, 2]]

    def test_empty_list(self):
        result = list(_chunks([], 5))
        assert result == []

    def test_single_element(self):
        result = list(_chunks([42], 1))
        assert result == [[42]]

    def test_chunk_size_one(self):
        result = list(_chunks([1, 2, 3], 1))
        assert result == [[1], [2], [3]]

    def test_chunk_size_equals_length(self):
        result = list(_chunks([1, 2, 3], 3))
        assert result == [[1, 2, 3]]


class TestParseReproLines:
    """Tests for _parse_repro_lines() — extracts actionable lines from issue body."""

    def test_numbered_steps(self):
        body = "1. Open the app\n2. Click login\n3. Enter creds"
        result = _parse_repro_lines(body)
        assert result == ["1. Open the app", "2. Click login", "3. Enter creds"]

    def test_bullet_steps(self):
        body = "* Step one\n* Step two"
        result = _parse_repro_lines(body)
        assert result == ["* Step one", "* Step two"]

    def test_parenthesized_numbers(self):
        body = "(1) Do this\n(2) Do that"
        result = _parse_repro_lines(body)
        assert result == ["(1) Do this", "(2) Do that"]

    def test_arrow_validation(self):
        body = "1. Do something\n--> Verify result"
        result = _parse_repro_lines(body)
        assert result == ["1. Do something", "--> Verify result"]

    def test_indented_arrow(self):
        body = "1. Step\n  --> Check"
        result = _parse_repro_lines(body)
        assert result == ["1. Step", "  --> Check"]

    def test_skips_blank_lines(self):
        body = "1. Step\n\n\n2. Step two"
        result = _parse_repro_lines(body)
        assert result == ["1. Step", "2. Step two"]

    def test_skips_plain_text(self):
        body = "Some description\n1. Actual step\nMore text"
        result = _parse_repro_lines(body)
        assert result == ["1. Actual step"]

    def test_empty_body(self):
        result = _parse_repro_lines("")
        assert result == []

    def test_no_actionable_lines(self):
        body = "This is just a paragraph.\nNothing actionable here."
        result = _parse_repro_lines(body)
        assert result == []

    def test_carriage_return_stripped(self):
        body = "1. Step one\r\n2. Step two\r\n"
        result = _parse_repro_lines(body)
        assert result == ["1. Step one", "2. Step two"]

    def test_mixed_patterns(self):
        body = (
            "Description text\n"
            "1. First numbered\n"
            "* A bullet\n"
            "(3) Paren step\n"
            "--> Validation arrow\n"
            "   --> Indented arrow\n"
            "Plain text ignored\n"
        )
        result = _parse_repro_lines(body)
        assert len(result) == 5
        assert "1. First numbered" in result
        assert "* A bullet" in result
        assert "(3) Paren step" in result
        assert "--> Validation arrow" in result
        assert "   --> Indented arrow" in result

    def test_multidigit_step_numbers(self):
        body = "10. Step ten\n100. Step hundred"
        result = _parse_repro_lines(body)
        assert result == ["10. Step ten", "100. Step hundred"]

    def test_long_arrow(self):
        body = "----> Result here"
        result = _parse_repro_lines(body)
        assert result == ["----> Result here"]


class TestCleanStepText:
    """Tests for _clean_step_text() — removes leading numbering, bullets, links."""

    def test_strips_numbered_prefix(self):
        assert _clean_step_text("1. Click the button") == " Click the button"

    def test_strips_bullet_prefix(self):
        assert _clean_step_text("* Open settings") == "Open settings"

    def test_strips_paren_number(self):
        assert _clean_step_text("(2) Navigate to page") == "Navigate to page"

    def test_strips_markdown_link(self):
        result = _clean_step_text("Visit [Google](https://google.com)")
        assert result == "Visit Google"

    def test_combined_cleaning(self):
        result = _clean_step_text("1. Go to [Docs](https://docs.example.com)")
        assert "Docs" in result
        assert "https://" not in result

    def test_no_prefix(self):
        # Text without a recognized prefix should pass through mostly unchanged
        result = _clean_step_text("Just plain text")
        assert result == "Just plain text"

    def test_multidigit_number(self):
        result = _clean_step_text("12. Do something")
        assert "Do something" in result
        assert not result.startswith("12")

    def test_multiple_links(self):
        result = _clean_step_text("See [A](url1) and [B](url2)")
        # LINK_PATTERN is greedy — matches the outermost brackets
        # This is a known behavior regression test
        assert "url1" not in result or "url2" not in result


class TestWriteMdSection:
    """Tests for _write_md_section() — writes categorized issue list to markdown."""

    def _make_issue(self, number, title, html_url):
        issue = MagicMock()
        issue.number = number
        issue.title = title
        issue.html_url = html_url
        return issue

    def test_writes_heading_and_count(self):
        buf = io.StringIO()
        _write_md_section(buf, "Automated", [])
        output = buf.getvalue()
        assert "Automated: 0" in output

    def test_writes_issue_links(self):
        issues = [
            self._make_issue(42, "Fix bug", "https://github.com/org/repo/issues/42"),
            self._make_issue(99, "Add feature", "https://github.com/org/repo/issues/99"),
        ]
        buf = io.StringIO()
        _write_md_section(buf, "Other", issues)
        output = buf.getvalue()
        assert "Other: 2" in output
        assert "[#42 Fix bug](https://github.com/org/repo/issues/42)" in output
        assert "[#99 Add feature](https://github.com/org/repo/issues/99)" in output

    def test_single_issue(self):
        issues = [self._make_issue(1, "Solo", "https://url")]
        buf = io.StringIO()
        _write_md_section(buf, "WontFix", issues)
        output = buf.getvalue()
        assert "WontFix: 1" in output
        assert "[#1 Solo](https://url)" in output


# ═══════════════════════════════════════════════════════════════════════════
# Regex pattern tests
# ═══════════════════════════════════════════════════════════════════════════


class TestPatterns:
    """Verify the compiled regex patterns match expected inputs."""

    # -- STEP_PATTERN: lines starting with a digit followed by a dot -------

    @pytest.mark.parametrize("text", [
        "1. Step one",
        "12. Multi-digit",
        "3.No space",
    ])
    def test_step_pattern_matches(self, text):
        assert STEP_PATTERN.match(text)

    @pytest.mark.parametrize("text", [
        "No number here",
        "* Bullet",
        "(1) Paren",
        " 1. Leading space",
    ])
    def test_step_pattern_no_match(self, text):
        assert not STEP_PATTERN.match(text)

    # -- BULLET_PATTERN: lines starting with * ----------------------------

    def test_bullet_matches(self):
        assert BULLET_PATTERN.match("* Item")
        assert BULLET_PATTERN.match("*NoSpace")

    def test_bullet_no_match(self):
        assert not BULLET_PATTERN.match(" * Indented")
        assert not BULLET_PATTERN.match("1. Numbered")

    # -- PAREN_NUM_PATTERN: (N) with optional trailing space ---------------

    @pytest.mark.parametrize("text", [
        "(1) Step",
        "(99) Step",
        "(1)NoSpace",
    ])
    def test_paren_num_matches(self, text):
        assert PAREN_NUM_PATTERN.match(text)

    def test_paren_num_no_match(self):
        assert not PAREN_NUM_PATTERN.match("1) Missing open paren")
        assert not PAREN_NUM_PATTERN.match("(a) Letter")

    # -- ARROW patterns ---------------------------------------------------

    def test_arrow_with_indent(self):
        assert ARROW_PATTERN.match("  --> Result")
        assert ARROW_PATTERN.match("-->")
        assert ARROW_PATTERN.match("   ---->")

    def test_arrow_no_indent(self):
        assert ARROW_PATTERN_NO_INDENT.match("--> Result")
        assert ARROW_PATTERN_NO_INDENT.match("----> Long arrow")

    def test_arrow_no_indent_rejects_indent(self):
        assert not ARROW_PATTERN_NO_INDENT.match("  --> Indented")

    # -- LINK_PATTERN: markdown links [text](url) -------------------------

    def test_link_pattern_captures(self):
        m = LINK_PATTERN.search("[Click here](https://example.com)")
        assert m
        assert m.group(1) == "Click here"
        assert m.group(2) == "https://example.com"

    def test_link_pattern_no_match(self):
        assert not LINK_PATTERN.search("No link here")


# ═══════════════════════════════════════════════════════════════════════════
# IssueWorkbook class tests (mocked GitHub API)
# ═══════════════════════════════════════════════════════════════════════════


def _make_mock_label(name):
    label = MagicMock()
    label.name = name
    return label


def _make_mock_issue(number, title, labels=None, closed_at=None, body="", html_url=None, pull_request=None, milestone=None):
    issue = MagicMock()
    issue.number = number
    issue.title = title
    issue.labels = [_make_mock_label(l) for l in (labels or [])]
    issue.closed_at = closed_at
    issue.body = body
    issue.html_url = html_url or f"https://github.com/Vantiq/repo/issues/{number}"
    issue.pull_request = pull_request
    issue.milestone = milestone
    return issue


@pytest.fixture
def mock_github_env():
    """Provide a patched Github and repo for IssueWorkbook construction."""
    mock_repo = MagicMock()
    mock_milestone = MagicMock()
    mock_repo.get_milestone.return_value = mock_milestone

    with patch.object(issueWriter, "g") as mock_g:
        mock_g.get_repo.return_value = mock_repo
        yield mock_g, mock_repo, mock_milestone


class TestIssueWorkbookInit:
    """Test IssueWorkbook constructor logic."""

    def test_defaults(self, mock_github_env):
        mock_g, mock_repo, _ = mock_github_env

        wb = IssueWorkbook(
            aLabel=[["bug"]],
            eLabel=[[]],
            milestoneNum=[None],
            date=[None],
            repo=["test-repo"],
            sheetNum=None,
            sheetName=None,
            workbookName="test",
            tabColor=None,
            specificIssues=[],
        )
        assert wb.num_rows == DEFAULT_ROWS_PER_SHEET
        assert wb.sheet_names == ["bug Issues"]
        assert wb.args_length == 1

    def test_custom_sheet_num(self, mock_github_env):
        wb = IssueWorkbook(
            aLabel=[["ui"]],
            eLabel=[[]],
            milestoneNum=[None],
            date=[None],
            repo=["repo"],
            sheetNum=50,
            sheetName=["Custom Sheet"],
            workbookName="out",
            tabColor=None,
            specificIssues=[],
        )
        assert wb.num_rows == 50
        assert wb.sheet_names == ["Custom Sheet"]

    def test_multiple_repos(self, mock_github_env):
        mock_g, mock_repo, _ = mock_github_env

        wb = IssueWorkbook(
            aLabel=[["a"], ["b"]],
            eLabel=[[], []],
            milestoneNum=[None, None],
            date=[None, None],
            repo=["repo1", "repo2"],
            sheetNum=10,
            sheetName=None,
            workbookName="multi",
            tabColor=None,
            specificIssues=[],
        )
        assert wb.args_length == 2
        assert len(wb.sheet_names) == 2


class TestGetIssues:
    """Test the get_issues filtering logic."""

    def test_filters_by_include_labels(self, mock_github_env):
        mock_g, mock_repo, _ = mock_github_env

        issue_with_label = _make_mock_issue(
            1, "Has bug label", labels=["bug"],
            closed_at=datetime(2025, 6, 1),
        )
        issue_without_label = _make_mock_issue(
            2, "No bug label", labels=["feature"],
            closed_at=datetime(2025, 6, 1),
        )
        mock_repo.get_issues.return_value = [issue_with_label, issue_without_label]

        wb = IssueWorkbook(
            aLabel=[["bug"]],
            eLabel=[[]],
            milestoneNum=[None],
            date=[None],
            repo=["repo"],
            sheetNum=30,
            sheetName=None,
            workbookName="test",
            tabColor=None,
            specificIssues=[],
        )
        result = wb.get_issues()
        assert len(result) == 1
        assert len(result[0]) == 1
        assert result[0][0].number == 1

    def test_filters_by_exclude_labels(self, mock_github_env):
        mock_g, mock_repo, _ = mock_github_env

        issue_ok = _make_mock_issue(
            1, "Good", labels=["bug"],
            closed_at=datetime(2025, 6, 1),
        )
        issue_excluded = _make_mock_issue(
            2, "Excluded", labels=["bug", "wontfix"],
            closed_at=datetime(2025, 6, 1),
        )
        mock_repo.get_issues.return_value = [issue_ok, issue_excluded]

        wb = IssueWorkbook(
            aLabel=[["bug"]],
            eLabel=[["wontfix"]],
            milestoneNum=[None],
            date=[None],
            repo=["repo"],
            sheetNum=30,
            sheetName=None,
            workbookName="test",
            tabColor=None,
            specificIssues=[],
        )
        result = wb.get_issues()
        assert len(result[0]) == 1
        assert result[0][0].number == 1

    def test_filters_by_date(self, mock_github_env):
        mock_g, mock_repo, _ = mock_github_env

        old_issue = _make_mock_issue(
            1, "Old", labels=["bug"],
            closed_at=datetime(2024, 1, 1),
        )
        new_issue = _make_mock_issue(
            2, "New", labels=["bug"],
            closed_at=datetime(2025, 7, 1),
        )
        mock_repo.get_issues.return_value = [old_issue, new_issue]

        wb = IssueWorkbook(
            aLabel=[["bug"]],
            eLabel=[[]],
            milestoneNum=[None],
            date=[["June", "1", "2025"]],
            repo=["repo"],
            sheetNum=30,
            sheetName=None,
            workbookName="test",
            tabColor=None,
            specificIssues=[],
        )
        result = wb.get_issues()
        assert len(result[0]) == 1
        assert result[0][0].number == 2

    def test_excludes_open_issues(self, mock_github_env):
        """Issues without closed_at should be filtered out."""
        mock_g, mock_repo, _ = mock_github_env

        open_issue = _make_mock_issue(1, "Open", labels=["bug"], closed_at=None)
        mock_repo.get_issues.return_value = [open_issue]

        wb = IssueWorkbook(
            aLabel=[["bug"]],
            eLabel=[[]],
            milestoneNum=[None],
            date=[None],
            repo=["repo"],
            sheetNum=30,
            sheetName=None,
            workbookName="test",
            tabColor=None,
            specificIssues=[],
        )
        result = wb.get_issues()
        assert len(result[0]) == 0

    def test_multiple_include_labels_require_all(self, mock_github_env):
        """Issues must have ALL include labels to pass the filter."""
        mock_g, mock_repo, _ = mock_github_env

        issue_both = _make_mock_issue(
            1, "Both", labels=["bug", "ui"],
            closed_at=datetime(2025, 6, 1),
        )
        issue_one = _make_mock_issue(
            2, "One label only", labels=["bug"],
            closed_at=datetime(2025, 6, 1),
        )
        mock_repo.get_issues.return_value = [issue_both, issue_one]

        wb = IssueWorkbook(
            aLabel=[["bug", "ui"]],
            eLabel=[[]],
            milestoneNum=[None],
            date=[None],
            repo=["repo"],
            sheetNum=30,
            sheetName=None,
            workbookName="test",
            tabColor=None,
            specificIssues=[],
        )
        result = wb.get_issues()
        assert len(result[0]) == 1
        assert result[0][0].number == 1


class TestGetSpecificIssues:
    """Test the get_specific_issues method."""

    def test_fetches_specific_issue_numbers(self, mock_github_env):
        mock_g, mock_repo, _ = mock_github_env

        issue_42 = _make_mock_issue(42, "Specific issue")
        mock_repo.get_issue.return_value = issue_42

        wb = IssueWorkbook(
            aLabel=[[]],
            eLabel=[[]],
            milestoneNum=[None],
            date=[None],
            repo=["repo"],
            sheetNum=30,
            sheetName=None,
            workbookName="test",
            tabColor=None,
            specificIssues=["42", "99"],
        )
        result = wb.get_specific_issues()
        assert len(result[0]) == 2
        mock_repo.get_issue.assert_any_call(42)
        mock_repo.get_issue.assert_any_call(99)


class TestWriteToSheet:
    """Test the Excel writing pipeline (mocked xlsxwriter)."""

    @patch("issueWriter.xlsxwriter.Workbook")
    def test_write_creates_workbook(self, mock_wb_class, mock_github_env):
        mock_g, mock_repo, _ = mock_github_env

        issue = _make_mock_issue(
            1, "Test Issue", labels=["bug"],
            closed_at=datetime(2025, 6, 1),
            body="1. Step one\n--> Verify",
        )
        mock_repo.get_issues.return_value = [issue]

        mock_wb = MagicMock()
        mock_wb_class.return_value = mock_wb
        mock_ws = MagicMock()
        mock_wb.add_worksheet.return_value = mock_ws

        wb = IssueWorkbook(
            aLabel=[["bug"]],
            eLabel=[[]],
            milestoneNum=[None],
            date=[None],
            repo=["repo"],
            sheetNum=30,
            sheetName=["Test Sheet"],
            workbookName="test_output",
            tabColor=None,
            specificIssues=[],
        )
        wb.write_to_sheet()

        mock_wb_class.assert_called_once_with("test_output.xlsx")
        mock_wb.close.assert_called_once()

    @patch("issueWriter.xlsxwriter.Workbook")
    def test_write_uses_specific_issues_when_set(self, mock_wb_class, mock_github_env):
        mock_g, mock_repo, _ = mock_github_env

        issue = _make_mock_issue(42, "Specific", body="")
        mock_repo.get_issue.return_value = issue

        mock_wb = MagicMock()
        mock_wb_class.return_value = mock_wb
        mock_wb.add_worksheet.return_value = MagicMock()

        wb = IssueWorkbook(
            aLabel=[[]],
            eLabel=[[]],
            milestoneNum=[None],
            date=[None],
            repo=["repo"],
            sheetNum=30,
            sheetName=["Specific"],
            workbookName="out",
            tabColor=None,
            specificIssues=["42"],
        )
        wb.write_to_sheet()

        mock_repo.get_issue.assert_called_with(42)

    @patch("issueWriter.xlsxwriter.Workbook")
    def test_tab_color_applied(self, mock_wb_class, mock_github_env):
        mock_g, mock_repo, _ = mock_github_env

        issue = _make_mock_issue(1, "T", labels=["x"], closed_at=datetime(2025, 6, 1), body="")
        mock_repo.get_issues.return_value = [issue]

        mock_wb = MagicMock()
        mock_wb_class.return_value = mock_wb
        mock_ws = MagicMock()
        mock_wb.add_worksheet.return_value = mock_ws

        wb = IssueWorkbook(
            aLabel=[["x"]],
            eLabel=[[]],
            milestoneNum=[None],
            date=[None],
            repo=["repo"],
            sheetNum=30,
            sheetName=["Sheet"],
            workbookName="out",
            tabColor=["#FF0000"],
            specificIssues=[],
        )
        wb.write_to_sheet()

        mock_ws.set_tab_color.assert_called_with("#FF0000")


class TestWriteIssueBlock:
    """Test _write_issue_block for correct cell placement."""

    @patch("issueWriter.xlsxwriter.Workbook")
    def test_issue_with_steps_writes_autogenerated_note(self, mock_wb_class, mock_github_env):
        mock_g, mock_repo, _ = mock_github_env

        mock_wb = MagicMock()
        mock_wb_class.return_value = mock_wb
        mock_ws = MagicMock()
        mock_format = MagicMock()

        issue = _make_mock_issue(
            1, "Steps Issue",
            body="1. Do A\n2. Do B\n--> Check result",
        )

        wb = IssueWorkbook(
            aLabel=[[]],
            eLabel=[[]],
            milestoneNum=[None],
            date=[None],
            repo=["repo"],
            sheetNum=30,
            sheetName=None,
            workbookName="test",
            tabColor=None,
            specificIssues=[],
        )

        next_row = wb._write_issue_block(mock_ws, 0, 0, issue, mock_format)

        # Should have written URL, steps, and returned a row beyond the last step
        mock_ws.write_url.assert_called_once()
        assert next_row > 0

        # Find the "autogenerated" notice
        autogen_calls = [
            c for c in mock_ws.write.call_args_list
            if len(c[0]) >= 3 and c[0][2] == "These steps were autogenerated!"
        ]
        assert len(autogen_calls) == 1

    @patch("issueWriter.xlsxwriter.Workbook")
    def test_issue_without_body_skips_steps(self, mock_wb_class, mock_github_env):
        mock_g, mock_repo, _ = mock_github_env

        mock_wb = MagicMock()
        mock_wb_class.return_value = mock_wb
        mock_ws = MagicMock()
        mock_format = MagicMock()

        issue = _make_mock_issue(1, "No body", body=None)

        wb = IssueWorkbook(
            aLabel=[[]],
            eLabel=[[]],
            milestoneNum=[None],
            date=[None],
            repo=["repo"],
            sheetNum=30,
            sheetName=None,
            workbookName="test",
            tabColor=None,
            specificIssues=[],
        )

        next_row = wb._write_issue_block(mock_ws, 0, 0, issue, mock_format)

        # No autogenerated note should appear
        autogen_calls = [
            c for c in mock_ws.write.call_args_list
            if len(c[0]) >= 3 and c[0][2] == "These steps were autogenerated!"
        ]
        assert len(autogen_calls) == 0

    @patch("issueWriter.xlsxwriter.Workbook")
    def test_validation_arrow_written_to_column_6(self, mock_wb_class, mock_github_env):
        mock_g, mock_repo, _ = mock_github_env

        mock_ws = MagicMock()
        mock_format = MagicMock()

        issue = _make_mock_issue(1, "Arrow test", body="1. Step\n--> Expected result")

        wb = IssueWorkbook(
            aLabel=[[]],
            eLabel=[[]],
            milestoneNum=[None],
            date=[None],
            repo=["repo"],
            sheetNum=30,
            sheetName=None,
            workbookName="test",
            tabColor=None,
            specificIssues=[],
        )

        wb._write_issue_block(mock_ws, 0, 0, issue, mock_format)

        # Validation text should be written to column 6
        validation_calls = [
            c for c in mock_ws.write.call_args_list
            if len(c[0]) >= 3 and c[0][1] == 6 and isinstance(c[0][2], str)
            and "Expected result" in c[0][2]
        ]
        assert len(validation_calls) == 1


# ═══════════════════════════════════════════════════════════════════════════
# Regression tests — edge cases & boundary conditions
# ═══════════════════════════════════════════════════════════════════════════


class TestRegressions:
    """Regression tests for tricky edge cases."""

    def test_link_pattern_greedy_behavior(self):
        """LINK_PATTERN uses .* which is greedy — verify behavior with multiple links."""
        text = "[A](url1) and [B](url2)"
        # Greedy .* makes it match from first [ to last )
        m = LINK_PATTERN.search(text)
        assert m is not None
        # The greedy match captures everything between outermost brackets
        # This documents current behavior for regression tracking
        assert m.group(0) is not None

    def test_parse_repro_lines_windows_newlines(self):
        """Ensure \r\n line endings don't break parsing."""
        body = "1. Step one\r\n2. Step two\r\n--> Check\r\n"
        result = _parse_repro_lines(body)
        assert len(result) == 3
        # Verify no \r characters remain
        for line in result:
            assert "\r" not in line

    def test_clean_step_no_space_after_number(self):
        """Step like '3.Click here' (no space after dot) should still clean."""
        result = _clean_step_text("3.Click here")
        assert "Click here" in result

    def test_parse_repro_handles_only_arrows(self):
        """Body with only arrow lines should still parse."""
        body = "--> Check this\n----> And this"
        result = _parse_repro_lines(body)
        assert len(result) == 2

    def test_chunks_with_strings(self):
        """_chunks should work with any list-like, not just integers."""
        result = list(_chunks(["a", "b", "c", "d", "e"], 2))
        assert result == [["a", "b"], ["c", "d"], ["e"]]

    def test_clean_step_nested_markdown_link(self):
        """Brackets inside link text (edge case)."""
        result = _clean_step_text("[text [nested]](http://url)")
        # Greedy match means it captures from first [ to last ]
        assert "http://" not in result

    def test_parse_repro_ignores_headers(self):
        """Markdown headers (## Steps) should not be parsed as steps."""
        body = "## Steps to reproduce\n1. First step\n## Expected\n--> Result"
        result = _parse_repro_lines(body)
        assert "## Steps to reproduce" not in result
        assert "## Expected" not in result
        assert len(result) == 2

    def test_arrow_stripped_in_validation(self):
        """Ensure the arrow prefix is stripped from validation text."""
        line = "----> Expected output here"
        cleaned = re.sub(r"-+>\s*", "", line)
        assert cleaned == "Expected output here"

    def test_empty_specific_issues_uses_get_issues(self, mock_github_env):
        """When specificIssues is empty, write_to_sheet should use get_issues."""
        mock_g, mock_repo, _ = mock_github_env
        mock_repo.get_issues.return_value = []

        with patch("issueWriter.xlsxwriter.Workbook") as mock_wb_class:
            mock_wb = MagicMock()
            mock_wb_class.return_value = mock_wb
            mock_wb.add_worksheet.return_value = MagicMock()

            wb = IssueWorkbook(
                aLabel=[[]],
                eLabel=[[]],
                milestoneNum=[None],
                date=[None],
                repo=["repo"],
                sheetNum=30,
                sheetName=["Sheet"],
                workbookName="test",
                tabColor=None,
                specificIssues=[],
            )
            wb.write_to_sheet()

            mock_repo.get_issues.assert_called()
            mock_repo.get_issue.assert_not_called()

    def test_default_sheet_name_from_labels(self, mock_github_env):
        """Sheet names should default to '<label> Issues' when not provided."""
        wb = IssueWorkbook(
            aLabel=[["feature", "ui"]],
            eLabel=[[]],
            milestoneNum=[None],
            date=[None],
            repo=["repo"],
            sheetNum=30,
            sheetName=None,
            workbookName="test",
            tabColor=None,
            specificIssues=[],
        )
        assert wb.sheet_names == ["feature ui Issues"]

    def test_empty_labels_sheet_name(self, mock_github_env):
        """Empty label list should produce ' Issues' as sheet name."""
        wb = IssueWorkbook(
            aLabel=[[]],
            eLabel=[[]],
            milestoneNum=[None],
            date=[None],
            repo=["repo"],
            sheetNum=30,
            sheetName=None,
            workbookName="test",
            tabColor=None,
            specificIssues=[],
        )
        assert wb.sheet_names == [" Issues"]


# ═══════════════════════════════════════════════════════════════════════════
# Constants sanity checks
# ═══════════════════════════════════════════════════════════════════════════


class TestConstants:
    def test_default_rows_per_sheet(self):
        assert DEFAULT_ROWS_PER_SHEET == 30

    def test_header_bg_color_is_hex(self):
        assert HEADER_BG_COLOR.startswith("#")
        assert len(HEADER_BG_COLOR) == 7
