import logging
import hashlib
import random
import re

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template

from twitter_auth import Twitter
from current_session import set_current_user, registration_code, set_registration_code
from request_model_binder import model_from_request
from models.users import User

class Register(webapp.RequestHandler):

    def get(self):
        random.seed()
        set_registration_code(random.randint(3000, 9000))
        model = RegisterModel()
        self.view(model)
    
    def post(self):
        twitter = Twitter.getInstance()
        model = model_from_request(self.request, RegisterModel)

        # validate data; on error, redisplay form with error messages
        if not model.validate():
            self.view(model)
            return

        # save new user        
        user = User()
        user.username = model.twitter_name
        user.twitter = model.twitter_name
        user.email = ""
        pwd_hash = hashlib.md5()
        pwd_hash.update(model.password)
        user.password = pwd_hash.hexdigest()
        user.timezone = ""
        user.next_run_time = 0
        user.message_type = "reply"
        user.account_status = "enabled"
        user.repeat_times = 6
        user.followed_by = ""
        user.i_follow = ""
        user.messages_per_day = 10
        user.default_source_lang = "en"
        user.follow_lang_list = "en"

        user.put()

        try:
            twitter.api.CreateFriendship(model.twitter_name)
        except:
            pass

        # put him into session
        set_current_user(user)

        # redirect to the home page
        self.redirect("/profile")

    def view(self, model):
        self.response.out.write(template.render("views/register.html", {"model": model}))

        
class RegisterModel:
    
    def __init__(self):
        self.registration_code = registration_code()
    
    def validate(self):
        twitter = Twitter.getInstance()
        try:
            messages = twitter.api.GetReplies()
        except:
            return False
        self.code_not_received = True
        for message in messages:
            # To check the code we need to remove the @BotName from the message
            # text
            botname_re = re.compile("@"+message.in_reply_to_screen_name, re.IGNORECASE)
            message_text = botname_re.sub('', message.text)
            if message_text.strip() == str(self.registration_code) and message.user.screen_name == self.twitter_name:
                self.code_not_received = False
        self.twitter_name_empty = (self.twitter_name == "")
        self.password_empty = (self.password == "")
        self.passwords_dont_match = (self.password != self.confirm_password)
        return self.is_valid()

    def is_valid(self):
        return not(self.twitter_name_empty\
               or self.password_empty or self.passwords_dont_match\
               or self.code_not_received)
