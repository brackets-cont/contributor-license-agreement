import os
import sys
import requests
import json
import subprocess
import re
from datetime import *
from diff_parser import get_diff_details

print("current working directory is: ", os.getcwd())
STATUS_FAILED = 'FAILED'
SUCCESS_MESSAGE = 'ok'


def get_github_details():
    github_info_file = open('./.tmp/github.json', 'r') 
    return json.load(github_info_file)


def get_commit_details():
    commit_info_file = open('./.tmp/commitDetails.json', 'r')
    return json.load(commit_info_file)


def process_git_local_details():
    # Check if current dir is git dir
    is_git_dir = subprocess.check_output(
            ['/usr/bin/git', 'rev-parse', '--is-inside-work-tree']).decode('utf-8')
    print("Is git dir: ", is_git_dir)

    # git status
    git_status = subprocess.check_output(
            ['/usr/bin/git', 'status']).decode('utf-8')
    print("Git status: ", git_status)

    # last n commits
    last_10_commit_list = subprocess.check_output(
            ['/usr/bin/git', 'rev-list', '--max-count=10', 'HEAD']).decode('utf-8')
    print("last 10 commit ids are: ", last_10_commit_list)

    return {
        'is_git_dir': is_git_dir,
        'last_10_commit_list': last_10_commit_list
    }


def extract_pull_request_changes(commits):
    # github logins of all committers
    commit_logins = []
    commit_id_list = []
    files_updated = []
    for commit in commits:
        commiter_github_login = commit['committer']['login']
        if commiter_github_login not in commit_logins:
            commit_logins.append(commiter_github_login)
        
        commit_id = commit['sha']
        commit_id_list.append(commit_id)
        try:
            files = subprocess.check_output(
            ['/usr/bin/git', 'diff-tree', '--no-commit-id', '--name-only', '-r', commit_id]).decode('utf-8').splitlines()
            for file in files:
                if file not in files_updated:
                    files_updated.append(file)
        except subprocess.CalledProcessError as e:
            print("Exception on process, rc=", e.returncode, "output=", e.output)
            sys.exit(1)

    print("All github users who made changes in the pull request: ", commit_logins)
    print("All commit ids in pull request: ", commit_id_list)
    print("All files updated in pull request: ", files_updated)
    
    return {
        'commit_id_list': commit_id_list,
        'commit_logins': commit_logins,
        'files_updated': files_updated
    }



def collect_pr_details(): 
    github = get_github_details()
    commits = get_commit_details()
    git_local = process_git_local_details()
    pr_changes = extract_pull_request_changes(commits)
    return {
        'github': github,
        'commits': commits,
        'num_commits_in_pr': len(commits),
        'event_name': github["event_name"],
        'pr_submitter_github_login': github['event']['pull_request']['user']['login'],
        'github_repo': github['repository'],
        'pr_number' : github['event']['number'],
        'is_git_dir': git_local['is_git_dir'],
        'last_10_commit_list': git_local['last_10_commit_list'],
        'commit_id_list': pr_changes['commit_id_list'],
        'commit_logins': pr_changes['commit_logins'],
        'files_updated': pr_changes['files_updated']
    }


def write_comment(comment):
    print(comment)
    f = open("./.tmp/comment", "a")
    f.write(comment)
    f.write("\n")
    f.close()


def task_failed(comment):
    f = open("./.tmp/failed", "a")
    f.write(comment)
    f.write("\n")
    f.close()
    write_comment(comment)
    return STATUS_FAILED


def get_month_number(month):
    month = month.lower()
    if month == 'january':
        return 1
    if month == 'february':
        return 2
    if month == 'march':
        return 3
    if month == 'april':
        return 4
    if month == 'may':
        return 5
    if month == 'june':
        return 6
    if month == 'july':
        return 7
    if month == 'august':
        return 8
    if month == 'september':
        return 9
    if month == 'october':
        return 10
    if month == 'november':
        return 11
    if month == 'december':
        return 12
    
    return -1


def extract_personal_contributer_details():
	f = open(os.getcwd() + '/personal_contributor_licence_agreement.md')
	personal_cla_contents = f.read()

	personal_contributers_regex = re.compile('\| *\[([^\s]+)\]\([^\s]+\) *\|')
	personal_contributers = personal_contributers_regex.findall(personal_cla_contents)

	return personal_contributers


def extract_employer_contributer_details():
	f = open(os.getcwd() + '/employer_contributor_license_agreement.md')
	employer_cla_contents = f.read()

	employer_contributers_regex = re.compile('\| *\[([^\s]+)\]\([^\s]+\) *\|')
	employer_contributers = employer_contributers_regex.findall(employer_cla_contents)

	return employer_contributers


def validate_is_pull_request(pr_details):
    github_details = pr_details['github']
    if github_details["event_name"] != "pull_request" :
        print("Error! This operation is valid on github pull requests. Exiting. Event received: ", github_details["event_name"])
        sys.exit(1)


def validate_has_only_a_single_commit(pr_details):
    num_commits = pr_details['num_commits_in_pr']
    if num_commits != 1 :
        message = '''## Error: The pull request should have only a single commit. 
        Please squash all your commits and update this pull request.
        more help: https://stackoverflow.com/questions/5189560/squash-my-last-x-commits-together-using-git
        '''
        return task_failed(message)
    print('Pass: Pull request has only a single commit.')


def validate_has_only_a_single_file_change(pr_details):
    files_updated = pr_details['files_updated']
    if len(files_updated) != 1 :
        message = '## Error: The pull request should have exactly one file change signing the CLA. \nBut found the following files changed: '
        for file in files_updated:
            message += '\n   * ' + file
        return task_failed(message)
    print('Pass: Pull request has only a single file change.')

    return validate_changed_file_name(files_updated)


def validate_changed_file_name(files_updated):
    employer_cla_file = 'employer_contributor_license_agreement.md'
    personal_cla_file = 'personal_contributor_licence_agreement.md'

    updated_file_name = files_updated[0]
    if updated_file_name != employer_cla_file and updated_file_name != personal_cla_file:
        return STATUS_FAILED
    print('Pass: Alterations to the correct file.')


def getChanges(patch_details):
    diff_details = get_diff_details(patch_details)
    line_added = None
    if len(diff_details['linesAdded']) == 1:
        line_added = diff_details['linesAdded'][0]
    return {
        'linesRemoved' : len(diff_details['linesRemoved']),
        'linesAdded': len(diff_details['linesAdded']),
        'textAdded': line_added
    }


def validate_row_formatting(files_updated, line):
    employer_cla_file = 'employer_contributor_license_agreement.md'
    FORMATTING_ERROR = ""
    line_format_re = ""
    extra_spaces_re = ""
    single_qoutes_re = ""

    if files_updated[0] == employer_cla_file:
        FORMATTING_ERROR = "Line Format Error: The expected line should be: | `full name` | [git-username](https://github.com/git-username) | employer name | country | dd-month-yyyy | \n"
        # Regular expression for validating the line format
        line_format_re = "\+\|\s*`[A-Za-z]+(\s[A-Za-z]+)*`\s*\|\s*\[[a-zA-Z\d](?:[A-Za-z\d]|-(?=[a-zA-Z\d])){0,38}\]\(https:\/\/github\.com\/[a-zA-Z\d](?:[A-Za-z\d]|-(?=[a-zA-Z\d])){0,38}\)\s*\|[^\|]+\|[a-zA-Z\s\-]+\|\s*[\d]{2}-[a-zA-Z\d]+-[\d]{4}\s*\|"
        # Regular expression for checking extra spaces at the begining of the line
        extra_spaces_re = "\+\s+\|\s*`[A-Za-z]+(\s[A-Za-z]+)*`\s*\|\s*\[[a-zA-Z\d](?:[A-Za-z\d]|-(?=[a-zA-Z\d])){0,38}\]\(https:\/\/github\.com\/[a-zA-Z\d](?:[A-Za-z\d]|-(?=[a-zA-Z\d])){0,38}\)\s*\|[^\|]+\|[a-zA-Z\s\-]+\|\s*[\d]{2}-[a-zA-Z\d]+-[\d]{4}\s*\|"
        # Regular expression for checking single qoutes instead of back ticks
        single_qoutes_re = "\+\|\s*'[A-Za-z]+(\s[A-Za-z]+)*'\s*\|\s*\[[a-zA-Z\d](?:[A-Za-z\d]|-(?=[a-zA-Z\d])){0,38}\]\(https:\/\/github\.com\/[a-zA-Z\d](?:[A-Za-z\d]|-(?=[a-zA-Z\d])){0,38}\)\s*\|[^\|]+\|[a-zA-Z\s\-]+\|\s*[\d]{2}-[a-zA-Z\d]+-[\d]{4}\s*\|"
        pass
    else:
        FORMATTING_ERROR = "Line Format Error: The expected line should be: | `full name` | [git-username](https://github.com/git-username) | dd-month-yyyy | \n"
        line_format_re = "\+\|\s*`[A-Za-z]+(\s[A-Za-z]+)*`\s*\|\s*\[[a-zA-Z\d](?:[A-Za-z\d]|-(?=[a-zA-Z\d])){0,38}\]\(https:\/\/github\.com\/[a-zA-Z\d](?:[A-Za-z\d]|-(?=[a-zA-Z\d])){0,38}\)\s*\|\s*[\d]{2}-[a-zA-Z\d]+-[\d]{4}\s*\|"
        extra_spaces_re = "\+\s+\|\s*`[A-Za-z]+(\s[A-Za-z]+)*`\s*\|\s*\[[a-zA-Z\d](?:[A-Za-z\d]|-(?=[a-zA-Z\d])){0,38}\]\(https:\/\/github\.com\/[a-zA-Z\d](?:[A-Za-z\d]|-(?=[a-zA-Z\d])){0,38}\)\s*\|\s*[\d]{2}-[a-zA-Z\d]+-[\d]{4}\s*\|"
        single_qoutes_re = "\+\|\s*'[A-Za-z]+(\s[A-Za-z]+)*'\s*\|\s*\[[a-zA-Z\d](?:[A-Za-z\d]|-(?=[a-zA-Z\d])){0,38}\]\(https:\/\/github\.com\/[a-zA-Z\d](?:[A-Za-z\d]|-(?=[a-zA-Z\d])){0,38}\)\s*\|\s*[\d]{2}-[a-zA-Z\d]+-[\d]{4}\s*\|"
    
    if re.match(line_format_re, line):
        print('Pass: Added line is of the specified format')
    elif re.match(extra_spaces_re, line):
        print(line)
        return task_failed(FORMATTING_ERROR + 'Please remove extra spaces in the start of the line.')
    elif re.match(single_qoutes_re, line):
        return task_failed(FORMATTING_ERROR + "please use `full name` instead of 'full name'")
    else:
        return task_failed(FORMATTING_ERROR)


def validate_githubid(pr_raiser_login, change):
    USERNAME_ERROR_MESSAGE = 'Username Error: The expected line should be: | `full name` | [git-username](https://github.com/git-username) | dd-month-yyyy | \n'

    username_in_brackets_re = "\|\s*\[(.*)\]" # Git username provided in square brackets
    username_in_url_re = '\(https:\/\/github.com\/(.*)\)' # Git username provided as a part of git profile url

    username_in_brackets_match = re.search(username_in_brackets_re, change)
    username_in_url_match = re.search(username_in_url_re, change)
    if username_in_brackets_match == None or username_in_url_match == None:
        return task_failed(USERNAME_ERROR_MESSAGE)

    username_in_brackets = username_in_brackets_match.group(1)
    username_in_url = username_in_url_match.group(1)
    if pr_raiser_login != username_in_brackets or pr_raiser_login != username_in_url:
        return task_failed(USERNAME_ERROR_MESSAGE + 'Github username should be same as pull request user name')

    print('Pass: Git username successfully validated')
    return SUCCESS_MESSAGE


def validate_date(line):
    DATE_ERROR_MESSAGE = "Date Error: The expected line should be: | `full name` | [git-username](https://github.com/git-username) | dd-month-yyyy | \n"\
                        + "Invalid date: Date should be within one week of <today's date in dd-month-YYYY format>"
   
    # regular expression for extracting the date from line
    date_re = '\|\s*([\d]{2}-[a-zA-Z\d]+-[\d]{4})\s*\|'
    date_string_match = re.search(date_re, line)
    if date_string_match == None:
        return task_failed(DATE_ERROR_MESSAGE)
    
    date_string = date_string_match.group(1)
    dd, month, yyyy = [x for x in date_string.split('-')]
    dd = int(dd)
    month = get_month_number(month)
    yyyy = int(yyyy)
    if month == -1:
        print('Month not entered properly')
        return task_failed(DATE_ERROR_MESSAGE + 'Month not entered properly')

    try:
        pr_date = date(yyyy, month, dd)
    except Exception as e:
        return task_failed(DATE_ERROR_MESSAGE + '\n' + str(e))

    today = date.today()
    date_diff = (today - pr_date).days
    if date_diff < 0 or date_diff > 7:
        print('Given date not within one week')
        return task_failed(DATE_ERROR_MESSAGE)

    print('Pass: Date is of the specified format and within one week of signing')
    return SUCCESS_MESSAGE


def validate_if_already_signed(pr_raiser_login):
    personal_contributers = extract_personal_contributer_details()
    if pr_raiser_login in personal_contributers:
        return task_failed('Error: ' + pr_raiser_login + ' has already signed the personal contributor license agreement.')
    
    employer_contributers = extract_employer_contributer_details()
    if pr_raiser_login in employer_contributers:
        return task_failed('Error: ' + pr_raiser_login + 'has already signed the employer contributor license agreement.')

    print('Pass: User has not signed CLA in personal capacity or employer capacity before')
    return SUCCESS_MESSAGE
    

# Change line is of the format "+| `full name`| [pr_raiser_login](https://github.com/pr_raiser_login) |12-july-2021|"
def validate_change(pr_raiser_login, files_updated, change):
    ROW_FORMATTING_VALIDATION = validate_row_formatting(files_updated, change)
    GITHUBID_VALIDATION = validate_githubid(pr_raiser_login, change)
    DATE_VALIDATION = validate_date(change)
    ALREADY_SIGNED_VALIDATION = validate_if_already_signed(pr_raiser_login)
    
    if ROW_FORMATTING_VALIDATION == STATUS_FAILED or GITHUBID_VALIDATION == STATUS_FAILED or DATE_VALIDATION == STATUS_FAILED or ALREADY_SIGNED_VALIDATION == STATUS_FAILED:
        print('Validation failed. Exiting!')
        return STATUS_FAILED
    
    return SUCCESS_MESSAGE


def validate_patch(pr_details):
    github = pr_details['github']
    diffURL = github['event']['pull_request']['diff_url']
    print(diffURL)
    response = requests.get(diffURL)
    if response.status_code != 200:
        task_failed('Could not get pull request details')
        sys.exit(1)
    
    if validate_changed_file_name(pr_details['files_updated']) == STATUS_FAILED:
        return task_failed('## Error: Changes were performed to the incorrect file. \n Either personal_contributor_license_agreement.md or employer_contributer_license_agreement.md should be changed in the pull request.')
    changes = getChanges(response.text)
    if changes['linesRemoved'] !=0:
        return task_failed('## Error: Some lines were removed. \n    Please re-submit PR containing exactly one change adding your name to the CLA.\n')
    if changes['linesAdded'] !=1:
        return task_failed('## Error: More than 1 line was added. \n   Please re-submit PR containing exactly one change adding your name to the CLA.\n')
    print(changes['textAdded'])

    CHANGE_VALIDATION = validate_change(pr_details['pr_submitter_github_login'], pr_details['files_updated'], changes['textAdded'])
    return CHANGE_VALIDATION

def review_pr():
    print('Reviewing PR')
    pr_details = collect_pr_details()
    validate_is_pull_request(pr_details)
    COMMIT_VALIDATION = validate_has_only_a_single_commit(pr_details)
    FILE_VALIDATION = validate_has_only_a_single_file_change(pr_details)
    PATCH_VALIDATION = validate_patch(pr_details)
    if COMMIT_VALIDATION == STATUS_FAILED or FILE_VALIDATION == STATUS_FAILED or PATCH_VALIDATION == STATUS_FAILED:
        print('Validations failed. Exiting!')
        return
    
    write_comment( '\n## Welcome \nHello ' + pr_details['pr_submitter_github_login'] + ', \n'\
                  + 'Thank you for being a part of our community and helping build free software for the future. '\
                  + 'On behalf of everyone at core.ai open research, we extend a warm welcome to our community. \n'\
                  + 'If you have not done so already, please [join our discord group](https://discord.gg/GaBDAK7BRM) to interact with our community members. \n'
    )


review_pr()

# files_updated1 = ['personal_contributor_licence_agreement.md']
# files_updated2 = ['employer_contributor_license_agreement.md']

# # Invalid row fomatting
# EXPECTED_ERROR_MESSAGE = STATUS_FAILED
# assert validate_change('naren', files_updated1, "+ `full name`| [naren](https://github.com/naren) |14-july-2021|") == EXPECTED_ERROR_MESSAGE
# assert validate_change('naren', files_updated1, "lols") == EXPECTED_ERROR_MESSAGE
# assert validate_change('naren', files_updated1, "+| `full name` [naren](https://github.com/naren) |14-july-2021|") == EXPECTED_ERROR_MESSAGE
# assert validate_change('naren', files_updated1, "+ `full name`| [nare") == EXPECTED_ERROR_MESSAGE
# assert validate_change('naren', files_updated1, "+       | `full name`|   [naren](https://github.com/naren)  |14-july-2021  |   ") == EXPECTED_ERROR_MESSAGE
# assert validate_change('psdhanesh7', files_updated1, "+| Dhanesh P S| [psdhanesh7](https://github.com/psdhanesh7)| 25-March-2022 |")

# assert validate_change('naren', files_updated2, "+ `full name`| [naren](https://github.com/naren) |14-july-2021|") == EXPECTED_ERROR_MESSAGE
# assert validate_change('naren', files_updated2, "lols") == EXPECTED_ERROR_MESSAGE
# assert validate_change('naren', files_updated2, "+| `full name` [naren](https://github.com/naren) |14-july-2021|") == EXPECTED_ERROR_MESSAGE
# assert validate_change('naren', files_updated2, "+ `full name`| [nare") == EXPECTED_ERROR_MESSAGE
# assert validate_change('naren', files_updated2, "+       | `full name`|   [naren](https://github.com/naren)  |14-july-2021  |   ") == EXPECTED_ERROR_MESSAGE
# assert validate_change('psdhanesh7', files_updated2, "+| Dhanesh P S| [psdhanesh7](https://github.com/psdhanesh7)| 25-March-2022 |")

# # success case
# EXPECTED_SUCCESS_MESSAGE = "ok"
# assert validate_change('newuser', files_updated1, "+| `full name user` | [newuser](https://github.com/newuser) | 25-march-2022 |") == EXPECTED_SUCCESS_MESSAGE
# assert validate_change('newuser', files_updated1, "+|`full name user`|[newuser](https://github.com/newuser)|26-march-2022|") == EXPECTED_SUCCESS_MESSAGE
# assert validate_change('newuser', files_updated1, "+|  `full name user`   |    [newuser](https://github.com/newuser)   |  26-march-2022  |") == EXPECTED_SUCCESS_MESSAGE

# assert validate_change('newuser', files_updated2, "+| `full name user` | [newuser](https://github.com/newuser) |abcd.pvt.ltd| India | 25-march-2022 |") == EXPECTED_SUCCESS_MESSAGE
# assert validate_change('newuser', files_updated2, "+|`full name user`|[newuser](https://github.com/newuser)|abcd.pvt.ltd| India | 26-march-2022|") == EXPECTED_SUCCESS_MESSAGE
# assert validate_change('newuser', files_updated2, "+|  `full name user`   |    [newuser](https://github.com/newuser)   |abcd.pvt.ltd| India |   26-march-2022  |") == EXPECTED_SUCCESS_MESSAGE

# user names should be valid
# EXPECTED_ERROR_MESSAGE = STATUS_FAILED
# assert validate_change('naren', files_updated1, "+| `full name`| [psdhanesh](https://github.com/naren) |14-july-2021|") == EXPECTED_ERROR_MESSAGE 
# assert validate_change('naren', files_updated1, "+| `full name`| [naren](https://github.com/psdhanesh7) |14-july-2021|") == EXPECTED_ERROR_MESSAGE 
# assert validate_change('naren', files_updated1, "+| 'full name'| [naren](https://github.com/some_wrong_user) |14-july-2021|") == EXPECTED_ERROR_MESSAGE

# assert validate_change('naren', files_updated2, "+| `full name`| [psdhanesh](https://github.com/naren) |14-july-2021|") == EXPECTED_ERROR_MESSAGE 
# assert validate_change('naren', files_updated2, "+| `full name`| [naren](https://github.com/psdhanesh7) |14-july-2021|") == EXPECTED_ERROR_MESSAGE 
# assert validate_change('naren', files_updated2, "+| 'full name'| [naren](https://github.com/some_wrong_user) |14-july-2021|") == EXPECTED_ERROR_MESSAGE

# DATE_ERROR_MESSAGE = STATUS_FAILED
# assert validate_change('naren', files_updated1, "+| `full name`| [naren](https://github.com/naren) |10-March-2022|") == DATE_ERROR_MESSAGE
# assert validate_change('naren', files_updated1, "+| `full name`| [naren](https://github.com/naren) |14-06-2021|") == DATE_ERROR_MESSAGE
# assert validate_change('naren', files_updated1, "+| `full name`| [naren](https://github.com/naren) ||") == DATE_ERROR_MESSAGE

# assert validate_change('naren', files_updated2, "+| `full name`| [naren](https://github.com/naren) |10-March-2022|") == DATE_ERROR_MESSAGE
# assert validate_change('naren', files_updated2, "+| `full name`| [naren](https://github.com/naren) |14-06-2021|") == DATE_ERROR_MESSAGE
# assert validate_change('naren', files_updated2, "+| `full name`| [naren](https://github.com/naren) ||") == DATE_ERROR_MESSAGE

# # check if already signed
# EXPECTED_ERROR_MESSAGE = STATUS_FAILED
# assert validate_change('Njay2000', files_updated1, "+| `full name`| [Njay2000](https://github.com/Njay2000) |14-july-2021|") == EXPECTED_ERROR_MESSAGE
# assert validate_change('mathewdennis1', files_updated1, "+| `full name`| [mathewdennis1](https://github.com/mathewdennis1) |14-july-2021|") == EXPECTED_ERROR_MESSAGE
# assert validate_change('hello', files_updated1, "+| `full name`| [hello](https://github.com/hello) |14-july-2021|") == EXPECTED_ERROR_MESSAGE

# assert validate_change('Njay2000', files_updated2, "+| `full name`| [Njay2000](https://github.com/Njay2000) |14-july-2021|") == EXPECTED_ERROR_MESSAGE
# assert validate_change('mathewdennis1', files_updated2, "+| `full name`| [mathewdennis1](https://github.com/mathewdennis1) |14-july-2021|") == EXPECTED_ERROR_MESSAGE
# assert validate_change('hello', files_updated2, "+| `full name`| [hello](https://github.com/hello) |14-july-2021|") == EXPECTED_ERROR_MESSAGE

# assert validate_change('psdhanesh7', files_updated2, "+| `Dhanesh P S` | [psdhanesh7](https://github.com/psdhanesh7) | Core.ai Scientific Technologies Private Ltd. |India |14-June-2021|") == STATUS_FAILED
