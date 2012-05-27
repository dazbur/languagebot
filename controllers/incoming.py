# coding=utf8

from google.appengine.ext import webapp
from apiclient.discovery import build
import re

from twitter_auth import Twitter
from models.dictionary import Dictionary
from models.users import User
from models.status import TwitterStatus
from controllers.learnlist import LearnList, getNextInterval, addNewLearnListItem

def parseMessage(message, botname):
    result = {}
    message = message.strip()


    # We need to make sure that @botname is at the begenning of the message. 
    # Message like "I love @LanguageBot :)" should be ignored
    # Also note that Twitter usernames are case insensitive 
    botname_re = re.compile("@"+botname, re.IGNORECASE)
    s = botname_re.search(message)
    if s:
        if s.start() != 0:
            return result

    # Remove @botname from message text
    message = botname_re.sub('', message)

    # Find a pronunciation: word [pronounce]: meaning1, 2, ..
    p = re.compile('\[.*\]')
    m = p.search(message)
    if m:
        result["pronounce"] = m.group()
        # Remove [.*] from text
        message = re.sub(p, "", message)
    else:
        result["pronounce"] = ""

    words = message.split(':',1)
    # If message is in valid definition:meaning1,meaning2... format
    if len(words) > 1:
        result["word"] = words[0].strip()
        result["meaning"] = words[1].strip()
    else:
        result = {}
    
    return result

def addNewDictEntry(twitter_user, message_id,  entry, served):
    dict_entry = Dictionary()
    dict_entry.pronounce = entry["pronounce"]
    dict_entry.twitter_user = twitter_user
    dict_entry.message_id = message_id
    dict_entry.word = entry["word"]
    dict_entry.meaning = entry["meaning"]
    dict_entry.served = served
    dict_entry.source_lang = entry["source_lang"]
    dict_entry.put()
    return dict_entry

def processMessage(message):
        
    # You can get addressee name by checking current
    # Twitter bot username, but this requires additional API call 
    twitter_user = message.user.screen_name

    # Sometimes there are mentions that are not addressed to one user
    # like: "RT @user1 Check out @LanguageBot!" 
    # Such mentions do not have in_reply_to_screen_name specified
    # We are ignoring them
    if  message.in_reply_to_screen_name:
        parsed_dict = parseMessage(message.text, message.in_reply_to_screen_name)
    else:
        return
            
    # Get User
    user =  User.all().filter("twitter =", twitter_user).get()
            
    # Exit if user is not registred. This is to avoid spam
    if not user:
        return            

    # If message is a valid dictionary entry -- save it to database
    if parsed_dict !={}:
    # Try and detect source language using Google Translate API
        try:
            service = build('translate', 'v2',\
                developerKey='AIzaSyAHrpwDJrmFiZOcQhNE6ZgIPY8dxqGsdz8')
            detection = service.detections().list(q=[parsed_dict["word"]]).execute()
        except:
            detection = {}

        if detection == {} or detection["detections"][0][0]["confidence"] <0.00001:
            source_lang = user.default_source_lang
        else:
            source_lang = detection["detections"][0][0]["language"]

        parsed_dict["source_lang"] = source_lang

        new_dict_entry = addNewDictEntry(twitter_user, message.id, parsed_dict, 0)
        addNewLearnListItem (twitter_user, new_dict_entry)


class CheckIncoming(webapp.RequestHandler):
    
    def __init__(self):
        self.twitter = Twitter.getInstance()
        super(CheckIncoming, self).__init__()
    
           
    def get(self):

        # Get the list of incoming replies since last processed ID
        last_processed_status = TwitterStatus.all().get();

        if last_processed_status:
            last_processed_id = last_processed_status.last_processed_id
            last_direct_processed_id = last_processed_status.last_direct_processed_id
        else:
            last_processed_id = None
            last_direct_processed_id = None
            last_processed_status = TwitterStatus()

        messages = self.twitter.api.GetReplies(since_id = last_processed_id)
         

        # Twitter messages are returned from most recent to oldest
        if len(messages) > 0:
            last_processed_id =  messages[0].id


        for message in messages:
            processMessage(message)

        # Save last processed status id to database
        last_processed_status.last_processed_id = last_processed_id
        last_processed_status.put()



        
            

      

