### Setup

To use issue writer, simply make a `config.py` file in the same directory and add a string varible `TOKEN` with your github token. Visit [here](https://docs.github.com/en/free-pro-team@latest/github/authenticating-to-github/creating-a-personal-access-token) to set up an access token. 

You will also need to install PyGithub with `pip install PyGithub`, XlsxWriter with `pip install XlsxWriter`, and dateutil with `pip install python-dateutil`

### Running issueWriter

IssueWriter functions off command line arguments. The only required parameter is repository, but it is highly
recommended that you specify some labels, or else you may end up with far more issues than you may have expected.
To see the full list, run `issueWriter.py --help` or `issueWriter.py -h` for short.

```python
usage: issueWriter.py [-h] [-al ALABEL [ALABEL ...]] [-el ELABEL [ELABEL ...]]
                      [-m MILESTONENUM] [-d DATE [DATE ...]] -r REPO
                      [-n SHEETNUM] [-sn SHEETNAME] [-wn WORKBOOKNAME]

IssueWriter: From Issues to Sheets

optional arguments:
  -h, --help            show this help message and exit
  -al ALABEL [ALABEL ...], --aLabel ALABEL [ALABEL ...]
                        List of labels to include. If more than one label is
                        specified, the program will find issues with ALL
                        labels.
  -el ELABEL [ELABEL ...], --eLabel ELABEL [ELABEL ...]
                        List of labels to exclude. If more than one label is
                        specified, the program will find issues with NONE of
                        the labels
  -m MILESTONENUM, --milestoneNum MILESTONENUM
                        Number of milestone to filter with. 1.32 Maintenance =
                        10 1.33 Maintenance = 11 Release 1.34 = 12
  -d DATE [DATE ...], --date DATE [DATE ...]
                        Datetime object to act as deadline. Will get all
                        issues created, edited, or commented on AFTER the
                        datetime object
  -r REPO, --repo REPO  Repository from which issues are pulled
  -n SHEETNUM, --sheetNum SHEETNUM
                        The number of issues per sheet
  -sn SHEETNAME, --sheetName SHEETNAME
                        The name for the sheets in the Workbook
  -wn WORKBOOKNAME, --workbookName WORKBOOKNAME
                        The name for workbook. (Full File)
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

## Previous Commands to Generate Full Test Run List
```py
# Get all of the iqtools bugs from the 1.34 Milestone
python issueWriter.py -sn "1.34 Milestone Bugs" -r iqtools -wn "milestone1.34_bugs"  -al bug -el wontfix -m 12 -tc "#f4b084"

# Get all of the iqtools bugs from the 1.33 Maint Milestone
python issueWriter.py -sn "1.33 Maint Bugs" -r iqtools -wn "maint1.33_bugs"  -al bug -el wontfix -m 11 -tc "#f4b084"

# Get all of the iqtools enhancements that are not marked as bugs from the 1.34 Milestone
python issueWriter.py -sn "1.34 Milestone Features" -r iqtools -wn "milestone1.34_features"  -al enhancement -el wontfix bug -m 12 -tc "#c6e0b4"

# Get all of the iqtools enhancements that are not marked as bugs from the 1.33 Maint Milestone
python issueWriter.py -sn "1.33 Maint Features" -r iqtools -wn "maint1.33_features"  -al enhancement -el wontfix bug -m 11 -tc "#c6e0b4"

# Get all of the vantiq-issues bugs from the 1.34 Milestone
python issueWriter.py -sn "VI 1.34 Milestone Bugs" -r vantiq-issues -wn "vi_milestone1.34_bugs"  -al bug -el wontfix -m 12 -tc "#f4b084"

# Get all of the vantiq-issues bugs from the 1.33 Maint Milestone
python issueWriter.py -sn "VI 1.33 Maint Bugs" -r vantiq-issues -wn "vi_maint1.33_bugs"  -al bug -el wontfix -m 11 -tc "#f4b084"

# Get all of the vantiq-issues enhancements that are not marked as bugs from the 1.34 Milestone
python issueWriter.py -sn "VI 1.34 Milestone Features" -r vantiq-issues -wn "vi_milestone1.34_features"  -al enhancement -el wontfix bug -m 12 -tc "#c6e0b4"

# Get all of the vantiq-issues enhancements that are not marked as bugs from the 1.33 Maint Milestone
python issueWriter.py -sn "VI 1.33 Maint Features" -r vantiq-issues -wn "vi_maint1.33_features"  -al enhancement -el wontfix bug -m 11 -tc "#c6e0b4"

```


## Version

This must be run on python 3.8 or above, because I used the Walrus operator.

## Other Issues

The automatic import of test steps only works if you have marked them with numbers or bullet points. Links are
not imported.

## Feedback

If any Vantiq employee has any questions or comments, feel free to either drop me an email at sackerman@vantiq.com
or open an issue on this repository. I will respond in a timely manner.