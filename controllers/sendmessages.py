from google.appengine.ext import webapp

from twitter_auth import Twitter
from models.dictionary import Dictionary
from models.users import User
from twitter import TwitterError


import random
import os
import time
import logging

MAXSERVE = 6 # Number of repeats for each word
MAXINTERVAL = 1 # Maximum interval between messages in hours
SCHEDULERUN = 600 # Message sender is scheduled to run every SCHEDULERUN seconds 

class SendMessages(webapp.RequestHandler):
    
    def postMessage(self, user):
        #print "You are %s " % user.twitter
        words = Dictionary.all()\
                        .filter("twitter_user =", user.twitter)\
                        .filter("served < ", user.repeat_times)
            
        dict_entry_list = []
        message = ""
        
        for entry in words:
            dict_entry_list.append(entry)

        #If user has enough his own words to fill all slots for the day
        # If not we need to fill slots with words from people he follows
        if len(dict_entry_list) < user.messages_per_day:
            follow_list = user.i_follow.split(",")
            # for an empty string split() return list with one '' element
            if follow_list == ['']:
                follow_list = []
            # Let's shuffle the list so we get some variety in users
            random.shuffle(follow_list)
            for follow_user in follow_list:
                f_repeat = 0
                for f_user in User.all().filter("twitter =", follow_user):
                    f_repeat = f_user.repeat_times
                    # Getting list of languages user follows
                    follow_lang_list = f_user.follow_lang_list
                    l = []
                    for lang in follow_lang_list.split(","):
                        l.append("'"+lang+"'")
                    lang_str = "(" + ",".join(l) + ")"
                        
                words = Dictionary.all()\
                .filter("twitter_user =", follow_user)\
                .filter("served < ", f_repeat)\
                .filter("source_lang IN ", lang_str)
                for entry in words:
                    dict_entry_list.append(entry)
                    #print "Adding %s from %s" % (entry.word, follow_user)
                if len(dict_entry_list) >= user.messages_per_day:
                    break
        #print "You have %d words in your list" % len(dict_entry_list)    

        # If we have any messages to send at all
        if len(dict_entry_list) > 0:
            dict_entry = random.sample(dict_entry_list,1)[0]
            served = dict_entry.served + 1
            if dict_entry.pronounce:
                pronounce = dict_entry.pronounce
            else:
                pronounce = ""
            count = " [%s]" % served
            # If we are posting message from one of the followed_by list
            # need to add (via @username) if total message is less than 140
            # characters
            if dict_entry.twitter_user != user.twitter:
                via = "(via " + dict_entry.twitter_user + ")"
            else:
                via = ""
            
            if user.default_source_lang != dict_entry.source_lang:
                lang = " ("+dict_entry.source_lang+")"
            else:
                lang = ""

            message = dict_entry.word+lang+pronounce+": "+dict_entry.meaning+count

            if len(message+via) < 140:
                message = message + via

            if user.message_type == "reply":
                try:
                    self.twitter.api.PostUpdate("@" +  user.twitter + " " + message,
                    in_reply_to_status_id=dict_entry.message_id)
                    #print "You will be sent word %s %s" % (dict_entry.word, via)
                except TwitterError:
                    logging.error("Twitter error: %s when sending message %s" %
                    (TwitterError.message, "@" +  dict_entry.twitter_user+
                    " " + message))
                        
                # Direct message are no longer user
                #if user.message_type == "direct":
                #    self.twitter.api.PostDirectMessage(dict_entry.twitter_user, message)

            # We do not change served field for word from other users
            if via == "":
                dict_entry.served = dict_entry.served + 1
                dict_entry.put()


        return message


    def get(self):
        self.twitter = Twitter.getInstance()
        current_time = int(time.time())
        
        # Is there a user to process in next SCHEDULERUN seconds?
        next_planned_interval = current_time + SCHEDULERUN
         
        for user in User.all().filter("account_status =","enabled").filter("next_run_time <=", next_planned_interval):
            next_run_time = current_time + self.getNextRunInterval(user.messages_per_day)
            user.next_run_time = next_run_time
            user.put()
            message = self.postMessage(user)

    def getNextRunInterval(self, messages_per_day):
        seconds_interval = (24 / messages_per_day) * 3600
        next_interval_seconds = random.randint(seconds_interval, seconds_interval + 3600 * MAXINTERVAL)
        return next_interval_seconds
        




    

        
                
                        

        

