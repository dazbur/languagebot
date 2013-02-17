# coding=utf8

from google.appengine.ext import webapp
from apiclient.discovery import build
import re
import datetime

from twitter_auth import Twitter
from models.dictionary import Dictionary
from models.users import User
from models.status import TwitterStatus
from models.questions import Question
from controllers.learnlist import addNewLearnListItem, calculateAnswerRating,\
     rescheduleLearnListItem
from langbot_globals import *


def parseOpt(message):
    """Parses out optional section [] from the message
    Optional section can include pronounciation or other info"""

    result = ""
    p = re.compile('\[.*\]')
    m = p.search(message)
    if m:
        result = m.group()
        # Remove [.*] from text
        message = re.sub(p, "", message)
    else:
        result = ""
    return (message, result)


def parseMessage(message, botname=''):
    result = {}
    message = message.strip()
    # We need to make sure that @botname is at the begenning of the message.
    # Message like "I love @LanguageBot :)" should be ignored
    # Also note that Twitter usernames are case insensitive
    botname_re = re.compile("@" + botname, re.IGNORECASE)
    s = botname_re.search(message)
    if s:
        if s.start() != 0:
            return result

    # Remove @botname from message text
    message = botname_re.sub('', message)

    # Find a pronunciation: word [pronounce]: meaning1, 2, ..
    message, result["pronounce"] = parseOpt(message)

    words = message.split(':', 1)
    # If message is  valid definition:meaning1,meaning2... format
    if len(words) > 1:
        result["word"] = words[0].strip().lower()
        # Need to replace all ";" with ","
        r = re.compile(";")
        result["meaning"] = r.sub(',', words[1].strip().lower())
    else:
        result = {}
    return result


def parseAnswer(message, botname):
    # We need a different parsing for mesages that are answers
    message = message.strip()
    # We need to make sure that @botname is at the begenning of the message.
    # Message like "I love @LanguageBot :)" should be ignored
    # Also note that Twitter usernames are case insensitive
    botname_re = re.compile("@" + botname, re.IGNORECASE)
    s = botname_re.search(message)
    if s:
        if s.start() != 0:
            return result

    # Remove @botname from message text
    message = botname_re.sub('', message)
    return message


def addNewDictEntry(twitter_user, message_id,  entry, served):
    new_dict_entry = None
    # No duplicate words allowed for a single user
    c = Dictionary.all().filter("word =", entry["word"]).\
        filter("twitter_user =", twitter_user).count()
    #logging.debug("Count for word %s is %s" % (entry["word"], c))
    if c == 0:
        new_dict_entry = Dictionary()
        new_dict_entry.pronounce = entry["pronounce"]
        new_dict_entry.twitter_user = twitter_user
        new_dict_entry.message_id = message_id
        new_dict_entry.word = entry["word"]
        new_dict_entry.meaning = entry["meaning"]
        new_dict_entry.served = served
        new_dict_entry.source_lang = entry["source_lang"]
        new_dict_entry.put()
    return new_dict_entry


def checkForAnswer(parsed_dict, twitter_user):
    # Check for answers via DirectMessage
    question = Question.all().\
        filter("twitter_user =", twitter_user).\
        filter("word =", parsed_dict["word"]).\
        filter("answer_received =", None).\
        filter("question_message_id !=", None).get()
    if not question:
        return None
    return question


def addNewWord(parsed_dict, user, message_id):
    if parsed_dict != {}:
    # Try and detect source language using Google Translate API
        try:
            service = build('translate', 'v2',\
                developerKey='AIzaSyAHrpwDJrmFiZOcQhNE6ZgIPY8dxqGsdz8')
            detection = service.detections().list(q=[parsed_dict["word"]]).execute()
        except:
            detection = {}

        if detection == {} or\
          detection["detections"][0][0]["confidence"] < 0.00001:
            source_lang = user.default_source_lang
        else:
            source_lang = detection["detections"][0][0]["language"]

        parsed_dict["source_lang"] = source_lang
        # You get one point for each new word. Yay!
        user.total_points = user.total_points + 1
        user.put()

        new_dict_entry = addNewDictEntry(user.twitter, message_id, parsed_dict, 0)
        if new_dict_entry:
            addNewLearnListItem(user.twitter, new_dict_entry)


def processMessage(message):
    today = datetime.date.today()
    # You can get addressee name by checking current
    # Twitter bot username, but this requires additional API call
    twitter_user = message.sender_screen_name
    # Get User
    user = User.all().filter("twitter =", twitter_user).get()
    # Exit if user is not registred. This is to avoid spam
    if not user:
        return
    parsed_dict = parseMessage(message.text, message.recipient_screen_name)
    question = checkForAnswer(parsed_dict, twitter_user)

    # Check if message is an answer to a previously sent question
    if question:
        answer_rating = calculateAnswerRating(question.lli_ref.dict_entry.meaning,\
             parsed_dict["meaning"])
        question.answer_received = today
        question.answer_rating = answer_rating
        question.lli_ref.latest_answer_rating = answer_rating
        question.answer_text = parsed_dict["meaning"]
        question.put()
        question.lli_ref.put()
        if (user.total_points + answer_rating) > 0:
            user.total_points = user.total_points + answer_rating
        else:
            user.total_points = 0
        user.put()
        # If answer_rating is very poor, we need to show correct answer right away
        # else reschedule as normal accorsing to answer_rating
        if answer_rating < 0:
            question.lli_ref.next_serve_time = 0
            question.lli_ref.next_serve_date = today
            question.put()
            question.lli_ref.put()
        else:
            rescheduleLearnListItem(question.lli_ref, answer_rating)
        return
    # If message is a valid dictionary entry -- save it to database
    addNewWord(parsed_dict, user, message.id)
    user.put()


class CheckIncoming(webapp.RequestHandler):

    def __init__(self):
        self.twitter = Twitter.getInstance()
        super(CheckIncoming, self).__init__()

    def get(self):
        # Get the list of incoming replies since last processed ID
        last_processed_status = TwitterStatus.all().get()
        if last_processed_status:
            last_processed_id = last_processed_status.last_processed_id
        else:
            last_processed_id = None
            last_processed_status = TwitterStatus()

        messages = self.twitter.api.\
            GetDirectMessages(since_id=last_processed_id)
        # Twitter messages are returned from most recent to oldest
        if len(messages) > 0:
            last_processed_id = messages[0].id

        for message in messages:
            processMessage(message)
        # Save last processed status id to database
        last_processed_status.last_processed_id = last_processed_id
        last_processed_status.put()
