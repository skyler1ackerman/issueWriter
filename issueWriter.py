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

def getIssuesByLabel(repo, ilabel, elabel, state):
	if elabel:
		return [i for i in repo.get_issues(state=state) if ilabel in i.labels and elabel not in i.labels]
	else:
		return [i for i in repo.get_issues(state=state) if ilabel in i.labels]

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

def getInput():
	# Prompt for repo
	print('Select a repo')
	# Show all repos
	for idx, repo in enumerate(allRepos:=g.get_user().get_repos()):
		print(idx, repo.name)
	# Select the given repo
	repo = allRepos[int(input())]
	# Prompt for label to include
	print('Select a label to filter by')
	# List all labels
	for idx, label in enumerate(allLabels:=repo.get_labels()):
		print(idx, label.name)
	# Select the given label
	ilabel = allLabels[int(input())]
	# Prompt for label  to exclude
	print('Select a label to exclude')
	# List all labels again
	for idx, label in enumerate(allLabels):
		print(idx, label.name)
	print(len(allLabels), 'None')
	# Select the given label
	try:
		elabel = allLabels[int(input())]
	except KeyError:
		elabel = None
	# Write the the sheet
	print('Running...')
	writeToSheet(getIssuesByLabel(repo, ilabel, elabel, 'all'))
	print('Done!')

getInput()
# Close the workbook
wb.close()