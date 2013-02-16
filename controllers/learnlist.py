from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.api import mail

import datetime
import random
import time
import logging
import difflib
import sys
import os

from twitter import TwitterError
from twitter_auth import Twitter

from models.learnlist import LearnList
from models.users import User
from models.questions import Question
from langbot_globals import *


random.seed()


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
            r = difflib.SequenceMatcher(None, a, o).ratio()
            if r > r_max:
                r_max = r
        rating_list.append(r_max)

    # The logic is the following. You get POINTS_PER_GUESS for first right
    # answer, 2 x POINTS_PER_GUESS for second, etc.
    i = 1
    for r in rating_list:
        if r > MINRATINGLIMIT:
            result = result + POINTS_PER_GUESS * i
            i = i + 1
    # You get -POINTS_PER_GUESS if you had no correct answers
    if result == 0:
        result = -POINTS_PER_GUESS

    return result


def getNextInterval(n, prev_interval, prev_efactor, answer_rating):
    if n == 1:
        return {'new_interval': 2.5, 'new_efactor': 1.5}

    new_interval = prev_interval * prev_efactor
    new_efactor = prev_efactor
    if answer_rating < 0:
        new_efactor = prev_efactor - 0.2
    if answer_rating >= 0:
        new_efactor = prev_efactor + 0.3
    return {'new_interval': round(new_interval, 2), \
        'new_efactor': round(new_efactor, 2)}


def rescheduleLearnListItem(lli, answer_rating):
    next_interval = getNextInterval(lli.total_served,\
        lli.interval_days, lli.efactor, answer_rating)
    lli.interval_days = next_interval["new_interval"]
    lli.efactor = next_interval["new_efactor"]
    lli.next_serve_date = addDays(lli.next_serve_date,\
        int(lli.interval_days))
    lli.total_served = lli.total_served + 1
    lli.next_serve_time = sys.maxint
    lli.put()


def addNewLearnListItem(twitter_user, dict_entry):
    l = LearnList()
    now = datetime.date.today()
    i = getNextInterval(1, 0, 0, 1)
    l.twitter_user = twitter_user
    l.dict_entry = dict_entry
    l.interval_days = i['new_interval']
    l.next_serve_date = addDays(now, int(l.interval_days))
    l.efactor = i['new_efactor']
    l.next_serve_time = sys.maxint
    l.total_served = 1
    l.latest_answer_rating = 0
    l.put()


def prepareTwitterMessage(learnListItem):
    served = learnListItem.total_served
    if learnListItem.dict_entry.pronounce:
        pronounce = learnListItem.dict_entry.pronounce
    else:
        pronounce = ""
    count = " [%s]" % served
    message = learnListItem.dict_entry.word\
     + pronounce + ": " + learnListItem.dict_entry.meaning + count
    return message


def prepareQuestionMessage(learnListItem):
    served = learnListItem.total_served
    if learnListItem.dict_entry.pronounce:
        pronounce = learnListItem.dict_entry.pronounce
    else:
        pronounce = ""
    count = " [%s]" % served
    message = learnListItem.dict_entry.word\
     + pronounce + ":?" + count
    return message


def acknowledgeQuestions(day):
    # This is used to acknowledge any unaswered question
    # It sets answer rating to 0 and reschedules to today
    for question in Question.all().filter("answer_received =", None).\
            filter("question_message_id !=", None):
        question.answer_received = day
        question.answer_rating = -POINTS_PER_GUESS
        question.lli_ref.latest_answer_rating = 0
        question.lli_ref.next_serve_time = 0
        question.lli_ref.next_serve_date = day
        question.lli_ref.total_served += 1
        question.put()
        question.lli_ref.put()


def buildDailyList(day, logging):
    logging.debug("Entered Build Daily List")
    current_timestamp = int(time.time())
    for user in User.all().filter("account_status =", "enabled"):
        llQuery = LearnList.all().filter("twitter_user =",\
                user.twitter).filter("next_serve_date =", day)
        use_questions = user.use_questions
        utc_offset = 0
        if user.utc_offset != None:
            utc_offset = user.utc_offset
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
        for l in message_list:
            try:
                time_shift = FIRSTMESSAGEHOUR * 3600 - utc_offset * 3600
                s = interval_gen.next()
                l.next_serve_time = current_timestamp + s + time_shift
                # Create new question entry for every second serve
                # If user has this option enabled
                if use_questions == "yes" and (l.total_served % 2 == 0):
                    q = Question()
                    q.lli_ref = l
                    q.twitter_user = user.twitter
                    q.word = l.dict_entry.word
                    q.put()
                l.put()
            except StopIteration:
                pass


def prepareEmailMessagesGenerator():
    # This must be run after buildDailyList
    # Since only there a daily message limit is applied
    # though, this limit can be different for emails
    path_current = os.path.dirname(__file__)
    root_path = os.path.split(path_current)[0]
    view_path = root_path + "/views/daily_email.html"

    today = datetime.date.today()
    emails_dict = {}
    for user in User.all().filter("account_status =", "enabled").\
        filter("use_daily_email =", "yes"):

        parameters = {}
        parameters["dict_row"] = []
        for lli in LearnList.all().\
            filter("next_serve_date =", today).\
            filter("twitter_user =", user.twitter):
            l = []
            l.append(lli.dict_entry.word + " " + lli.dict_entry.pronounce)
            l.append(lli.dict_entry.meaning)
            parameters["dict_row"].append(l)
        emails_dict["email"] = user.email
        emails_dict["message"] = template.\
            render(view_path, parameters)
        yield emails_dict


def sendMessagesGenerator(TwitterAPI, logging):
    current_time = int(time.time())
    # Are there messages to send out in next SCHEDULERUN seconds?
    next_planned_interval = current_time + SCHEDULERUN
    today = datetime.date.today()

    for lli in LearnList.all().\
        filter("next_serve_time <=", next_planned_interval):
        result = None
        # Don't send messages if user is disabled
        user = User.all().filter("twitter =", lli.twitter_user).\
            filter("account_status =", "enabled").fetch(1)
        if user == []:
            yield result
            # If user has messages in todays list but is disabled now
            # Let's just reschedule it to tomorrow
            lli.next_serve_date = addDays(lli.next_serve_date, 1)
            lli.next_serve_time = sys.maxint
            lli.put()
            continue

        # If there is a question to send, prepare a different
        # Twitter message format
        question = Question.all().filter("lli_ref =", lli).\
            filter("answer_received =", None).fetch(1)

        if question != []:
            message = prepareQuestionMessage(lli)
        else:
            message = prepareTwitterMessage(lli)

        try:
            #status = TwitterAPI.api.PostUpdate(message)
            status = TwitterAPI.api.PostDirectMessage(lli.twitter_user,\
             message)
            result = message
            # For questions we do no recalculate new interval right away
            # We do it when answer is recieved or no received
            # Instead we update Question entity
            if question == []:
                answer_rating = lli.latest_answer_rating
                rescheduleLearnListItem(lli, answer_rating)
            else:
                question[0].question_sent = today
                question[0].question_message_id = status.id
                question[0].put()
                # We also need to make sure this message is not sent again automatically
                # Until answer is recieved or it expires
                lli.next_serve_time = sys.maxint
                lli.put()

        except TwitterError:
            print TwitterError.message
            logging.error("Twitter error when sending message %s" % message)
        yield result


def getNextRunInterval(messages_per_day):
    seconds_interval = (24 / messages_per_day) * 3600
    new_interval = 0
    i = 1
    while i <= messages_per_day:
        # Random part is added to avoid sending multiple twitter
        # messages at the same time
        new_interval = new_interval + random.randint(MININTERVAL * 3600, \
             seconds_interval)
        yield new_interval
        i = i + 1


class BuildDailyListScheduler(webapp.RequestHandler):

    def __init__(self):
        self.twitter = Twitter.getInstance()
        super(BuildDailyListScheduler, self).__init__()

    def get(self):
        today = datetime.date.today()
        # Before we build a daily list let's acknowledge any unaswered questions
        # From previous day
        acknowledgeQuestions(today)
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


class SendDailyMail(webapp.RequestHandler):

    def get(self):
        g = prepareEmailMessagesGenerator()
        while True:
            try:
                emails_dict = g.next()
                message = mail.EmailMessage(sender="zburivsky@gmail.com",
                            subject="Language Bot Daily Mail")

                message.to = emails_dict["email"]
                message.html = emails_dict["message"]
                message.send()
            except StopIteration:
                break
