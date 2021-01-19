### Setup

To use issue writer, simply make a `config.py` file in the same directory and add a string varible `TOKEN` with your github token. Visit [here](https://docs.github.com/en/free-pro-team@latest/github/authenticating-to-github/creating-a-personal-access-token) to set up an access token. 

You will also need to install PyGithub with `pip install PyGithub`, XlsxWriter with `pip install XlsxWriter`, and dateutil with `pip install python-dateutil`

### Running issueWriter

When run, the issueWriter should ask you to select a repo by number out of your existing repos. It will then ask you for a label to filter by (usually bug) and a label to exclude (usually verified). It will then write all of the issues to an xlsx file called "issueSheet".

## Version

This must be run on python 3.8 or above, because I used the Walrus operator.

## Other Issues

There is no way for xlsxwriter to set a cell to autofill with text, so after the sheet is created you will have to change that formatting yourself, globally.


### Running IssueWriter

Run issueWriter2.0.py with `python issueWriter2.0.py`.

It will first ask for the name of the workbook. This is the name of the file in general. It will automatically make this a .xlxs file.

Next it will ask for a repo. It will list all of the repos that you have access to with your github account. Like every other menu in the CLI, select the repository you want with the index of that repository.

Next, you will be given the option menu:

0. *Add a Label* - Adds a label to filter by. If you add more than one label to filter by, it will search for all of the issues with BOTH labels.
1. *Exclude a Label* - Adds a label to exclude. If you add more than on label, it will remove all issues with ANY of the given labels.
2. *Add a Milestone* - Adds a milestone to filter by. There can only be one milestone selected at a time. It will cause only issues from that milestone to be fetched.
3. *Specify Date* - Specifies the "since" parameter. Only issues that were created AFTER the given date will be written.
4. *Change Repo* - Change the current repository. Resets all other settings to the defaults. 
5. *Change Number of Issues per Sheet* - Allows you to change the number of issues per sheet. Defaults to 30.
6. *Show Current Settings* - Prints current settings.
7. *Reset to Default Settings* - Resets to default settings, including repository. Does not change the workbook name.
8. *Write to Sheet* - Writes all issues that match current settings to a given sheet.
9. *Exit* - Exits the program and closes the workbook.