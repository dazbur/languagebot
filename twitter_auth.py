from google.appengine.ext import db

import twitter
import ConfigParser

class Twitter:
    instance = None

    class TwitterHelper:
        def __call__( self, *args, **kw ) :
            if Twitter.instance is None :
                object = Twitter()
                Twitter.instance = object

            return Twitter.instance

    getInstance = TwitterHelper()

    def __init__(self):

        if not Twitter.instance == None :
            raise RuntimeError, 'Only one instance of Twitter is allowed!'
        config = ConfigParser.RawConfigParser()
        config.read('twitter.cfg')
        self.consumer_key = config.get('api', 'consumer_key')
        self.consumer_secret = config.get('api', 'consumer_secret')
        self.access_token_key = config.get('api', 'access_token_key')
        self.access_token_secret = config.get('api', 'access_token_secret')
        self.authenticate()

    def authenticate(self):
        """ Authenticating to Twitter account """
        self.api = twitter.Api(consumer_key=self.consumer_key,
                    consumer_secret=self.consumer_secret,
                    access_token_key=self.access_token_key,
                    access_token_secret=self.access_token_secret)








