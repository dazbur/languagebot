import logging

# Google App Engine imports.
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app

from controllers.home import MainPage
from controllers.register import Register
from controllers.login import Login
from controllers.signout import Signout
from controllers.incoming import CheckIncoming
from controllers.profile import Profile
from controllers.admin import Admin
from controllers.details import Details
from controllers.learnlist import BuildDailyListScheduler
from controllers.learnlist import SendMessagesScheduler
from controllers.learnlist import SendDailyMail
from controllers.rpchandler import RPCHandler
from controllers.vocabulary import Vocabulary
from controllers.userlist import UsersList


# Initialize webb application. Assosiates index URL with MainPage class
application = webapp.WSGIApplication(
                                    [('/', MainPage),
                                    ('/register', Register),
                                    ('/login', Login),
                                    ('/signout', Signout),
                                    ('/check_incoming', CheckIncoming),
                                    ('/send_messages', SendMessagesScheduler),
                                    ('/build_daily_list', BuildDailyListScheduler),
                                    ('/send_daily_mail', SendDailyMail),
                                    ('/profile', Profile),
                                    ('/details', Details),
                                    ('/admin_model', Admin),
                                    ('/vocabulary/.*', Vocabulary),
                                    ('/users', UsersList),
                                    ('/rpc', RPCHandler),
                                    ],
                                     debug=True)


def main():
    logging.getLogger().setLevel(logging.DEBUG)
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
