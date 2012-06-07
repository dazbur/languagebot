from models.learnlist import LearnList
from models.users import User
import datetime
import random
import time

random.seed()

MININTERVAL = 1 # Minimal interval between messages in hours
SCHEDULERUN = 600 # Message sender is scheduled to run every SCHEDULERUN seconds 


def addDays(date, days):
    return date + datetime.timedelta(days=days)

# It would be easier to just use this approach for now:
# if answer_rating=0 (no answer at all or completely incorrect answer) 
# then ef'= -0.2
# if answer_rating=1 (correct answer for at least one meaning) then ef' = 0.1
# for each additional correct meaning add 0.05 to ef'
# Starting EF = 1.5
def getNextInterval(n,prev_interval,prev_efactor,answer_rating):
    if n == 1:
        return  {'new_interval':2, 'new_efactor':1.5}

    new_interval = prev_interval * prev_efactor
    new_efactor = prev_efactor
    if answer_rating == 0:
        new_efactor = prev_efactor - 0.2
    if answer_rating == 1:
        new_efactor = prev_efactor + 0.1

    return {'new_interval':round(new_interval,2),\
        'new_efactor':round(new_efactor,2)}

def addNewLearnListItem(twitter_user, dict_entry):
    l = LearnList()
    now = datetime.date.today()
    i = getNextInterval(1,0,0,0)
    l.twitter_user = twitter_user
    l.dict_entry = dict_entry
    l.interval_days = i['new_interval']
    l.next_serve_date = addDays(now, int(l.interval_days)) 
    l.efactor = i['new_efactor']
    l.total_served = 0
    l.put()

def prepareTwitterMessage(learnListItem):
    served = learnListItem.total_served + 1
    if learnListItem.dict_entry.pronounce:
        pronounce = learnListItem.dict_entry.pronounce
    else:
        pronounce = ""
    count = " [%s]" % served
    message = "@" + learnListItem.twitter_user + " " + learnListItem.dict_entry.word\
     + pronounce + ": " + learnListItem.dict_entry.meaning + count
    return message

def buildDailyList(day):
    current_timestamp = int(time.time())
    for user in User.all().filter("account_status =","enabled"):
        llQuery = LearnList.all().filter("twitter_user =",\
                user.twitter).filter("next_serve_date =",day)
        i = 0
        message_list = []
        for learnListItem in llQuery.run():
            # If we are within limit of messages per dat, keep adding
            if i < user.messages_per_day:
                message_list.append(learnListItem)
                i = i + 1                
            # if we exceeded limit per day, reschedule to next day
            else:
                learnListItem.next_serve_date =\
                     addDays(learnListItem.next_serve_date, 1)
                learnListItem.put() 
                i = i + 1
        # Set next run timestamp for words scheduled for today
        interval_gen = getNextRunInterval(len(message_list))
        for l in  message_list:
            try:
                s = interval_gen.next()
                l.next_serve_time = current_timestamp + s 
                l.put()
            except StopIteration:
                pass

def sendMessages(TwitterAPI):
    return TwitterAPI.api.PostUpdate("blah!")
        
def getNextRunInterval(messages_per_day):
    seconds_interval = (24 / messages_per_day) * 3600
    new_interval = 0
    i = 1
    while i <= messages_per_day:
        # Random part is added to avoid sending multiple twitter 
        # messages at the same time
        new_interval = new_interval + random.randint(MININTERVAL*3600,\
             seconds_interval)
        yield new_interval
        i = i + 1
     
	
