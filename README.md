###Setup

To use issue writer, simply make a `config.py` file in the same directory and add a string varible `TOKEN` with your github token. Visit [here](https://docs.github.com/en/free-pro-team@latest/github/authenticating-to-github/creating-a-personal-access-token) to set up an access token. 

###Running issueWriter

When run, the issueWriter should ask you to select a repo by number out of your existing repos. It will then ask you for a label to filter by (usually bug) and a label to exclude (usually verified). It will then write all of the issues to an xlsx file called "issueSheet".

##Version

This must be run on python 3.8 or above, because I used the Walrus operator.

##Other Issues

There is no way for xlsxwriter to set a cell to autofill with text, so after the sheet is created you will have to change that formatting yourself, globally.