import logging
from twitter_auth import Twitter

from google.appengine.ext import webapp
from models.users import User

class Admin(webapp.RequestHandler):
    
    def get(self):
        for user in User.all():
            user.default_source_lang = 'en'
            user.put()
 

