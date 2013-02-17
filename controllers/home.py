
from google.appengine.ext import webapp

from current_session import current_user


class MainPage(webapp.RequestHandler):
    def get(self):
        user = current_user()
        if user:
			self.redirect("/details")
        else:
        	self.redirect("/login")
            
