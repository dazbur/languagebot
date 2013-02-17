# coding=utf8

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template

from current_session import current_user
from models.users import User
from models.dictionary import Dictionary


class Details(webapp.RequestHandler):

    def view(self, parameters):
        self.response.out.write(template.render("views/details.html",\
           {"stats_dict": parameters}))

    def get(self):
        user = current_user()
        if not user:
            self.redirect("/login")
        else:
            parameters = {}
            parameters["total_points"] = User.all().\
                filter("twitter =", user.twitter).get().total_points
            parameters["total_words"] = Dictionary.all().\
                filter("twitter_user =", user.twitter).count()
            self.view(parameters)
