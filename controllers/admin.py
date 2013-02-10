import logging
import hashlib
import os, time
import re
from twitter_auth import Twitter

from google.appengine.ext import webapp
from models.users import User
from models.dictionary import Dictionary
from models.questions import Question

class Admin(webapp.RequestHandler):
    
    def get(self):
        for u in User.all():
            u.total_points = 0
            u.put()
        

