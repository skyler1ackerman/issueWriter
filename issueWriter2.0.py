from config import TOKEN
from github import Github
from datetime import datetime, timedelta, timezone
from dateutil.parser import parse
import github.GithubObject
import xlsxwriter

# If you use TFA you need to auth using an access token instead of username/password
g = Github(TOKEN)
# Init a WorkBook
wb = xlsxwriter.Workbook('issueSheet.xlsx')
cell_format = wb.add_format({'bold': True, 'bg_color': '#d7dbd8'})

class wbMain():
	g = Github(TOKEN)
	#Init class, set everything to NotSet
	def __init__(self):
		self.iLabelList = self.milestone = self.since = github.GithubObject.NotSet
		self.eLabelList = []
		self.optionList = [('Add a label', self.addILabel), ('Exclude a label', self.addILabel), ('Add a milestone', self.addMilestone), \
		('Specify date', self.addDate), ('Change Repo', self.getRepo), ('Write to sheet', self.writeToSheet), ('Show Current Settings', self.showSettings)]
		self.repoList = g.get_user().get_repos()
		self.repo = None
		self.rowNum = 0

	def input_checker(func):
		def input_checker_wrapper(*args, **kwargs):
			while True:
				try:
					return func(*args, **kwargs)
					break
				except (IndexError, ValueError, KeyError):
					print('Invalid input, please try again')			
		return input_checker_wrapper

	# Add a value to any given
	def addToList(self, listA, val):
		if listA == github.GithubObject.NotSet:
			return [val]
		return listA[:] + [val]

	@input_checker
	def addILabel(self):
		print('Add a label to filter by')
		for idx, obj in enumerate(allLabels:=self.repo.get_labels()):
			print(idx, obj.name)
		print(allLabels.totalCount, 'Cancel')
		objIndex = int(input())
		if objIndex == allLabels.totalCount:
			return
		self.iLabelList = self.addToList(self.iLabelList, allLabels[objIndex])

	@input_checker
	def addELabel(self):
		print('Add a label to exclude')
		for idx, obj in enumerate(allLabels:=self.repo.get_labels()):
			print(idx, obj.name)
		print(allLabels.totalCount, 'Cancel')
		objIndex = int(input())
		if objIndex == allLabels.totalCount:
			return
		self.eLabelList = self.addToList(self.eLabelList, allLabels[objIndex])

	@input_checker
	def addMilestone(self):
		print('Add a milestone to filter by')
		for idx, obj in enumerate(allLabels:=self.repo.get_milestones(state='all')):
			print(idx, obj.title)
		print(allLabels.totalCount, 'Cancel')
		objIndex = int(input())
		if objIndex == allLabels.totalCount:
			return
		self.milestone = allLabels[objIndex]
		print(self.milestone)

	@input_checker
	def addDate(self):
		print('Please enter a date in pretty much any format')
		self.since = parse(input(), fuzzy_with_tokens = True)[0]
		print(self.since)

	def getIssues(self):
		# This needs fixing, how to make it work with the full list?
		if self.eLabelList:
			return [i for i in self.repo.get_issues(state='all', labels=self.iLabelList, milestone=self.milestone, since=self.since, direction='asc') if elabel not in self.iLabelList]
		else:	
			return self.repo.get_issues(state='all', labels=self.iLabelList, milestone=self.milestone, since=self.since, direction='asc')

	@input_checker
	def writeToSheet(self):
		issueList = self.getIssues()
		print('Enter the sheet name')
		ws = wb.add_worksheet(input())
		for i in range(self.rowNum, issueList.totalCount*3, 3):
			# Format the top row
			for j in range(1, 8):
				ws.write(i, j, '', cell_format)
			# Write the issue number and issue title, and link the text back to the original issue
			ws.write_url(i, 1, issueList[int(i/3)].html_url, cell_format, string='#{} {}'.format(issueList[int(i/3)].number, issueList[int(i/3)].title))
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

	def showSettings(self):
		print('Current repository:', self.repo.name)
		print('Current labels to filter by:', end=' '),
		if self.iLabelList != github.GithubObject.NotSet:
			for label in self.iLabelList:
				print(label.name, end=' ')
			print('\n')
		else:
			print('None')
		# print('\nCurrent labels to exclude:'),
		# for label in self.eLabelList:
		# 	print(label/name, end=' '),
		if self.milestone != github.GithubObject.NotSet:
			print('Current milestone:', self.milestone.title, end=' ')
		else:
			print('Current milestone: None')
		if self.since != github.GithubObject.NotSet:
			print('Current date:', self.since.strftime('%m-%d-%y'))
		else:
			print('Current date: None')

	@input_checker
	def getRepo(self):
		# Reset all of the global variables upon switching to a new repo
		self.__init__()
		# Prompt for repo
		print('Select a repository')
		# Show all repos
		for idx, repo in enumerate(self.repoList):
			print(idx, repo.name)
		self.repo = self.repoList[int(input())]

	@input_checker
	def mainMenu(self):
		if not self.repo:
			self.getRepo()
		while True:
			for idx, option in enumerate(self.optionList):
				print(idx, option[0])
			print(len(self.optionList), 'Exit')
			inputIdx = int(input())
			if inputIdx == len(self.optionList):
				break
			self.optionList[inputIdx][1]()

newWb = wbMain()
newWb.mainMenu()
wb.close()


# TODO:
# Show the current settings (TOUCHUP)
# Name the worksheet?