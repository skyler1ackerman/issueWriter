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


## Version

This must be run on python 3.8 or above, because I used the Walrus operator.

## Other Issues

The automatic import of test steps only works if you have marked them with numbers or bullet points. Links are
not imported.

## Feedback

If any Vantiq employee has any questions or comments, feel free to either drop me an email at sackerman@vantiq.com
or open an issue on this repository. I will respond in a timely manner.