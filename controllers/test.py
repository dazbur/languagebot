from google.appengine.ext import webapp
from google.appengine.ext.webapp import template

from request_model_binder import model_from_request
from models.dictionary import Dictionary
from models.results import TestResults
from current_session import words_iter, set_words_iter


class TestScreen(webapp.RequestHandler):
    def __init__(self):
        i = words_iter()
        if i:
            self.words_iterator = i

        else:
            words = Dictionary.all().filter("twitter_user =", 'da_zbur')
            self.words_iterator = {"words":words,"pos":0}
            set_words_iter(self.words_iterator)

        
    def show_next_word(self):
        pos =  self.words_iterator["pos"]
        word = self.words_iterator["words"][pos]
        pos = pos + 1
        self.words_iterator["pos"] = pos
        set_words_iter(self.words_iterator)

        self.response.out.write(template.render("views/test.html", {"word":word}))

        
    def get(self):
        results = TestResults.all().order("added")
        res_dict = {}
        sorted_dates = []
        for res in results:
            date_str = str(res.added.year)+'-'+str(res.added.month)+'-'+str(res.added.day)
            if not date_str in sorted_dates:
                sorted_dates.append(date_str)
            if res_dict.has_key(date_str):
                res_dict[date_str].append(res.testresult)
            else:
                res_dict[date_str] = [res.testresult]

        for i in  sorted_dates:
            a = sum(res_dict[i]) / len(res_dict[i])
            print "sss"
            print "%s : %s" % (i, res_dict[i])
        

    def post(self):
        pos =  self.words_iterator["pos"] - 1
        word = self.words_iterator["words"][pos]

        test_result = TestResults()
        test_result.word = word.word
        test_result.added = word.added
        test_result.testresult= int(self.request.get("level"))
        test_result.put()
        self.show_next_word()
        


