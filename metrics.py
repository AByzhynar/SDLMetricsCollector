from jira import JIRA
from datetime import date, timedelta
import time
import getpass

# TODO:
# Not logged vacation
#	Open code reviews with age more 2 days 
#	Absence of "in progress" issues assigned to each team member 
#	Weekly metrics
#	Monthly project metrics
from IPython.lib.editorhooks import emacs

server = "http://adc.luxoft.com/jira"
current_sprint = "SDL_RB_B3.20"
users = ["DKlimenko", "DTrunov ", "AGaliuzov", "AKutsan", "AOleynik", "ANosach", "OKrotenko", "VVeremjova",
         "AByzhynar", "EZamakhov", "ALeshin", "AKirov", "VProdanov"]

def is_holiday(day):
    return day.weekday() > 4


def calc_diff_days(from_date, to_date):
    from_date = from_date.split("-")
    to_date = to_date.split("-")
    from_date = date(int(from_date[0]), int(from_date[1]), int(from_date[2]))
    to_date = date(int(to_date[0]), int(to_date[1]), int(to_date[2]))
    day_generator = (from_date + timedelta(x + 1) for x in range((to_date - from_date).days))
    return sum(1 for day in day_generator if not is_holiday(day))


def to_h(val):
    return val / 60.0 / 60.0


class SDL():
    issue_path = "https://adc.luxoft.com/jira/browse/%s"
    def __init__(self, user, passwd):
        self.jira = JIRA(server, basic_auth=("AKutsan", passwd))
        self.sdl = self.jira.project('APPLINK')
        versions = self.jira.project_versions(self.sdl)
        for v in versions:
            if v.name == current_sprint:
                self.sprint = v
                break

    def workload(self, user, report=[]):
        query = 'assignee = %s AND status not in (Suspended, Closed, Resolved) AND fixVersion in("%s")'
        issues = self.jira.search_issues(query % (user, self.sprint))
        res = 0
        for issue in issues:
            if issue.fields.timeestimate:
                res += to_h(issue.fields.timeestimate)
                report.append((issue, to_h(issue.fields.timeestimate)))
            else:
                print("Not estimated issue %s (%s)" % (issue, user))
        return res

    def calc_overload(self, users):
        report = []
        for user in users:
            load = self.workload(user)
            today = time.strftime("%Y-%m-%d")
            days_left = calc_diff_days(today, self.sprint.releaseDate)
            hours_left = days_left * 8
            overload = hours_left - load
            #res = "OK"
            if (overload < 0):
                res = "OVERLOAD : %s"%(-overload)
                print("%s overload : %s h  (%s/%s)" % (user, -overload, load, hours_left))
                report_str = "%s/%s : %s"%(load, hours_left, res)
                report.append((user, report_str))
        return report

    def issues_without_due_date(self, users):
        report = []
        for user in users:
            query = ''' assignee = %s and type not in (Question) AND fixversion in ("%s")  AND status not in (Closed, Resolved, Suspended) AND duedate is EMPTY '''
            issues = self.jira.search_issues(query % (user, self.sprint))
            for issue in issues:
                report.append((user, self.issue_path%issue))
                print("%s has issue without estimate %s" % (user, issue))
        return report


    def issues_with_expired_due_date(self, users):
        report = []
        for user in users:
            query = ''' assignee = %s and status not in (closed, resolved, Approved) AND duedate < startOfDay()'''
            issues = self.jira.search_issues(query % user)
            for issue in issues:
                report.append((user, self.issue_path%issue))
                print("%s has issue with expired due date %s" % (user, issue))
        return report


    def expired_in_progress(self, users):
        report = []
        for user in users:
            query = ''' assignee = %s AND status = "In Progress" AND (updated < -2d OR fixVersion = Backlog)'''
            issues = self.jira.search_issues(query % user)
            for issue in issues:
                report.append((user, self.issue_path%issue))
                print("%s has issue in Progress that wasn't updated more then 2 days %s" % (user, issue))
        return report


    def without_correct_estimation(self, users):
        report = []
        for user in users:
            query = ''' assignee = %s and type not in (Question) AND fixversion in ("%s") AND status not in (Closed, Resolved, Suspended) AND (remainingEstimate = 0 OR remainingEstimate is EMPTY)'''
            issues = self.jira.search_issues(query % (user, self.sprint))
            for issue in issues:
                report.append((user, self.issue_path%issue))
                print("%s has issue without correct estimation %s" % (user, issue))
        return report


    def wrong_due_date(self, users):
        report = []
        for user in users:
            query = ''' assignee = %s and type not in (Question) AND fixversion in ("%s") AND (duedate < "%s" OR duedate > "%s") AND status not in (resolved, closed)'''
            issues = self.jira.search_issues(query % (user, self.sprint, self.sprint.startDate, self.sprint.releaseDate))
            for issue in issues:
                report.append((user, self.issue_path%issue))
                print("%s has issue %th wrong due date %s" % (user, issue))
        return report


    def wrong_fix_version(self, users):
        report = []
        for user in users:
            query = '''assignee = %s AND fixversion not in ("%s") and (labels is EMPTY OR labels != exclude_from_metrics) AND status not in (closed, resolved) AND duedate > "%s" AND duedate <= "%s" '''
            issues = self.jira.search_issues(query % (user, self.sprint, self.sprint.startDate, self.sprint.releaseDate))
            for issue in issues:
                report.append((user, self.issue_path%issue))
                print("%s has issue with wrong fix version %s" % (user, issue))
        return report


    def daily_metrics(self, users):
        report = {}
        report['7. Workload of team members'] = self.calc_overload(users)
        report['1. Issues without due dates (except ongoing activities)'] = self.issues_without_due_date(users)
        report['2. Issues with expired due dates'] = self.issues_with_expired_due_date(users)
        report['4. Tickets "in progress" without updating during last 2 days'] = self.expired_in_progress(users)
        report['5. Open issues without correct estimation'] = self.without_correct_estimation(users)
        report['8. Wrong due date'] = self.wrong_due_date(users)
        report['11. Tickets with wrong FixVersion'] = self.wrong_fix_version(users)
        return report


def main():
    user = raw_input("Enter JIRA username : ")
    passwd = getpass.getpass()
    sdl = SDL(user, passwd)
    daily_report = sdl.daily_metrics(users)
    email_list = []
    email_template = "%s@luxoft.com"
    for metric in daily_report:
        print("%s :"%metric)
        fails = daily_report[metric]
        for fail in fails:
            print("\t%s : %s"%(fail[0],fail[1]))
            email = email_template%(fail[0])
            if email not in email_list:
                email_list.append(email)
    email_list = " ;".join(email_list)
    print(email_list)
    return 0
if __name__ == "__main__" :
    main()