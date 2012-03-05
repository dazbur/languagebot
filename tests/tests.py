# coding=utf8

import appcfg
appcfg.fix_sys_path()

import unittest
from google.appengine.ext   import db
from google.appengine.ext   import testbed
from django.utils           import simplejson

from controllers.incoming   import parseMessage 
from controllers.incoming   import processMessage
from controllers.learnlist  import get_next_interval
from controllers.learnlist  import add_new_item

from models.learnlist       import LearnList
from models.dictionary      import Dictionary
from models.users           import User

from twitter                import Status

class TestMessageParsing(unittest.TestCase):
    
    def testParsing1(self):
        message = "@LanguageBot capex: capital expenditures; капитальные затраты"
        result = parseMessage(message, "LanguageBot")
        self.assertEqual(result['word'], "capex")
        self.assertEqual(result['pronounce'], "")
        self.assertEqual(result['meaning'], "capital expenditures; капитальные затраты")

    def testParsing2(self):
        message = "  @languagebot lucrative[LOO-kruh-tiv]: profitable, moneymaking, remunerative "
        result = parseMessage(message, "LanguageBot")
        self.assertEqual(result['word'], "lucrative")
        self.assertEqual(result['pronounce'], "[LOO-kruh-tiv]")
        self.assertEqual(result['meaning'], "profitable, moneymaking, remunerative")

    def testParsing3(self):
        message = "вcе прекрасно, но бот твои сообщения не видит, нужно писать @LanguageBot :)"
        result = parseMessage(message, "LanguageBot")
        self.assertEqual(result, {})

    def testParsing4(self):
        message = "@LangBotStage You will be singled out for promotion in your work"
        result = parseMessage(message, "LanguageBot")
        self.assertEqual(result, {})


class TestProcessMessage(unittest.TestCase):
    
    def setUp(self):
        self.testbed = testbed.Testbed()
        self.testbed.activate()
        self.testbed.init_datastore_v3_stub()

        # Preparing datastore by prepopulating some data
        user = User()
        user.username = "ny_blin"
        user.twitter =  "ny_blin"
        user.put()

    def tearDown(self):
        self.testbed.deactivate()

    def testProcessMessageNormalAddForExistingUser(self):
        json_file = open("files/message1.json")
        message_json = simplejson.load(json_file)
        twitter_status = Status.NewFromJsonDict(message_json)
        processMessage(twitter_status)
        query = Dictionary.all()        
        results =   query.fetch(1)
        self.assertEqual(1, len(results))
        self.assertEqual("", results[0].pronounce)
        self.assertEqual("ny_blin", results[0].twitter_user)
        self.assertEqual(171632287904043008, results[0].message_id)
        self.assertEqual("ferociously(en)", results[0].word)
        self.assertEqual(u"жестоко, яростно, свирепо, дико, неистово. Ужасно, невыносимо.", results[0].meaning)
        self.assertEqual(0, results[0].served)
        self.assertEqual(None, results[0].source_lang)

    def testProcessMessageFromNonExistentUser(self):
        # Message from user "spammer" who doesn't exist in database
        # It must not be processed and must not be saved
        json_file = open("files/message2.json")
        message_json = simplejson.load(json_file)
        twitter_status = Status.NewFromJsonDict(message_json)
        processMessage(twitter_status)
        query = Dictionary.all()        
        results =   query.fetch(1)
        self.assertEqual(0, len(results))
        self.assertEqual("spammer", twitter_status.user.screen_name)

    def testProcessMessageFromExistingUserButNotReply(self):
        # Message from exsitng user, but not a reply
        # Such messages, like retweets must not me added
        json_file = open("files/message3.json")
        message_json = simplejson.load(json_file)
        twitter_status = Status.NewFromJsonDict(message_json)
        processMessage(twitter_status)
        query = Dictionary.all()        
        results =   query.fetch(1)
        self.assertEqual(0, len(results))
        self.assertEqual("ny_blin", twitter_status.user.screen_name)

        
        



        


class TestLearningList(unittest.TestCase):
    def setUp(self):
        # First, create an instance of the Testbed class.
        self.testbed = testbed.Testbed()
        # Then activate the testbed, which prepares the service stubs for use.
        self.testbed.activate()
        # Next, declare which service stubs you want to use.
        self.testbed.init_datastore_v3_stub()
    
    def tearDown(self):
        self.testbed.deactivate()
    
    def testGet_next_interval(self):
        l = [0,0,1,1]
        n = 0
        res = []
        prev_interval = 0
        prev_efactor = 0

        for i in l:
            n = n + 1
            r = get_next_interval(n, prev_interval, prev_efactor,\
            i)
            res.append(r)
            prev_interval = r["new_interval"]
            prev_efactor = r["new_efactor"]
        self.assertEqual(res, [{'new_interval': 2, 'new_efactor': 1.5},\
            {'new_interval': 3.0, 'new_efactor': 1.3},\
            {'new_interval': 3.9, 'new_efactor':1.4},\
            {'new_interval':5.46, 'new_efactor':1.5}])

    def testAddNewItem(self):
        add_new_item("da_zbur",1234)
        query = LearnList.all().filter('twitter_user =','da_zbur').\
            filter('word_id =',1234)
        results = query.fetch(2)
        self.assertEqual(1, len(results))
        self.assertEqual('da_zbur', results[0].twitter_user)
        self.assertEqual(1234, results[0].word_id)
        self.assertEqual(2, results[0].interval_days)
        self.assertEqual(1.5, results[0].efactor)
        self.assertEqual(0, results[0].total_served)
    
        
        
if __name__ == "__main__":
    unittest.main()        
        
