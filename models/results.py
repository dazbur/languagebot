from google.appengine.ext import db

class TestResults(db.Model):
    word            = db.StringProperty()
    added           = db.DateTimeProperty()
    testresult      = db.IntegerProperty()
