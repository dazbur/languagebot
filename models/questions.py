from google.appengine.ext import db
from models.learnlist import LearnList

class Question(db.Model):	
	# LearnList reference
    lli_ref             = db.ReferenceProperty(LearnList)
    question_sent       = db.DateProperty()
    twitter_user		= db.StringProperty()
    word				= db.StringProperty()
    answer_text			= db.StringProperty(multiline=True)
    # Twitter message id of the question sent
    question_message_id = db.IntegerProperty()
    answer_received     = db.DateProperty()
    answer_rating       = db.IntegerProperty()


    