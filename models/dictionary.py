from google.appengine.ext import db

class Dictionary(db.Model):
    twitter_user    = db.StringProperty()
    message_id      = db.IntegerProperty()
    word            = db.StringProperty()
    pronounce       = db.StringProperty()
    meaning         = db.StringProperty(multiline=True)
    added           = db.DateTimeProperty(auto_now_add=True)
    served          = db.IntegerProperty()
    source_lang     = db.StringProperty()
    target_lang     = db.StringProperty()
