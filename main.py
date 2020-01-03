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
    "Honors Precalculus" : "Precalculus",
    "AP Computer Science A CS" : "Computer Science",
    "Physical Ed 11 Lab" : "Gym",
    "AP Physics 1" : "Physics",
    "AP US History" : "History",
    "Spanish 3" : "Spanish"
}

UPDATE_FREQ = 30 ## number of seconds in between checks

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
    post_login = s.post(LOGIN_POST_URL, data=loginData)
    return s

def get_all_assignments(s):
    ## Gets all assignments from assignment page and updates db
    ## Takes session as parameter
    page = s.get(ASSIGNMENTS_URL)
    tree = etree.HTML(page.text)

    rows = tree.xpath("//*/tr[contains(@class, 'listrow')]") ## array of Element objects
    data = [] ## all assignments data as list with format [course, teacher, assignment, grade, percentage]
    for row in rows:
        if len(row[5]) == 0: percentage = None
        else: percentage = "".join(row[5][-1].text.split())
        temp = [
            row[2][0].text, ## course
            row[2][1].text, ## teacher
            row[4][0].text, ## assignment
            "".join(row[5].text.split()), ## grade
            percentage ## percentage
        ]
        data.append(temp)
        ##print (temp)
    
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
        if change[0] != currCourse:
            message += "-- {} --\n".format(COURSE_NAMES[change[0]])
            currCourse = change[0]
        message += "{}\n[{} - {}]\n".format(change[2],change[3],change[4])

    message = message.strip()
    ##print(message)
    sms.send_message(message)
    return


oldData = []


loginData = read_login()

lastTime = datetime.datetime.now()

sms.send_message("Grade checker service has started running.")

while True:
    session = login(loginData)
    data = get_all_assignments(session)
    if oldData == []:
        oldData = data

    changes, oldData = find_changes(oldData,session)

    if (len(changes) > 0):
        print("CHANGES: {}".format(changes))
        print("Found {} changes. Notifying user.".format(len(changes)))
        text_changes(changes)

    now = datetime.datetime.now()
    print("Updated. {} -- took {}".format(now, now-lastTime))
    lastTime = now
    time.sleep(UPDATE_FREQ)