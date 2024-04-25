import argparse, re
import github.GithubObject
import xlsxwriter
import pytz

from config import TOKEN
from github import Github
from datetime import datetime, timedelta, timezone
from datetime import date as dt
from dateutil.parser import parse


# If you use TFA you need to auth using an access token instead of username/password
g = Github(TOKEN)
# Init a WorkBook

class wbMain():
	g = Github(TOKEN)
	#Init class, set everything to NotSet
	def __init__(self, aLabel, eLabel, milestoneNum, date, repo, sheetNum, sheetName, workbookName, tabColor, specificIssues):
		self.iLabelList = [a if a else [] for a in aLabel]
		self.eLabelList = [e if e else [] for e in eLabel]
		self.repo = [g.get_repo(f'Vantiq/{r}') for r in repo]
		self.milestone = [self.repo[idx].get_milestone(int(mn[0])) if mn else github.GithubObject.NotSet for idx, mn in enumerate(milestoneNum)] 
		self.since = [parse(' '.join(d)) if d else datetime(dt.min.year, dt.min.month, dt.min.day) for d in date]
		self.numRows = 30
		self.sheetName = f'{" ".join(self.iLabelList)} Issues' if not sheetName else sheetName
		self.tabColor = tabColor
		self.specificIssues = specificIssues
		self.issueFunc = self.getSpecIssues if specificIssues else self.getIssues
		it = iter([l for l in [self.iLabelList, self.eLabelList, self.repo, self.milestone, self.since, self.sheetName] if l and l != github.GithubObject.NotSet])
		the_len = len(next(it))
		# if not all(len(l) == the_len for l in it):
		# 	raise ValueError('You have not passed in the same number of args for all of the options!')
		self.args_length = the_len
		self.issueList = []

	def getIssues(self):
		issueList = []
		# First get all of the issues that fit the criteria
		for i in range(self.args_length):
			# print(i)
			issueList.append(self.repo[i].get_issues(state='all', milestone=self.milestone[i], direction='asc'))
			# print([i.number for i in issueList[i]])
			# print(f'Initial len: {len(list(issueList[i]))}')
			# Make sure issue is only included if it has all of the "include" labels
			for label in self.iLabelList[i]:
				issueList[i] = [issue for issue in issueList[i] if label in [l.name for l in issue.labels]]
			# print(f'After include len: {len(list(issueList[i]))}')
			# Make sure the issue is NOT included if it has any of the "exclude" labels
			for label in self.eLabelList[i]:
				issueList[i] = [issue for issue in issueList[i] if label not in [l.name for l in issue.labels]]
			# print(f'After Exclude len: {len(list(issueList[i]))}')
			issueList[i] = [issue for issue in issueList[i] if issue.closed_at and self.since[i] and self.since[i] < issue.closed_at.replace(tzinfo=None)]
			# print(f'After since: {len(issueList[i])}')
			# print('\n\n')

		return issueList

	def getSpecIssues(self):
		issueList = []
		for i in range(self.args_length):
			issueList.append([])
			for issueNum in self.specificIssues:
				issueList[i].append(self.repo[i].get_issue(int(issueNum)))
		return issueList

	def writeToSheet(self):
		wb = xlsxwriter.Workbook(f'{wbName}.xlsx')
		cell_format = wb.add_format({'bold': True, 'bg_color': '#d7dbd8'})
		cell_format.set_text_wrap()

		# Helper function to split the list into chunks
		def chunks(lst, n):
			for i in range(0, len(lst), n):
				yield lst[i:i + n]
		# Get all of the issues with the given states
		self.issueList = self.issueFunc()
		for sheetNum in range(self.args_length):
			# Split the issueList into chunks
			curIssueList = list(chunks(self.issueList[sheetNum], self.numRows))
			for idx, subList in enumerate(curIssueList):
				ws = wb.add_worksheet(self.sheetName[sheetNum]+' #'+str(idx+1))
				if self.tabColor:
					ws.set_tab_color(self.tabColor[sheetNum])
				curRow = 0
				ws.set_column(1, 1, 70)
				ws.set_column(3, 3, 30)
				ws.set_column(5, 6, 40)
				ws.set_column(8, 8, 18)
				for i, issue in enumerate(subList):
					# Format the top row
					for j in range(1, 8):
						ws.write(curRow, j, '', cell_format)
					# Write the issue number and issue title, and link the text back to the original issue
					ws.write_url(curRow, 1, issue.html_url, cell_format, string='#{} {}'.format(issue.number, issue.title))
					ws.write(curRow, 3, 'Tester:', cell_format)
					ws.write(curRow, 8, 'Automation Status:', cell_format)
					curRow+=1
					# Write the bug number
					ws.write(curRow, 0, i+1)
					ws.write(curRow, 2, 'TC: Detail')
					ws.write(curRow, 4, 'Step #:')
					ws.write(curRow, 5, 'Test Steps:')
					ws.write(curRow, 6, 'Validation:')
					ws.write(curRow, 7, 'Status (Pass/Fail/Blocked)')
					ws.write(curRow, 8, 'Issue #')
					issueText = []
					if issue.body:
						# Pull all steps marked by numbering or bullet points, as well as validations (--->)
						issueText = [b.replace('\r', '') for b in issue.body.split('\n') if b \
						and(re.match(r'^\d+\.', b) or re.match(r'^\s*-+>', b)
							or re.match(r'^-+>', b) or re.match(r'^\*', b)) or re.match(r'^\(\d+\)\s*', b)]
						curRow+=1
					# If any steps were found, 
					if issueText:
						ws.write(curRow, 5, 'These steps were autogenerated!')
						curRow+=1
					else:
						curRow+=3
					stepNum=1
					for repro_step in issueText:
						# If it starts with a digit, a bullet point, or a digit wrapped in parenthesis, it's a step
						if re.match(r'^\d+\.', repro_step) or re.match(r'^\*', repro_step) or re.match(r'^\(\d+\)', repro_step):
							# Remove any leading digits or bullet points
							repro_step = re.sub(r'^\d+\s*\.', r'', repro_step)
							repro_step = re.sub(r'^\*\s*', '', repro_step)
							repro_step = re.sub(r'^\(\d+\)\s*', '', repro_step)
							# Remove any links
							repro_step = re.sub(r'\[(.*)\]\((.*)\)', '\1', repro_step)
							ws.write(curRow, 5, repro_step)
							ws.write(curRow, 4, stepNum)
							stepNum+=1
							curRow+=1
						if re.match(r'^\s+-+>', repro_step) or re.match(r'^-+>', repro_step):
							# Remove the arrow
							repro_step = re.sub(r'-+>\s*', '', repro_step)
							ws.write(curRow-1, 6, repro_step)
					curRow+=1
				curRow+=1
				ws.write(curRow, 1, 'Total Tested Issues')
				ws.write(curRow, 2, 'Total Issues')
				curRow+=1
				ws.write_formula(curRow, 1, '=SUMPRODUCT((D2:D1000<>"")*(D1:D999="Tester:"))')
				ws.write_formula(curRow, 2, '=SUMPRODUCT((1)*(D1:D999="Tester:"))')
		wb.close()


	def postProcess(self):
		MIN_DATE = 'January 24th, 2024'
		allRepos = set(self.repo)
		allIssues = set()
		for l in self.issueList:
			allIssues.update(set(l))
		skipped_issues = []
		for r in allRepos:
			skipped_issues+=(r.get_issues(state='all', since=parse(MIN_DATE)))

		print(f'Issue List len: {len(allIssues)}')
		skipped_issues = [issue for issue in skipped_issues if not issue.pull_request and issue not in allIssues]
		all_automated = []
		all_wont_fix = []
		all_duplicate = []
		all_verifed = []
		all_open = []
		all_other_release = []
		all_other = []
		for issue in skipped_issues:
			labels = [l.name.lower() for l in issue.labels]
			if 'automated' in labels:
				all_automated.append(issue)
			elif 'wontfix' in labels:
				all_wont_fix.append(issue)
			elif 'duplicate' in labels:
				all_duplicate.append(issue)
			# elif 'verified' in labels:
			# 	all_verifed.append(issue)
			elif issue.milestone and issue.milestone not in self.milestone:
				all_other_release.append(issue)
			elif not issue.closed_at:
				all_open.append(issue)
			else:
				all_other.append(issue)

		with open('x.md', 'w') as f:
			f.write(f'Automated: {len(all_automated)}\n\n\n')
			for issue in all_automated:
				f.write(f'[#{issue.number} {issue.title}]({issue.html_url})\n\n')

			f.write(f'WontFix: {len(all_wont_fix)}\n\n\n')
			for issue in all_wont_fix:
				f.write(f'[#{issue.number} {issue.title}]({issue.html_url})\n\n')

			f.write(f'Duplicate: {len(all_duplicate)}\n\n\n')
			for issue in all_duplicate:
				f.write(f'[#{issue.number} {issue.title}]({issue.html_url})\n\n')

			f.write(f'Verified: {len(all_verifed)}\n\n\n')
			for issue in all_verifed:
				f.write(f'[#{issue.number} {issue.title}]({issue.html_url})\n\n')

			f.write(f'Marked for a different release: {len(all_other_release)}\n\n\n')
			for issue in all_other_release:
				f.write(f'[#{issue.number} {issue.title}]({issue.html_url})\n\n')

			f.write(f'Still open: {len(all_open)}\n\n\n')
			for issue in all_open:
				f.write(f'[#{issue.number} {issue.title}]({issue.html_url})\n\n')

			f.write(f'Other: {len(all_other)}\n\n\n')
			for issue in all_other:
				f.write(f'[#{issue.number} {issue.title}]({issue.html_url})\n\n')





parser = argparse.ArgumentParser(description='IssueWriter: From Issues to Sheets')

parser.add_argument(
	'-al','--aLabel', 
	help="""List of labels to include. If more than one label is specified, the program willfind issues with ALL labels.""", 
	nargs='*', 
	action='append', 
	default=[])

parser.add_argument(
	'-el','--eLabel', 
	help="""List of labels to exclude. If more than one label is specified, the program willfind issues with NONE of the labels""", 
	nargs='*', 
	action='append', 	
	default=[])

parser.add_argument(
	'-m','--milestoneNum', 
	help="""Number of milestone to filter with.\n
	1.32 Maintenance = 10\n
	1.33 Maintenance = 11\n
	Release 1.34 = 12\n
	Release 1.35 = 13
	1.34 Maintenance = 14""", 
	nargs='*', 
	action='append', 
	default=[])

parser.add_argument(
	'-d','--date', 
	help="""Datetime object to act as deadline. Will get all issues closed AFTER the date provided""", 
	nargs='*', 
	action='append')

parser.add_argument(
	'-r','--repo', 
	help='Repository from which issues are pulled', 
	required=True, 
	action='append')

parser.add_argument('-si', '--specificIssues', 
	help="""List of specific issues for a given Repository. If provided, will return sheet with given issues, regardless of other parameters entered.""",
	nargs='*', 
	default=[])

parser.add_argument(
	'-n', '--sheetNum', 
	help='The number of issues per sheet', 
	type=int, 
	default=30)

parser.add_argument(
	'-sn', '--sheetName', 
	help='The name for the sheets in the Workbook', 
	action='append')

parser.add_argument(
	'-wn', '--workbookName', 
	help='The name for workbook. (Full File)')

parser.add_argument(
	'-tc', '--tabColor', 
	help='Color for the created tabs. Can be a string or or HEX. (#FF9900)', 
	action='append')

# parser.add_argument('-ew', '--existingWorkbook', help='Existing Worksheet to copy data from. Any new sheets created will be placed at the end of the worksheet', default=None)

args = vars(parser.parse_args())
wbName = args['workbookName']


newWb = wbMain(**args)
print("Making sheet")
newWb.writeToSheet()
# print("Starting postProcess")
# newWb.postProcess()

# TODO:
# Add color