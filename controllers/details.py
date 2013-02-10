# coding=utf8
import logging

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template

from current_session import current_user
from request_model_binder import model_from_request
from models.users import User
from models.learnlist import LearnList
from models.questions import Question
from models.dictionary import Dictionary
from controllers.incoming import parseMessage
from controllers.incoming import addNewWord


class Details(webapp.RequestHandler):

    def view(self, parameters):
        self.response.out.write(template.render("views/details.html",\
           {"stats_dict":parameters}))

    def get(self):
        user = current_user()
        parameters = {}
        parameters["total_points"] = User.all().\
        	filter("twitter =", user.twitter).get().total_points
        parameters["total_words"] = Dictionary.all().\
        	filter("twitter_user =", user.twitter).count()
        self.view(parameters)


