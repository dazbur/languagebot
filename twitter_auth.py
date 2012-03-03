from google.appengine.ext import db

import twitter

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
        
        # Login into twitter account
        self.api = twitter.Api(consumer_key='8hUziMDlvgoMLOPskIrIA',
                    consumer_secret='qU86upQ36NogZw7y5HvXvR1Ki6uvH4P7GXlYwpas4',
                    access_token_key='361573893-OuCJBZNnHGjprS0dQxwXeey0GcEjsjdJ3phEc3VH',
                    access_token_secret='4qqahAmLF230ooXE9FRtaWg69cilhvPGzVNJ8IrMhLQ',
                    debugHTTP=True)
        

    def authenticate(self):
        self.api = twitter.Api(consumer_key='8hUziMDlvgoMLOPskIrIA',
                    consumer_secret='qU86upQ36NogZw7y5HvXvR1Ki6uvH4P7GXlYwpas4',
                    access_token_key='361573893-OuCJBZNnHGjprS0dQxwXeey0GcEjsjdJ3phEc3VH',
                    access_token_secret='4qqahAmLF230ooXE9FRtaWg69cilhvPGzVNJ8IrMhLQ',
                    debugHTTP=True)
        
                    
        





