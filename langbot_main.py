import logging, os

# Google App Engine imports.
from google.appengine.ext.webapp import util
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template
from google.appengine.ext import db

from controllers.home import MainPage
from controllers.register import Register
from controllers.login import Login
from controllers.signout import Signout
from controllers.incoming import CheckIncoming
from controllers.sendmessages import SendMessages
from controllers.profile import Profile
from controllers.admin import Admin
from controllers.test import TestScreen

# Initialize webb application. Assosiates index URL with MainPage class
application = webapp.WSGIApplication(
                                    [('/', MainPage),
                                    ('/register', Register),
                                    ('/login', Login),
                                    ('/signout', Signout),
                                    ('/check_incoming',CheckIncoming),
                                    ('/send_messages', SendMessages),
                                    ('/profile', Profile),
                                    ('/admin_model', Admin),
                                    ],
                                     debug=True)

def main():
    run_wsgi_app(application)
	
if __name__ == "__main__":
    main()			
