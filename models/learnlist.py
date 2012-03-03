from google.appengine.ext import db

class LearnList(db.Model):
    twitter_user       = db.StringProperty()
    word_id            = db.IntegerProperty()
    interval_days      = db.IntegerProperty()
    efactor            = db.FloatProperty()
    next_serve_date    = db.DateTimeProperty()
    total_served       = db.IntegerProperty()   
