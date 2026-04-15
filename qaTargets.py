from config import TOKEN
from github import Github
import xlsxwriter

g = Github(TOKEN)

r = g.get_repo('Vantiq/iqtools')


# Gets all of the QA targets
def get_all_qa_targets():
    all_qa_targets = []
    for n in r.get_issues(labels=['qaTarget'], state='all'):
        all_qa_targets.append(n)
    return all_qa_targets

# Gets the QA targets and writes them to a sheet
def write_to_sheet(issue_list):
    wb = xlsxwriter.Workbook('qaTargets.xlsx')
    cell_format = wb.add_format({'bold': True, 'bg_color': '#d7dbd8'})
    ws = wb.add_worksheet()
    ws.write(0, 0, 'Issue Number')
    ws.write(0, 1, 'Issue Title')
    ws.write(0, 2, 'Ease of Testability')
    ws.write(0, 3, 'Intern Recommendation')
    ws.write(0, 4, 'Other notes')
    cur_row = 1
    for issue in issue_list:
        ws.write_url(cur_row, 1, issue.html_url, cell_format, issue.title)
        ws.write(cur_row, 0, f'#{issue.number}')
        cur_row += 2
    wb.close()


all_qa_targets = get_all_qa_targets()
write_to_sheet(all_qa_targets)
