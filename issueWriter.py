import argparse

from config import TOKEN
from github import Github
from datetime import datetime, timedelta, timezone
from dateutil.parser import parse
import github.GithubObject
import xlsxwriter

# If you use TFA you need to auth using an access token instead of username/password
g = Github(TOKEN)
# Init a WorkBook

class wbMain():
	g = Github(TOKEN)
	#Init class, set everything to NotSet
	def __init__(self, aLabel, eLabel, milestoneNum, date, repo, sheetNum, sheetName, workbookName):
		self.iLabelList = aLabel
		self.eLabelList = eLabel
		self.repo = g.get_repo(f'Vantiq/{repo}')
		self.milestone = self.repo.get_milestone(milestoneNum) if milestoneNum else github.GithubObject.NotSet
		self.since = parse(' '.join(date)) if date else github.GithubObject.NotSet
		self.numRows = 30
		self.sheetName = f'{" ".join(self.iLabelList)} Issues' if not sheetName else sheetName

	def getIssues(self):
		# First get all of the issues that fit the criteria
		issueList = list(self.repo.get_issues(state='all', labels=self.iLabelList, milestone=self.milestone, since=self.since, direction='asc'))
		for label in self.eLabelList:
			issueList = [i for i in issueList if label not in [l.name for l in i.labels]]
		return issueList

	def writeToSheet(self):
		# Helper function to split the list into chunks
		def chunks(lst, n):
			for i in range(0, len(lst), n):
				yield lst[i:i + n]
		# Get all of the issues with the given states
		issueList = self.getIssues()
		# Split the issueList into chunks
		issueList = list(chunks(issueList, self.numRows))
		for idx, subList in enumerate(issueList):
			ws = wb.add_worksheet(self.sheetName+'_'+str(idx))
			for i in range(0, len(subList)*3, 3):
				# Format the top row
				for j in range(1, 8):
					ws.write(i, j, '', cell_format)
				# Write the issue number and issue title, and link the text back to the original issue
				ws.write_url(i, 1, subList[int(i/3)].html_url, cell_format, string='#{} {}'.format(subList[int(i/3)].number, subList[int(i/3)].title))
				ws.write(i, 3, 'Tester:', cell_format)
				ws.write(i, 8, 'Automation Status:', cell_format)
				# Write the bug number
				ws.write(i+1, 0, i/3+1)
				ws.write(i+1, 2, 'TC: Detail')
				ws.write(i+1, 3, 'Step #:')
				ws.write(i+1, 4, 'Test Steps:')
				ws.write(i+1, 5, 'Validation:')
				ws.write(i+1, 6, 'Stats (Pass/Fail/Blocked)')
				ws.write(i+1, 7, 'Issue #')


parser = argparse.ArgumentParser(description='IssueWriter: From Issues to Sheets')

parser.add_argument('-al','--aLabel', help="""List of labels to include. If more than one label is specified, the program will
	find issues with ALL labels.""", nargs='+', default=github.GithubObject.NotSet)

parser.add_argument('-el','--eLabel', help="""List of labels to exclude. If more than one label is specified, the program will
	find issues with NONE of the labels""", nargs='+', default=[])

parser.add_argument('-m','--milestoneNum', help="""Number of milestone to filter with.\n
	1.32 Maintenance = 10\n
	1.33 Maintenance = 11\n
	Release 1.34 = 12""", type=int, default=0)

parser.add_argument('-d','--date', help="""Datetime object to act as deadline. Will get all issues created, edited, 
	or commented on AFTER the datetime object""", nargs='+', default=[])

parser.add_argument('-r','--repo', help='Repository from which issues are pulled', required=True)

parser.add_argument('-n', '--sheetNum', help='The number of issues per sheet', type=int, default=30)

parser.add_argument('-sn', '--sheetName', help='The name for the sheets in the Workbook')

parser.add_argument('-wn', '--workbookName', help='The name for workbook. (Full File)')

args = vars(parser.parse_args())
wbName = args['workbookName']

wb = xlsxwriter.Workbook(f'{wbName}.xlsx')
cell_format = wb.add_format({'bold': True, 'bg_color': '#d7dbd8'})
newWb = wbMain(**args)
newWb.writeToSheet()
wb.close()

# TODO:
# Show the current settings (TOUCHUP)