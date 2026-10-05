### Setup

To use issue writer, simply make a `config.py` file in the same directory and add a string varible `TOKEN` with your github token. Visit [here](https://docs.github.com/en/free-pro-team@latest/github/authenticating-to-github/creating-a-personal-access-token) to set up an access token. 

You will also need to install PyGithub with `pip install PyGithub`, XlsxWriter with `pip install XlsxWriter`, and dateutil with `pip install python-dateutil`

### Running issueWriter

IssueWriter functions off command line arguments. The only required parameter is repository, but it is highly
recommended that you specify some labels, or else you may end up with far more issues than you may have expected.
To see the full list, run `issueWriter.py --help` or `issueWriter.py -h` for short.

```python
usage: issueWriter.py [-h] [-al [ALABEL [ALABEL ...]]]
                      [-el [ELABEL [ELABEL ...]]]
                      [-m [MILESTONENUM [MILESTONENUM ...]]]
                      [-d [DATE [DATE ...]]] -r REPO
                      [-si [SPECIFICISSUES [SPECIFICISSUES ...]]]
                      [-n SHEETNUM] [-sn SHEETNAME] [-wn WORKBOOKNAME]
                      [-tc TABCOLOR]

IssueWriter: From Issues to Sheets

optional arguments:
  -h, --help            show this help message and exit
  -al [ALABEL [ALABEL ...]], --aLabel [ALABEL [ALABEL ...]]
                        List of labels to include. If more than one label is
                        specified, the program will find issues with ALL
                        labels.
  -el [ELABEL [ELABEL ...]], --eLabel [ELABEL [ELABEL ...]]
                        List of labels to exclude. If more than one label is
                        specified, the program will find issues with NONE of
                        the labels
  -m [MILESTONENUM [MILESTONENUM ...]], --milestoneNum [MILESTONENUM [MILESTONENUM ...]]
                        Number of milestone to filter with. 1.32 Maintenance =
                        10 1.33 Maintenance = 11 Release 1.34 = 12
  -d [DATE [DATE ...]], --date [DATE [DATE ...]]
                        Datetime object to act as deadline. Will get all
                        issues closed AFTER the date provided
  -r REPO, --repo REPO  Repository from which issues are pulled
  -si [SPECIFICISSUES [SPECIFICISSUES ...]], --specificIssues [SPECIFICISSUES [SPECIFICISSUES ...]]
                        List of specific issues for a given Repository. If
                        provided, will return sheet with given issues,
                        regardless of other parameters entered.
  -n SHEETNUM, --sheetNum SHEETNUM
                        The number of issues per sheet
  -sn SHEETNAME, --sheetName SHEETNAME
                        The name for the sheets in the Workbook
  -wn WORKBOOKNAME, --workbookName WORKBOOKNAME
                        The name for workbook. (Full File)
  -tc TABCOLOR, --tabColor TABCOLOR
                        Color for the created tabs. Can be a string or or HEX.
                        (#FF9900)
```

Most of these are pretty self-explanatory. The only tricky one is milestones, which have to be passed in as numbers.
Luckily, we only have a few milestones, so I just kept track of their numbers in the help message.

Additionally, you may be wondering what format to enter the "date" arg. The answer is, pretty much anything you like.
The code is set up to parse datetime from any String, and almost only gets confused when deliberately messed with. 
Here are some example commands;

If you want to make a workbook called "allBugs" which contains all bugs from the iqtools repository.

`issueWriter.py -r iqtools -wn allBugs -al bug`

If you wanted to make a workbook containing all the bugs that need automation from last March 
to the present, but not if they're already automated.

`issueWriter.py -r iqtools -al needsautomation bug -el automated -date March 1st 2022`

If you wanted all the High Priority Enhancements from the Release 1.34 milestone.

`issueWriter.py -r iqtools -al enchancement "High Priority" -m 12`

And so on.

Additionally, you can run the command with multiple copies of the same arg to make multiple sheets.
However, if you do this, you need to have the same number of each argument, so the program can create
the sheets in order.

## Previous Command to Generate Full Test Run List

To create a full 1.34 UI Test sheet in one command, run the allsheets.sh file in this repository. 
It runs a single unholy command to create everything we need.


## Optional AI features (`--ai-steps`, `--ai-triage`)

Two optional steps use Claude through the **Claude Code CLI** in non-interactive mode
(`claude -p`). They authenticate with your Claude.ai subscription, so runs count against
your subscription's rate limit rather than pay-per-token API billing.

Setup (one time):

1. Install the CLI. The Claude Code desktop app does **not** put `claude` on PATH.
   In PowerShell: `irm https://claude.ai/install.ps1 | iex`
2. Run `claude auth login` once.
3. `gh` must be installed and logged in (`gh auth status`) for `--ai-triage`.

Flags (also available as `aiSteps`, `aiTriage`, `aiModel` in a JSON config):

| Flag | What it does |
| --- | --- |
| `--ai-steps` | Numbered steps / bullets the regex parser finds are first **verified** by Claude to be real test steps (feature checklists, file lists and the like are rejected and treated as if nothing was found). When nothing usable is found, Claude **extracts** steps written in prose or **infers** plausible steps from the title, body, comments and linked PRs. Expected results are written only on the steps that check something, not on setup steps. Rows are marked `AI-extracted` or `AI-INFERRED` so testers know to verify them. If the change has no UI surface (refactor, tooling, server-only), the step area instead reads `NOT MANUALLY TESTABLE` with the reason, and Status is left for the tester to mark N/A. If the issue text gives the model nothing to work with, it reads `AI found no usable steps` so you can tell an attempted issue from an unattempted one. |
| `--ai-triage` | For issues that land in the `Other` or `Unlabeled in tracked milestone` buckets of `x.md`, ask Claude whether they belong in the sheet (`INCLUDE`), are missing a label (`NEEDS_LABEL`), or are correctly excluded. Claude may run read-only `gh issue view` / `gh pr view` / `gh pr diff` to inspect linked PRs. Verdicts are written under each issue in `x.md`. |
| `--ai-model MODEL` | Model alias or ID for `claude --model` (e.g. `sonnet`). Defaults to the CLI's default. |

### Manual overrides (config file only)

* Per sheet, `"addIssues": [1276]` forces those issue numbers onto that sheet even if they match no filter
  (e.g. an issue that should have had the milestone but doesn't).
* Top level, `"excludeIssues": ["iqtools#10683"]` drops repo-qualified issues from every sheet.

Pull requests returned by the issues API are now always skipped.

Results are cached in `ai_cache.json` (keyed by issue number and `updated_at`), so re-running
does not re-pay for unchanged issues. Delete an entry or the file to regenerate.

`x.md` also now has more deterministic buckets (`Verified`, `Invalid`, `No milestone`,
`Closed before date cutoff`, `Label clash`, `Unlabeled in tracked milestone`) so that `Other`
only holds issues that genuinely need a judgment call.

## Version

This must be run on python 3.8 or above, because I used the Walrus operator.

## Other Issues

The automatic import of test steps only works if you have marked them with numbers or bullet points. Links are
not imported.

## Feedback

If any Vantiq employee has any questions or comments, feel free to either drop me an email at sackerman@vantiq.com
or open an issue on this repository. I will respond in a timely manner, if possible.