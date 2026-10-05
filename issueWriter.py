import argparse
import json
import os
import re

import github.Auth
import github.GithubObject
import xlsxwriter

from config import TOKEN
from datetime import datetime, date as dt
from dateutil.parser import parse
from github import Github

import ai_features
from claude_cli import (
    AiCache,
    ClaudeCliError,
    add_usage,
    empty_usage,
    find_claude,
    format_usage,
    install_hint,
)

# ── Constants ────────────────────────────────────────────────────────────────

DEFAULT_ROWS_PER_SHEET = 30
HEADER_BG_COLOR = "#d7dbd8"
AI_CACHE_PATH = "ai_cache.json"

# Sentinel used when a sheet has no --date: "include everything ever closed".
NO_DATE = datetime(dt.min.year, dt.min.month, dt.min.day)

# Post-processing buckets that get sent to the LLM for triage when --ai-triage is on.
AI_TRIAGE_CATEGORIES = ("Other", "Unlabeled in tracked milestone")

# Regex patterns for parsing issue body text
STEP_PATTERN = re.compile(r"^\d+\.")
BULLET_PATTERN = re.compile(r"^\*")
PAREN_NUM_PATTERN = re.compile(r"^\(\d+\)\s*")
ARROW_PATTERN = re.compile(r"^\s*-+>")
ARROW_PATTERN_NO_INDENT = re.compile(r"^-+>")
LINK_PATTERN = re.compile(r"\[(.*)\]\((.*)\)")

# Authenticate once at module level. per_page=100 cuts the number of list
# requests by ~3x; post_process alone pages through ~1000 issues.
g = Github(auth=github.Auth.Token(TOKEN), per_page=100)


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
        aiSteps=False,
        aiTriage=False,
        aiModel=None,
        addIssues=None,
        excludeIssues=None,
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
            parse(" ".join(d)) if d else NO_DATE
            for d in date
        ]

        self.num_rows = sheetNum if sheetNum else DEFAULT_ROWS_PER_SHEET
        self.sheet_names = sheetName if sheetName else [f'{" ".join(labels)} Issues' for labels in self.include_labels]
        self.tab_colors = tabColor
        self.specific_issues = specificIssues
        self.workbook_name = workbookName

        self.args_length = len(self.repos)
        self.issue_list = []

        # Manual overrides (config only). addIssues: per-sheet list of issue
        # numbers to force onto that sheet regardless of filters. excludeIssues:
        # repo-qualified "repo#number" strings dropped from every sheet.
        self.add_issues = [list(a) if a else [] for a in (addIssues or [[] for _ in self.repos])]
        self.exclude_issues = set()
        for item in excludeIssues or []:
            repo_name, _, num = str(item).partition("#")
            if not num.isdigit():
                raise ValueError(f"excludeIssues entries must look like 'iqtools#1234', got {item!r}")
            self.exclude_issues.add((f"Vantiq/{repo_name}", int(num)))

        # ── Optional LLM features (run through the `claude` CLI) ──
        self.ai_steps = bool(aiSteps)
        self.ai_triage = bool(aiTriage)
        self.ai_model = aiModel
        self.ai_cost = 0.0
        self.ai_usage = empty_usage()
        self.claude_exe = None
        self.ai_cache = None
        if self.ai_steps or self.ai_triage:
            self.claude_exe = find_claude()
            if not self.claude_exe:
                raise SystemExit(install_hint())
            self.ai_cache = AiCache(AI_CACHE_PATH)
            print(f"AI features enabled via {self.claude_exe}")

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

            # The issues API also returns pull requests; the test suite is
            # issues only. (post_process already filtered these.)
            repo_issues = [issue for issue in repo_issues if not issue.pull_request]

            # Manual overrides
            repo_name = self.repos[i].full_name
            repo_issues = [
                issue for issue in repo_issues
                if (repo_name, issue.number) not in self.exclude_issues
            ]
            present = {issue.number for issue in repo_issues}
            for num in self.add_issues[i]:
                if int(num) not in present and (repo_name, int(num)) not in self.exclude_issues:
                    repo_issues.append(self.repos[i].get_issue(int(num)))
                    present.add(int(num))

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
        out_path = f"{self.workbook_name}.xlsx"
        _ensure_writable(out_path)
        wb = xlsxwriter.Workbook(out_path)
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
        marker = "These steps were autogenerated!"
        note = None

        # With AI on: regex hits are verified as real test steps (lists of
        # features, files, etc. are rejected); regex misses get generated steps.
        if self.ai_steps:
            repro_lines, marker, note = self._ai_repro_lines(issue, repro_lines, marker)

        if repro_lines:
            row += 1
            ws.write(row, 5, marker)
            row += 1
        elif note:
            # No steps: either the change has no UI surface, or the issue text
            # gave the model nothing to work with. Say which where the steps
            # would have gone; leave Status for the tester to fill.
            row += 1
            ws.write(row, 5, marker)
            ws.write(row, 6, note)
            row += 2
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

    def _ai_repro_lines(self, issue, detected_lines, detected_marker):
        """Ask Claude to verify regex-detected steps, or write steps if there are none.

        Returns (lines, marker, note). When no steps come back, `marker` says
        whether the issue was judged not manually testable or simply had no
        usable information, and `note` carries the model's one-line reason.
        On CLI failure, falls back to the regex result unchanged.
        """
        try:
            result = ai_features.generate_repro_steps(
                issue,
                cache=self.ai_cache,
                model=self.ai_model,
                executable=self.claude_exe,
                detected_lines=detected_lines,
            )
        except ClaudeCliError as e:
            print(f"  AI steps FAILED for #{issue.number}: {e}")
            return detected_lines, detected_marker, None

        self.ai_cost += result["cost"]
        add_usage(self.ai_usage, result["usage"])
        print(f"  AI steps for #{issue.number}: {result['mode']}")
        return result["lines"], result["marker"], result.get("note")

    # ── Post-processing report ───────────────────────────────────────────

    def _repo_rules(self):
        """Per-repo view of the sheet rules: tracked milestone numbers and date cutoff.

        cutoff is None when any sheet for that repo has no --date (meaning
        issues closed at any time were eligible), otherwise the earliest date.
        """
        rules = {}
        for i, repo in enumerate(self.repos):
            info = rules.setdefault(
                repo.full_name,
                {"repo": repo, "milestones": set(), "cutoff": None, "undated": False},
            )
            ms = self.milestones[i]
            if ms is not github.GithubObject.NotSet:
                info["milestones"].add(ms.number)
            since = self.since_dates[i]
            if since == NO_DATE:
                info["undated"] = True
            elif info["cutoff"] is None or since < info["cutoff"]:
                info["cutoff"] = since
        for info in rules.values():
            if info["undated"]:
                info["cutoff"] = None
        return rules

    def post_process(self):
        """Categorize skipped issues and write a summary markdown report."""
        MIN_DATE = "May 2nd, 2025"

        rules = self._repo_rules()

        included = {
            (self.repos[i].full_name, issue.number)
            for i, group in enumerate(self.issue_list)
            for issue in group
        }

        # Gather all issues updated since MIN_DATE that we didn't already include.
        # Note: GitHub's `since` means "updated since", not "closed since".
        skipped = []  # list of (repo_full_name, issue)
        for full_name, info in rules.items():
            for issue in info["repo"].get_issues(state="all", since=parse(MIN_DATE)):
                if issue.pull_request:
                    continue
                if (full_name, issue.number) in included:
                    continue
                skipped.append((full_name, issue))

        # Categorize skipped issues. Order matters: first match wins.
        categories = {
            "Automated": [],
            "WontFix": [],
            "Duplicate": [],
            "Invalid": [],
            "Server": [],
            "Verified": [],
            "Marked for a different release": [],
            "Still open": [],
            "No milestone": [],
            "Closed before date cutoff": [],
            "Label clash (enhancement + bug)": [],
            "Unlabeled in tracked milestone": [],
            "Other": [],
        }

        for full_name, issue in skipped:
            labels = {l.name.lower() for l in issue.labels}
            info = rules[full_name]
            in_tracked_ms = bool(
                issue.milestone and issue.milestone.number in info["milestones"]
            )
            closed_at = issue.closed_at.replace(tzinfo=None) if issue.closed_at else None

            if "automated" in labels:
                categories["Automated"].append(issue)
            elif "wontfix" in labels:
                categories["WontFix"].append(issue)
            elif "duplicate" in labels:
                categories["Duplicate"].append(issue)
            elif "invalid" in labels:
                categories["Invalid"].append(issue)
            elif "server" in labels:
                categories["Server"].append(issue)
            elif "verified" in labels:
                categories["Verified"].append(issue)
            elif issue.milestone and not in_tracked_ms:
                categories["Marked for a different release"].append(issue)
            elif not closed_at:
                categories["Still open"].append(issue)
            elif not issue.milestone:
                categories["No milestone"].append(issue)
            elif info["cutoff"] is not None and closed_at <= info["cutoff"]:
                categories["Closed before date cutoff"].append(issue)
            elif {"enhancement", "bug"} <= labels:
                categories["Label clash (enhancement + bug)"].append(issue)
            elif not labels:
                categories["Unlabeled in tracked milestone"].append(issue)
            else:
                categories["Other"].append(issue)

        # Optional LLM triage of the buckets that need a judgment call
        verdicts = {}
        if self.ai_triage:
            verdicts = self._ai_triage(categories)

        # Write report
        print(f"Issue List len: {len(included)}")
        for name, issues in categories.items():
            print(f"  {name}: {len(issues)}")
        if self.ai_steps or self.ai_triage:
            print("AI usage this run (cached results cost nothing):")
            print(format_usage(self.ai_usage, self.ai_cost))

        with open("x.md", "w", encoding="utf-8") as f:
            for category_name, issues in categories.items():
                _write_md_section(f, category_name, issues, verdicts)

    def _ai_triage(self, categories):
        """Run LLM triage over AI_TRIAGE_CATEGORIES. Returns {(repo, number): verdict}."""
        to_triage = [
            issue
            for name in AI_TRIAGE_CATEGORIES
            for issue in categories.get(name, [])
        ]
        if not to_triage:
            return {}

        sheet_rules_text = ai_features.describe_sheet_rules(self)
        print(f"AI triage: {len(to_triage)} issues")

        verdicts = {}
        for n, issue in enumerate(to_triage, start=1):
            repo_name = ai_features.repo_full_name(issue)
            verdict = ai_features.triage_issue(
                issue,
                sheet_rules_text,
                cache=self.ai_cache,
                model=self.ai_model,
                executable=self.claude_exe,
                cwd=os.getcwd(),
            )
            self.ai_cost += verdict.get("cost", 0.0)
            add_usage(self.ai_usage, verdict.get("usage") or empty_usage())
            verdicts[(repo_name, issue.number)] = verdict
            print(f"  [{n}/{len(to_triage)}] #{issue.number}: {verdict['verdict']}")
        return verdicts


# ── Helper functions ─────────────────────────────────────────────────────────

def _chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def _ensure_writable(path):
    """Fail fast if the output workbook can't be written (usually: open in Excel).

    xlsxwriter only opens the file at close(), i.e. after all fetching and any
    AI calls, so without this check a locked file wastes the whole run.
    """
    if not os.path.exists(path):
        return
    try:
        with open(path, "r+b"):
            pass
    except PermissionError:
        raise SystemExit(
            f"Cannot write {path}: the file is locked, probably open in Excel. "
            "Close it and re-run."
        )


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


def _write_md_section(f, heading, issues, verdicts=None):
    """Write a titled section of issue links to a markdown file.

    `verdicts` is an optional {(repo_full_name, number): verdict} map from AI
    triage; matching issues get a verdict line under their link.
    """
    f.write(f"{heading}: {len(issues)}\n\n\n")

    if verdicts:
        section_verdicts = [
            verdicts[(ai_features.repo_full_name(i), i.number)]
            for i in issues
            if (ai_features.repo_full_name(i), i.number) in verdicts
        ]
        if section_verdicts:
            counts = {}
            for v in section_verdicts:
                counts[v["verdict"]] = counts.get(v["verdict"], 0) + 1
            summary = ", ".join(f"{k}: {n}" for k, n in sorted(counts.items()))
            f.write(f"_AI triage summary: {summary}_\n\n")

    for issue in issues:
        f.write(f"[#{issue.number} {issue.title}]({issue.html_url})\n\n")
        if verdicts:
            v = verdicts.get((ai_features.repo_full_name(issue), issue.number))
            if v:
                f.write(f"  - {ai_features.format_verdict(v)}\n\n")


# ── Config file support ─────────────────────────────────────────────────────

def load_config(config_path):
    """Load a JSON config file and translate it into IssueWorkbook kwargs.

    The config file uses a 'sheets' array where each entry defines a single
    sheet's parameters (repo, labels, milestone, etc.), which is far easier
    to read and maintain than the equivalent CLI invocation.

    Returns a dict suitable for passing to IssueWorkbook(**kwargs).
    """
    with open(config_path, "r") as f:
        cfg = json.load(f)

    sheets = cfg.get("sheets", [])
    if not sheets:
        raise ValueError("Config file must contain a non-empty 'sheets' array.")

    # Build the parallel-list structures that IssueWorkbook expects
    aLabel = []
    eLabel = []
    milestoneNum = []
    date = []
    repo = []
    sheetName = []
    tabColor = []
    addIssues = []

    for sheet in sheets:
        repo.append(sheet["repo"])
        aLabel.append(sheet.get("includeLabels", []))
        eLabel.append(sheet.get("excludeLabels", []))
        addIssues.append([int(n) for n in sheet.get("addIssues", [])])

        # milestoneNum expects a list-of-lists (each inner list has one element)
        ms = sheet.get("milestoneNum")
        milestoneNum.append([str(ms)] if ms is not None else [])

        # date expects a list-of-lists (each inner list is the date string split on spaces)
        d = sheet.get("date")
        date.append(d.split() if d else [])

        sheetName.append(sheet.get("sheetName", ""))
        tabColor.append(sheet.get("tabColor", None))

    # If no tab colors were specified at all, pass None
    if all(tc is None for tc in tabColor):
        tabColor = None

    return {
        "aLabel": aLabel,
        "eLabel": eLabel,
        "milestoneNum": milestoneNum,
        "date": date,
        "repo": repo,
        "sheetNum": cfg.get("sheetNum", DEFAULT_ROWS_PER_SHEET),
        "sheetName": sheetName if any(sheetName) else None,
        "workbookName": cfg.get("workbookName", "output"),
        "tabColor": tabColor,
        "specificIssues": cfg.get("specificIssues", []),
        "aiSteps": bool(cfg.get("aiSteps", False)),
        "aiTriage": bool(cfg.get("aiTriage", False)),
        "aiModel": cfg.get("aiModel"),
        "addIssues": addIssues,
        "excludeIssues": cfg.get("excludeIssues", []),
    }


# ── CLI entry point ──────────────────────────────────────────────────────────

def build_arg_parser():
    """Configure and return the argument parser."""
    parser = argparse.ArgumentParser(
        description="IssueWriter: From Issues to Sheets"
    )

    parser.add_argument(
        "-c", "--config",
        help="Path to a JSON config file. When provided, all other options are ignored.",
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

    # ── Optional LLM features (require the `claude` CLI, billed to your subscription) ──
    parser.add_argument(
        "--ai-steps",
        dest="aiSteps",
        action="store_true",
        help="When an issue has no parseable repro steps, ask Claude to extract or infer them.",
    )
    parser.add_argument(
        "--ai-triage",
        dest="aiTriage",
        action="store_true",
        help="Ask Claude whether issues left in the 'Other' buckets of x.md belong in the sheet.",
    )
    parser.add_argument(
        "--ai-model",
        dest="aiModel",
        help="Model alias or ID passed to `claude --model` (e.g. sonnet, opus). Default: CLI default.",
    )

    return parser


if __name__ == "__main__":
    parser = build_arg_parser()
    args = parser.parse_args()

    if args.config:
        # Config file mode — load everything from JSON. The AI flags are the one
        # exception: passing them on the command line turns them on for this run.
        kwargs = load_config(args.config)
        if args.aiSteps:
            kwargs["aiSteps"] = True
        if args.aiTriage:
            kwargs["aiTriage"] = True
        if args.aiModel:
            kwargs["aiModel"] = args.aiModel
    else:
        # CLI mode — require at least one repo
        if not args.repo:
            parser.error("the following arguments are required: -r/--repo (or use -c/--config)")
        kwargs = vars(args)
        # Remove the config key since IssueWorkbook doesn't expect it
        kwargs.pop("config", None)

    workbook = IssueWorkbook(**kwargs)
    print("Making sheet")
    workbook.write_to_sheet()
    workbook.post_process()

# TODO: Add color
