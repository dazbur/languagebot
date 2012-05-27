from google.appengine.ext import db
from models.dictionary import Dictionary

class LearnList(db.Model):
    twitter_user       = db.StringProperty()
    dict_entry         = db.ReferenceProperty(Dictionary)
    interval_days      = db.IntegerProperty()
    efactor            = db.FloatProperty()
    next_serve_time    = db.IntegerProperty()
    next_serve_date    = db.DateProperty()
    total_served       = db.IntegerProperty()   
