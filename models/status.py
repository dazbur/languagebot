from google.appengine.ext import db


class TwitterStatus(db.Model):
    last_processed_id = db.IntegerProperty()
    last_direct_processed_id = db.IntegerProperty()
