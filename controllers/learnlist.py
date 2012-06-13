from google.appengine.ext import webapp

from twitter import TwitterError
from twitter_auth import Twitter

from models.learnlist import LearnList
from models.users import User

import datetime
import random
import time
import logging
import difflib

random.seed()

MININTERVAL = 1 # Minimal interval between messages in hours
SCHEDULERUN = 600 # Message sender is scheduled to run every SCHEDULERUN seconds 

MAXRATINGLIMIT = 0.9
MINRATINGLIMIT = 0.8
ONEMATCHPERCENT = 80


def addDays(date, days):
    return date + datetime.timedelta(days=days)


def calculateAnswerRating(original, answer):
    # Caclulate the rating of an answer provided using fuzzy comparison
    # both parameters are strings of comma separated words
    original_list = original.split(',')
    answer_list = answer.split(',')
    original_list = [x.strip() for x in original_list]
    answer_list = [x.strip() for x in answer_list]
    rating_list = []
    result = 0

    for a in answer_list:
        r_max = 0
        for o in original_list:
            r  = difflib.SequenceMatcher(None, a, o).ratio()
            if r > r_max:
                r_max = r
        rating_list.append(r_max)
    
    # The logic is the following. Answer with max tating which greater than MAXRATINGLIMIT 
    # will give you ONEMATCHPERCENT result. At MINRATINGLIMIT this will 
    # be ONEMATCHPERCENT - 10. You can get (100 - ONEMATCHPERCENT)/(words_count-1) 
    # for rest of the words
    # Anything smaller than MINRATINGLIMIT should be discarded as insignificant
    
    rating_list = filter(lambda x: x > MINRATINGLIMIT, rating_list)
    if len(rating_list) == 0:
        return 0

    words_count = len(original_list)
    r_max = max(rating_list)

    if r_max >= MAXRATINGLIMIT:
        result = ONEMATCHPERCENT
    else:
        result = ONEMATCHPERCENT - (r_max - MINRATINGLIMIT) / 0.01

    result = result + ((100 - ONEMATCHPERCENT)/(words_count -1)) * (len(rating_list)-1)
    

    return result


# It would be easier to just use this approach for now:
# if answer_rating=0 (no answer at all or completely incorrect answer) 
# then ef'= -0.2
# if answer_rating=1 (correct answer for at least one meaning) then ef' = 0.1
# for each additional correct meaning add 0.05 to ef'
# Starting EF = 1.5
def getNextInterval(n,prev_interval,prev_efactor,answer_rating):
    if n == 1:
        return  {'new_interval':2.0, 'new_efactor':1.5}

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
    i = getNextInterval(1,0,0,1)
    l.twitter_user = twitter_user
    l.dict_entry = dict_entry
    l.interval_days = i['new_interval']
    l.next_serve_date = addDays(now, int(l.interval_days)) 
    l.efactor = i['new_efactor']
    l.total_served = 1
    l.put()

def prepareTwitterMessage(learnListItem):
    served = learnListItem.total_served 
    if learnListItem.dict_entry.pronounce:
        pronounce = learnListItem.dict_entry.pronounce
    else:
        pronounce = ""
    count = " [%s]" % served
    message = "@" + learnListItem.twitter_user + " " + learnListItem.dict_entry.word\
     + pronounce + ": " + learnListItem.dict_entry.meaning + count
    return message

def buildDailyList(day, logging):
    logging.debug("Entered Build Daily List") 
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


def sendMessagesGenerator(TwitterAPI, logging):
    current_time = int(time.time())
    # Are there messages to send out in next SCHEDULERUN seconds?
    next_planned_interval = current_time + SCHEDULERUN

    for lli in LearnList.all().\
        filter("next_serve_time <=", next_planned_interval):
        result = None
        # Don't send messages if user is disabled
        user = User.all().filter("twitter =",lli.twitter_user).\
            filter("account_status =","enabled").fetch(1)
        
        if user == []:            
            yield result
            # If user has messages in todays list but is disabled now
            # Let's just reschedule it to tomorrow
            lli.next_serve_date = addDays(lli.next_serve_date, 1)
            lli.next_serve_time = None
            lli.put()
            continue
        
        message = prepareTwitterMessage(lli)

        
        try:
            TwitterAPI.api.PostUpdate(message)
            result = message
            next_interval = getNextInterval(lli.total_served,\
             lli.interval_days, lli.efactor, 1)
            lli.interval_days = next_interval["new_interval"]
            lli.efactor = next_interval["new_efactor"]
            lli.next_serve_date = addDays(lli.next_serve_date,\
             int(lli.interval_days))
            lli.total_served = lli.total_served + 1
            lli.next_serve_time = None 
            lli.put()
        except TwitterError:
            logging.error("Twitter error when sending message %s" % message)
        yield result
        
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


class BuildDailyListScheduler(webapp.RequestHandler):
    
    def __init__(self):
        self.twitter = Twitter.getInstance()
        super(BuildDailyListScheduler, self).__init__()
    
           
    def get(self):
        today = datetime.date.today() #+ datetime.timedelta(days=2) #TEST!!! 
        buildDailyList(today, logging)


class SendMessagesScheduler(webapp.RequestHandler):
    
    def __init__(self):
        self.twitter = Twitter.getInstance()
        super(SendMessagesScheduler, self).__init__()
    
           
    def get(self):
        g = sendMessagesGenerator(self.twitter, logging)
        while True:
            try:
                message = g.next()
                logging.debug("Sent message %s" % message)
            except StopIteration:
                break

        
     
	
