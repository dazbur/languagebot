# coding=utf8
import logging
import simplejson

from google.appengine.ext import webapp

from current_session import current_user
from request_model_binder import model_from_request
from models.users import User
from models.learnlist import LearnList
from models.questions import Question
from models.dictionary import Dictionary
from controllers.incoming import parseMessage
from controllers.incoming import addNewWord


def getLatestAnswers(user):
        latest_answers = []
        l = {}
        questions = Question.all().\
            filter("twitter_user =", user.twitter).\
            filter("answer_received !=", None).\
            order("-answer_received").fetch(10)
        
        for q in questions:
            original = q.lli_ref.dict_entry.meaning.split(',')
            if q.answer_text:
                answer = q.answer_text.split(',')
            else:
                answer = ''

            original = [x.strip() for x in original]
            answer = [x.strip() for x in answer]
            
            match = set(original).intersection(set(answer))
            wrong = set(answer).difference(set(original))
            neutral = set(original).difference(set(answer))

            l = {"word":q.word,"answers":[],"rating":q.answer_rating}
            for i in match:
                l["answers"].append({"answer_text":i,"status":"match"})
            for i in neutral:
                l["answers"].append({"answer_text":i,"status":"neutral"})
            for i in wrong:
                l["answers"].append({"answer_text":i,"status":"wrong"})
            latest_answers.append(l)
        return simplejson.dumps(latest_answers)

class RPCHandler(webapp.RequestHandler):

    def get(self):
        result = None
        user = current_user()
        if user:	       
            action = self.request.get("action")
            if action == "getLatestAnswers":
                result = getLatestAnswers(user)
                self.response.out.write(result)
        else:
            self.error(404)
            exit




