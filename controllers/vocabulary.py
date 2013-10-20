# coding=utf8
import logging

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template

from current_session import current_user
from models.users import User
from models.learnlist import LearnList
from controllers.incoming import parseMessage
from controllers.incoming import addNewWord


def getParameters(user):
    parameters = {}
    parameters["dict_row"] = []
    parameters["username"] = user.username
    for lli in LearnList.all().filter("twitter_user =", user.twitter)\
                              .order("next_serve_date").run():
        l = []
        l.append(lli.dict_entry.word+" "+lli.dict_entry.pronounce)
        l.append(lli.dict_entry.meaning)
        l.append(lli.next_serve_date.strftime("%B %d"))
        parameters["dict_row"].append(l)
    return parameters


class Vocabulary(webapp.RequestHandler):

    def view(self, parameters, template_file):
        self.response.out.write(template.render(template_file,
                                                parameters))

    def get(self):
        user_name = self.request.path.split('/')[-1]
        viewed_user = User.all().filter("username =", user_name)\
                                .get()
        curr_user = current_user()
        # If non-existing user is specified on URL
        if (user_name != "") and (viewed_user is None):
            self.error(404)
        if viewed_user:
            parameters = getParameters(viewed_user)
            self.view(parameters, "views/view_vocabulary.html")
        elif curr_user:
            parameters = getParameters(curr_user)
            self.view(parameters, "views/vocabulary.html")

    def post(self):
        user = current_user()
        text = self.request.get("new_word")
        message_dict = parseMessage(text, '')
        addNewWord(message_dict, user, None)
        self.redirect("/vocabulary")
