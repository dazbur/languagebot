# coding=utf8
import json
import logging
from google.appengine.ext import webapp

from current_session import current_user
from controllers.incoming import parseMessage, parseOpt
from models.questions import Question
from models.dictionary import Dictionary
from models.learnlist import LearnList
from models.users import User


def getLatestAnswers(user):
        #TODO Need to make display follow the same comparison algorithm
        # as in calculateAnswerRating
        latest_answers = []
        l = {}
        questions = Question.all().\
            filter("twitter_user =", user.twitter).\
            filter("answer_received >", None).\
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

            l = {"word": q.word, "answers": [], "rating": q.answer_rating}
            for i in match:
                l["answers"].append({"answer_text": i, "status": "match"})
            for i in neutral:
                l["answers"].append({"answer_text": i, "status": "neutral"})
            for i in wrong:
                l["answers"].append({"answer_text": i, "status": "wrong"})
            latest_answers.append(l)
        return json.dumps(latest_answers)


def getUsers():
    userlist = []
    for user in User.all().order("-total_points").run():
        c = Dictionary.all().\
            filter("twitter_user =", user.twitter).count()
        userlist.append({"username": user.twitter, "points": user.total_points,
                        "wordscount": c})
    return json.dumps(userlist)


def editDictEntry(user, original_word, new_string):
    original_word, _ = parseOpt(original_word)
    dict_entry = Dictionary.all().\
        filter("twitter_user =", user.twitter).\
        filter("word =", original_word.strip()).get()
    if dict_entry:
        parsed_dict = parseMessage(new_string, '')
        if parsed_dict != {}:
            dict_entry.word = parsed_dict["word"]
            dict_entry.meaning = parsed_dict["meaning"]
            dict_entry.pronounce = parsed_dict["pronounce"]
            dict_entry.put()
    return json.dumps({})


def deleteDictEntry(user, word):
    word, _ = parseOpt(word)
    dict_entry = Dictionary.all().\
        filter("twitter_user =", user.twitter).\
        filter("word =", word.strip()).get()
    if dict_entry:
        lli = LearnList.all().\
            filter("dict_entry =", dict_entry.key()).get()
        for q in Question.all().filter("lli_ref =", lli.key()).run():
            q.delete()
        lli.delete()
        dict_entry.delete()
    return json.dumps({})


class RPCHandler(webapp.RequestHandler):

    def get(self):
        result = None
        user = current_user()
        if user:
            action = self.request.get("action")
            if action == "getLatestAnswers":
                result = getLatestAnswers(user)
                self.response.out.write(result)
            if action == "getUsers":
                result = getUsers()
                self.response.out.write(result)
        else:
            self.error(404)
            exit

    def post(self):
        result = None
        user = current_user()
        if user:
            action = self.request.get("action")
            if action == "editDictEntry":
                original_word = self.request.get("original")
                new_string = self.request.get("newentry")
                result = editDictEntry(user, original_word, new_string)
                self.response.out.write(result)
            if action == "deleteDictEntry":
                word = self.request.get("word")
                result = deleteDictEntry(user, word)
                self.response.out.write(result)
        else:
            self.error(404)
            exit
