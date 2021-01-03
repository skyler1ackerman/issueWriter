from github import Github
from config import TOKEN
import xlsxwriter

# If you use TFA you need to auth using an access token instead of username/password
g = Github(TOKEN)
# Init a WorkBook
wb = xlsxwriter.Workbook('issueSheet.xlsx')
# Add a worksheet. We can make more than one worksheet if there's way's to tell catagories apart.
ws = wb.add_worksheet()
# Set the format for the top row (Bold and Grey)
cell_format = wb.add_format({'bold': True, 'bg_color': '#d7dbd8'})

famBot = g.get_repo('skyler1ackerman/famBot')
vantiq = g.get_repo('Vantiq/iqtools')

LABEL = 'label'
MILESTONE = 'milestone'

def getIssuesByLabel(repo, ilabel, elabel, state='all', milestone='none'):
	if elabel:
		return [i for i in repo.get_issues(state=state, labels=[ilabel], direction='asc') if elabel not in i.labels]
	else:	
		return [i for i in repo.get_issues(state=state, labels=[ilabel], direction='asc')]

def writeToSheet(issueList):
	for i in range(0, len(issueList)*3, 3):
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

def input_checker(func):
	def input_checker_wrapper(*args, **kwargs):
		while True:
			try:
				return func(*args, **kwargs)
				break
			except (IndexError, ValueError, KeyError):
				print('Invalid input, please try again')
	return input_checker_wrapper

@input_checker
def getRepo():
	# Prompt for repo
	print('Select a repository')
	# Show all repos
	for idx, repo in enumerate(allRepos:=g.get_user().get_repos()):
		print(idx, repo.name)
	return allRepos[int(input())]

@input_checker
def getRepoObject(repo, repoObject, prompt):
	print(prompt)
	functDict = {LABEL: repo.get_labels(), MILESTONE: repo.get_milestones(state='all')}
	for idx, obj in enumerate(allObjects:=functDict[repoObject]):
		try:
			print(idx, obj.name)
		except AttributeError:
			print(idx, obj.title)
	print(allObjects.totalCount, 'None')
	objIndex = int(input())
	if objIndex == allObjects.totalCount:
		return None
	return allObjects[objIndex]

@input_checker
def getYesNo(prompt):
	print(prompt, '(Y/N)')
	yesNoDict = {'y': True, 'n': False}
	return yesNoDict[input().lower()]

def getInput():
	# Get the base repo
	repo = getRepo()
	ilabel = getRepoObject(repo, LABEL, 'Select a label to filter by')
	elabel = getRepoObject(repo, LABEL, 'Select a label to exclude')
	if getYesNo('Would you like to sort by a milestone?'):
		milestone = getRepoObject(repo, MILESTONE, 'Select a milestone to filter by')
	else:
		milestone = None
	# Write the the sheet
	print('Running...')
	writeToSheet(getIssuesByLabel(repo=repo, ilabel=ilabel, elabel=elabel, state='all', milestone=milestone))
	print('Done!')

getInput()
# Close the workbook
wb.close()