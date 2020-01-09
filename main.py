import requests
import time
from lxml import etree
import ast
import datetime

#personal module
import sms

LOGIN_POST_URL = "https://parents.frhsd.com/genesis/sis/j_security_check"
MAIN_GRADES_URL = "https://parents.frhsd.com/genesis/parents?tab1=studentdata&tab2=gradebook&tab3=weeklysummary&studentid=2140376&action=form"
ASSIGNMENTS_URL = "https://parents.frhsd.com/genesis/parents?tab1=studentdata&tab2=gradebook&tab3=listassignments&studentid=2140376&action=form&dateRange=allMP&courseAndSection=&status="

COURSE_NAMES = {
    "AP English Language & Comp" : "English",
    "Health 11 Lab" : "Health", 
    "Honors Precalculus" : "Precalc",
    "AP Computer Science A CS" : "Comp Sci",
    "Physical Ed 11 Lab" : "Gym",
    "AP Physics 1" : "Physics",
    "AP US History" : "History",
    "Spanish 3" : "Spanish"
}

UPDATE_FREQ = 30 ## number of seconds in between checks

MAX_RETRIES = 10 ## number of times to retry url GET/POST

def read_login():
    ## Set variables from config
    with open("config.json") as infile:
        read = infile.read()
        info = ast.literal_eval(read)
    return info

def login(loginData):
    ## Logs into genesis and returns session    
    s = requests.Session()
    ##print(loginData)
    post_login = post(LOGIN_POST_URL, loginData, s)
    return s

def format_grade(grade):
    ## removes unnecessary newlines and returns from grade string
    return "".join(grade.split())

def get_all_assignments(s):
    ## Gets all assignments from assignment page and updates db
    ## Takes session as parameter
    page = get(ASSIGNMENTS_URL,s)
    tree = etree.HTML(page.text)

    rows = tree.xpath("//*/tr[contains(@class, 'listrow')]") ## array of Element objects
    course = "//*/tr[contains(@class, 'listrow')][{}]/td[3]/div[1]"
    teacher = "//*/tr[contains(@class, 'listrow')][{}]/td[3]/div[2]"
    assignment = "//*/tr[contains(@class, 'listrow')][{}]/td[5]/b"
    grade = "//*/tr[contains(@class, 'listrow')][{}]/td[6]/text()"
    percentage = "//*/tr[contains(@class, 'listrow')][{}]/td[6]/div[contains(@style, 'bold')]"
    data = [] ## all assignments data as list with format [course, teacher, assignment, grade, percentage]
    for row in range(1, len(rows)+1):
        ## holy hackjob
        g = tree.xpath(grade.format(row)) ## check grade to see which index to use
        if len(g) == 2: grade_str = format_grade(g[0])
        else: grade_str = format_grade(g[1])

        p = tree.xpath(percentage.format(row)) ## check percentage for empty grades
        if len(p) == 0: percent_str = ""
        else: percent_str = format_grade(p[0].text)

        temp = [
            tree.xpath(course.format(row))[0].text, ## course
            tree.xpath(teacher.format(row))[0].text, ## teacher
            tree.xpath(assignment.format(row))[0].text, ## assignment
            grade_str,
            percent_str
        ]
        data.append(temp)
    
    return data

def find_changes(oldData,s):
    ## compares oldData with newly fetched data
    ## accepts oldData list and session object as parameters
    ## returns list of changes and newly fetched data 
    newData = get_all_assignments(s)
    changes = []
    for data in newData:
        if data not in oldData:
            changes.append(data)
    return changes, newData

def text_changes(changes):
    ## texts formatted changes to user
    ## accepts list of changes as parameter
    message = ""
    changes = sorted(changes, key=lambda x: x[0]) ## sort by course name
    courses = list(set([x[0] for x in changes]))
    
    currCourse = ""

    for change in changes:
        if change[3] == "" and change[4] == "":
            print("Skipping change: {}".format(change))
            continue
        if change[0] != currCourse:
            message += "-- {} --\n".format(COURSE_NAMES[change[0]])
            currCourse = change[0]
        message += "{}\n[{}]\n".format(change[2],
            (" - ".join(
                [x for x in [change[3],change[4]] if x is not None and x != ""]
            ))) ## formats grade so that there won't be any blank spaces

    message = message.strip()
    ##print(message)
    if message != "": ## prevent empty message
        sms.send_message(message)
    return

def get(url, s):
    ## method for retrying get request multiple times before giving up
    for _ in range(MAX_RETRIES):
        try:
            return s.get(url)
        except:
            print("FAILED GET, RETRYING")
            time.sleep(0.5)

def post(url, data, s):
    ## method for retrying post request multiple times before giving up
    for _ in range(MAX_RETRIES):
        try:
            return s.post(url, data=data)
        except:
            print("FAILED POST, RETRYING")
            time.sleep(0.5)


            
def run():    
    ## main loop function
    oldData = []

    loginData = read_login()

    lastTime = datetime.datetime.now()

    sms.send_message("Grade checker service has started running.")

    while True:
        session = login(loginData)
        data = get_all_assignments(session)
        print (data[3])
        if data == []: continue
        if oldData == []: oldData = data
        changes, oldData = find_changes(oldData,session)

        if (len(changes) > 0):
            print("CHANGES: {}".format(changes))
            print("Found {} changes. Notifying user.".format(len(changes)))
            text_changes(changes)

        now = datetime.datetime.now()
        print("Updated. {} -- took {}. {} assignments".format(now, now-lastTime, len(oldData)))
        lastTime = now
        time.sleep(UPDATE_FREQ)


import traceback
try:
    run()
except Exception as e: ## notify user when program crashes
    print(traceback.format_exc()) ## print traceback
    sms.send_message("Genesis program has crashed:\n{}".format(e))