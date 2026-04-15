import argparse
import re

import github.GithubObject
import xlsxwriter

from config import TOKEN
from datetime import datetime, date as dt
from dateutil.parser import parse
from github import Github

# ── Constants ────────────────────────────────────────────────────────────────

DEFAULT_ROWS_PER_SHEET = 30
HEADER_BG_COLOR = "#d7dbd8"

# Regex patterns for parsing issue body text
STEP_PATTERN = re.compile(r"^\d+\.")
BULLET_PATTERN = re.compile(r"^\*")
PAREN_NUM_PATTERN = re.compile(r"^\(\d+\)\s*")
ARROW_PATTERN = re.compile(r"^\s*-+>")
ARROW_PATTERN_NO_INDENT = re.compile(r"^-+>")
LINK_PATTERN = re.compile(r"\[(.*)\]\((.*)\)")

# Authenticate once at module level
g = Github(TOKEN)


# ── Main class ───────────────────────────────────────────────────────────────

class IssueWorkbook:
    """Fetches GitHub issues and writes them to an Excel workbook for QA tracking."""

    def __init__(
        self,
        aLabel,
        eLabel,
        milestoneNum,
        date,
        repo,
        sheetNum,
        sheetName,
        workbookName,
        tabColor,
        specificIssues,
    ):
        self.include_labels = [labels if labels else [] for labels in aLabel]
        self.exclude_labels = [labels if labels else [] for labels in eLabel]
        self.repos = [g.get_repo(f"Vantiq/{r}") for r in repo]

        self.milestones = [
            self.repos[idx].get_milestone(int(mn[0]))
            if mn
            else github.GithubObject.NotSet
            for idx, mn in enumerate(milestoneNum)
        ]

        self.since_dates = [
            parse(" ".join(d)) if d else datetime(dt.min.year, dt.min.month, dt.min.day)
            for d in date
        ]

        self.num_rows = sheetNum if sheetNum else DEFAULT_ROWS_PER_SHEET
        self.sheet_names = sheetName if sheetName else [f'{" ".join(labels)} Issues' for labels in self.include_labels]
        self.tab_colors = tabColor
        self.specific_issues = specificIssues
        self.workbook_name = workbookName

        self.args_length = len(self.repos)
        self.issue_list = []

    # ── Issue fetching ───────────────────────────────────────────────────

    def get_issues(self):
        """Fetch issues from each repo, filtered by include/exclude labels and date."""
        issue_list = []

        for i in range(self.args_length):
            repo_issues = self.repos[i].get_issues(
                state="all",
                milestone=self.milestones[i],
                direction="asc",
            )

            # Keep only issues that have ALL of the "include" labels
            for label in self.include_labels[i]:
                repo_issues = [
                    issue for issue in repo_issues
                    if label in [l.name for l in issue.labels]
                ]

            # Remove issues that have ANY of the "exclude" labels
            for label in self.exclude_labels[i]:
                repo_issues = [
                    issue for issue in repo_issues
                    if label not in [l.name for l in issue.labels]
                ]

            # Keep only issues closed after the "since" date
            repo_issues = [
                issue for issue in repo_issues
                if issue.closed_at
                and self.since_dates[i]
                and self.since_dates[i] < issue.closed_at.replace(tzinfo=None)
            ]

            issue_list.append(repo_issues)

        return issue_list

    def get_specific_issues(self):
        """Fetch explicitly listed issue numbers from each repo."""
        issue_list = []
        for i in range(self.args_length):
            repo_issues = [
                self.repos[i].get_issue(int(num))
                for num in self.specific_issues
            ]
            issue_list.append(repo_issues)
        return issue_list

    # ── Excel writing ────────────────────────────────────────────────────

    def write_to_sheet(self):
        """Write fetched issues into an Excel workbook with QA test-step formatting."""
        wb = xlsxwriter.Workbook(f"{self.workbook_name}.xlsx")
        header_format = wb.add_format({"bold": True, "bg_color": HEADER_BG_COLOR})
        header_format.set_text_wrap()

        # Decide which fetcher to use
        fetch_func = self.get_specific_issues if self.specific_issues else self.get_issues
        self.issue_list = fetch_func()

        for sheet_idx in range(self.args_length):
            chunked_issues = list(
                _chunks(self.issue_list[sheet_idx], self.num_rows)
            )

            for chunk_idx, issue_chunk in enumerate(chunked_issues):
                sheet_label = f"{self.sheet_names[sheet_idx]} #{chunk_idx + 1}"
                ws = wb.add_worksheet(sheet_label)

                if self.tab_colors:
                    ws.set_tab_color(self.tab_colors[sheet_idx])

                # Column widths
                ws.set_column(1, 1, 70)   # Title
                ws.set_column(3, 3, 30)   # Tester
                ws.set_column(5, 6, 40)   # Test Steps / Validation
                ws.set_column(8, 8, 18)   # Automation Status

                row = 0
                for issue_num, issue in enumerate(issue_chunk):
                    row = self._write_issue_block(
                        ws, row, issue_num, issue, header_format
                    )

                # Summary formulas at the bottom
                row += 1
                ws.write(row, 1, "Total Tested Issues")
                ws.write(row, 2, "Total Issues")
                row += 1
                ws.write_formula(
                    row, 1,
                    '=SUMPRODUCT((D2:D1000<>"")*(D1:D999="Tester:"))',
                )
                ws.write_formula(
                    row, 2,
                    '=SUMPRODUCT((1)*(D1:D999="Tester:"))',
                )

        wb.close()

    def _write_issue_block(self, ws, row, issue_num, issue, header_format):
        """Write a single issue's header and parsed repro steps. Returns the next row."""
        # Header row
        for col in range(1, 8):
            ws.write(row, col, "", header_format)

        ws.write_url(
            row, 1, issue.html_url, header_format,
            string=f"#{issue.number} {issue.title}",
        )
        ws.write(row, 3, "Tester:", header_format)
        ws.write(row, 8, "Automation Status:", header_format)
        row += 1

        # Sub-header row
        ws.write(row, 0, issue_num + 1)
        ws.write(row, 2, "TC: Detail")
        ws.write(row, 4, "Step #:")
        ws.write(row, 5, "Test Steps:")
        ws.write(row, 6, "Validation:")
        ws.write(row, 7, "Status (Pass/Fail/Blocked)")
        ws.write(row, 8, "Issue #")

        # Parse repro steps from the issue body
        repro_lines = _parse_repro_lines(issue.body) if issue.body else []

        if repro_lines:
            row += 1
            ws.write(row, 5, "These steps were autogenerated!")
            row += 1
        else:
            row += 3

        step_num = 1
        for line in repro_lines:
            is_step = (
                STEP_PATTERN.match(line)
                or BULLET_PATTERN.match(line)
                or PAREN_NUM_PATTERN.match(line)
            )
            is_validation = (
                ARROW_PATTERN.match(line)
                or ARROW_PATTERN_NO_INDENT.match(line)
            )

            if is_step:
                cleaned = _clean_step_text(line)
                ws.write(row, 5, cleaned)
                ws.write(row, 4, step_num)
                step_num += 1
                row += 1

            if is_validation:
                validation_text = re.sub(r"-+>\s*", "", line)
                ws.write(row - 1, 6, validation_text)

        row += 1
        return row

    # ── Post-processing report ───────────────────────────────────────────

    def post_process(self):
        """Categorize skipped issues and write a summary markdown report."""
        MIN_DATE = "May 2nd, 2025"

        all_repos = set(self.repos)
        all_issues = {issue for group in self.issue_list for issue in group}

        # Gather all issues since MIN_DATE that we didn't already include
        skipped_issues = []
        for repo in all_repos:
            skipped_issues.extend(repo.get_issues(state="all", since=parse(MIN_DATE)))

        skipped_issues = [
            issue for issue in skipped_issues
            if not issue.pull_request and issue not in all_issues
        ]

        # Categorize skipped issues by label / state
        categories = {
            "Automated": [],
            "WontFix": [],
            "Duplicate": [],
            "Server": [],
            "Verified": [],
            "Marked for a different release": [],
            "Still open": [],
            "Other": [],
        }

        for issue in skipped_issues:
            labels = [l.name.lower() for l in issue.labels]

            if "automated" in labels:
                categories["Automated"].append(issue)
            elif "wontfix" in labels:
                categories["WontFix"].append(issue)
            elif "duplicate" in labels:
                categories["Duplicate"].append(issue)
            elif "server" in labels:
                categories["Server"].append(issue)
            elif issue.milestone and issue.milestone not in self.milestones:
                categories["Marked for a different release"].append(issue)
            elif not issue.closed_at:
                categories["Still open"].append(issue)
            else:
                categories["Other"].append(issue)

        # Write report
        print(f"Issue List len: {len(all_issues)}")

        with open("x.md", "w") as f:
            for category_name, issues in categories.items():
                _write_md_section(f, category_name, issues)


# ── Helper functions ─────────────────────────────────────────────────────────

def _chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def _parse_repro_lines(body):
    """Extract numbered steps, bullets, and validation arrows from an issue body."""
    lines = []
    for line in body.split("\n"):
        cleaned = line.replace("\r", "")
        if not cleaned:
            continue
        if (
            STEP_PATTERN.match(cleaned)
            or ARROW_PATTERN.match(cleaned)
            or ARROW_PATTERN_NO_INDENT.match(cleaned)
            or BULLET_PATTERN.match(cleaned)
            or PAREN_NUM_PATTERN.match(cleaned)
        ):
            lines.append(cleaned)
    return lines


def _clean_step_text(text):
    """Strip leading numbering, bullets, and markdown links from a repro step."""
    text = re.sub(r"^\d+\s*\.", "", text)
    text = re.sub(r"^\*\s*", "", text)
    text = re.sub(r"^\(\d+\)\s*", "", text)
    text = LINK_PATTERN.sub(r"\1", text)
    return text


def _write_md_section(f, heading, issues):
    """Write a titled section of issue links to a markdown file."""
    f.write(f"{heading}: {len(issues)}\n\n\n")
    for issue in issues:
        f.write(f"[#{issue.number} {issue.title}]({issue.html_url})\n\n")


# ── CLI entry point ──────────────────────────────────────────────────────────

def build_arg_parser():
    """Configure and return the argument parser."""
    parser = argparse.ArgumentParser(
        description="IssueWriter: From Issues to Sheets"
    )

    parser.add_argument(
        "-al", "--aLabel",
        help="Labels to include. Issues must have ALL listed labels.",
        nargs="*",
        action="append",
        default=[],
    )
    parser.add_argument(
        "-el", "--eLabel",
        help="Labels to exclude. Issues with ANY listed label are removed.",
        nargs="*",
        action="append",
        default=[],
    )
    parser.add_argument(
        "-m", "--milestoneNum",
        help="Milestone number to filter by.",
        nargs="*",
        action="append",
        default=[],
    )
    parser.add_argument(
        "-d", "--date",
        help="Only include issues closed AFTER this date.",
        nargs="*",
        action="append",
    )
    parser.add_argument(
        "-r", "--repo",
        help="Repository name (under the Vantiq org) to pull issues from.",
        required=True,
        action="append",
    )
    parser.add_argument(
        "-si", "--specificIssues",
        help="Specific issue numbers to fetch, ignoring other filters.",
        nargs="*",
        default=[],
    )
    parser.add_argument(
        "-n", "--sheetNum",
        help="Number of issues per sheet.",
        type=int,
        default=DEFAULT_ROWS_PER_SHEET,
    )
    parser.add_argument(
        "-sn", "--sheetName",
        help="Name(s) for the worksheet tabs.",
        action="append",
    )
    parser.add_argument(
        "-wn", "--workbookName",
        help="Output workbook filename (without extension).",
    )
    parser.add_argument(
        "-tc", "--tabColor",
        help="Tab color as a name or hex code (e.g. #FF9900).",
        action="append",
    )

    return parser


if __name__ == "__main__":
    parser = build_arg_parser()
    args = vars(parser.parse_args())

    workbook = IssueWorkbook(**args)
    print("Making sheet")
    workbook.write_to_sheet()
    workbook.post_process()

# TODO: Add color
