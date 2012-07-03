import logging

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template

from current_session import current_user
from request_model_binder import model_from_request
from models.users import User
from models.learnlist import LearnList
from controllers.incoming import parseMessage
from controllers.incoming import addNewWord

def getParameters(user):
    parameters = {}
    parameters["dict_row"] = []
    if not user:
        parameters["username"] = "Please log in"
        return parameters
    else:
        parameters["username"] = user.username

    for lli in LearnList.all().filter("twitter_user =", user.twitter).\
        order("next_serve_date").run():
        l = []
        l.append(lli.dict_entry.word+" "+lli.dict_entry.pronounce)
        l.append(lli.dict_entry.meaning)
        l.append(lli.next_serve_date.strftime("%B %d"))
        parameters["dict_row"].append(l)
    return parameters


class Details(webapp.RequestHandler):

    def view(self, parameters):
        self.response.out.write(template.render("views/details.html", parameters))

    def get(self):
        user = current_user()
        parameters = getParameters(user)
        self.view(parameters)

    def post(self):
        user = current_user()
        text = self.request.get("new_word")
        message_dict = parseMessage(text, '')
        addNewWord(message_dict, user, None)
        self.redirect("/details")



