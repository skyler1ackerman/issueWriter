# A quick helper file for getting the milestone numbers for the Vantiq/vantiq-issues and Vantiq/iqtools repos
# Used to update the allSheets.sh files
from config import TOKEN
from github import Github

g = Github(TOKEN)

r = g.get_repo('Vantiq/vantiq-issues')
for n in r.get_milestones():
	print(n)

r = g.get_repo('Vantiq/iqtools')
for n in r.get_milestones():
	print(n)