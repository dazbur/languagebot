# coding=utf8

import appcfg
appcfg.fix_sys_path()

import unittest
import datetime
import time
from google.appengine.ext   import db
from google.appengine.ext   import testbed
from django.utils           import simplejson
from twitter_mockup         import TwitterMockup

from controllers.incoming   import parseMessage 
from controllers.incoming   import processMessage
from controllers.learnlist  import getNextInterval
from controllers.learnlist  import addNewLearnListItem
from controllers.learnlist  import buildDailyList
from controllers.learnlist  import prepareTwitterMessage
from controllers.learnlist  import sendMessages
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
        self.assertEqual(u"жестоко, яростно, свирепо, дико, неистово. Ужасно, невыносимо.",\
         results[0].meaning)
        self.assertEqual(0, results[0].served)
        self.assertEqual(None, results[0].source_lang)
        # Test integration with LearnList
        query = LearnList.all()
        ll_results = query.fetch(2)
        self.assertEqual(1, len(ll_results))
        # Check if LearnList references same object
        self.assertEqual(ll_results[0].dict_entry.key(), results[0].key())

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
        # Test integration with LearnList
        query = LearnList.all()
        ll_results = query.fetch(2)
        self.assertEqual(0, len(ll_results))

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
        # Test integration with LearnList
        query = LearnList.all()
        ll_results = query.fetch(2)
        self.assertEqual(0, len(ll_results))


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

    # Helper methods for sample data loadinf: createUser,
    # createDictEntry, createLearnListItem
    def createUser(self, twitter_user, account_status, messages_per_day):
        user = User()
        user.twitter = twitter_user
        user.username = twitter_user
        user.account_status = account_status
        user.messages_per_day = messages_per_day
        user.put()
        return user

    def createDictEntry(self, twitter_user, message_id, word, meaning,\
         pronounce=""):
        dictEntry = Dictionary()
        dictEntry.twitter_user = twitter_user
        dictEntry.message_id = message_id
        dictEntry.word = word
        dictEntry.pronounce = pronounce
        dictEntry.meaning = meaning
        dictEntry.served = 0
        dictEntry.source_lang = ""
        dictEntry.target_lang = ""
        dictEntry.put()
        return dictEntry

    def createLearnListItem(self, twitter_user, dict_entry, next_serve_date):
        learnListItem = LearnList()
        learnListItem.twitter_user = twitter_user
        learnListItem.dict_entry = dict_entry
        learnListItem.next_serve_date = next_serve_date
        learnListItem.next_serve_time = 0
        learnListItem.total_served = 0
        learnListItem.put()
        return learnListItem        
    
    def testGetNextInterval(self):
        l = [0,0,1,1]
        n = 0
        res = []
        prev_interval = 0
        prev_efactor = 0

        for i in l:
            n = n + 1
            r = getNextInterval(n, prev_interval, prev_efactor,\
            i)
            res.append(r)
            prev_interval = r["new_interval"]
            prev_efactor = r["new_efactor"]
        self.assertEqual(res, [{'new_interval': 2, 'new_efactor': 1.5},\
            {'new_interval': 3.0, 'new_efactor': 1.3},\
            {'new_interval': 3.9, 'new_efactor':1.4},\
            {'new_interval':5.46, 'new_efactor':1.5}])

    def testAddNewLearnListItem(self):
        # Preparing datastore by prepopulating some data
        user = User()
        user.username = "ny_blin"
        user.twitter =  "ny_blin"
        user.put()
        json_file = open("files/message1.json")
        message_json = simplejson.load(json_file)
        twitter_status = Status.NewFromJsonDict(message_json)
        processMessage(twitter_status)
        query = LearnList.all().filter('twitter_user =','ny_blin')
        results = query.fetch(2)
        self.assertEqual(1, len(results))
        self.assertEqual('ny_blin', results[0].twitter_user)
        self.assertEqual(2, results[0].interval_days)
        self.assertEqual(1.5, results[0].efactor)
        self.assertEqual(0, results[0].total_served)
        now_plus_two = datetime.date.today() +\
            datetime.timedelta(days=2)
        self.assertEqual(now_plus_two, results[0].next_serve_date)      

    def testBuildDailyList(self):
        # Prepare 4 users: 3 active one disabled, one with 
        # limit of messages per day
        self.createUser("ny_blin","enabled",10)
        self.createUser("da_zbur","enabled",10)
        self.createUser("mr_qizz","disabled",10)
        self.createUser("mr_2_per_day","enabled",2)

        d1 = self.createDictEntry("ny_blin",1,"cat",u"котик")
        d2 = self.createDictEntry("da_zbur",2,"dog",u"собачка")
        d3 = self.createDictEntry("da_zbur",3,"heron",u"цапля")
        d4 = self.createDictEntry("mr_qizz",4,"raccoon",u"енотик")

        today = datetime.date.today()
        tomorrow = today + datetime.timedelta(days=1)
        current_timestamp = int(time.time())

        self.createLearnListItem("ny_blin",d1,today)
        self.createLearnListItem("da_zbur",d2,today)
        self.createLearnListItem("da_zbur",d3,today)
        self.createLearnListItem("da_zbur",d4,tomorrow)
        self.createLearnListItem("mr_qizz",d4,today)
        self.createLearnListItem("mr_2_per_day",d1,today)
        self.createLearnListItem("mr_2_per_day",d2,today)
        self.createLearnListItem("mr_2_per_day",d3,today)
        self.createLearnListItem("mr_2_per_day",d4,today)
        
        buildDailyList(today)
        dailyList = []
        for i in  LearnList.all().filter("next_serve_date =",today).run():
            dailyList.append(i)
        self.assertEqual(6, len(dailyList))
        
        self.assertEqual("ny_blin", dailyList[0].twitter_user)
        self.assertEqual(d1.key(), dailyList[0].dict_entry.key())
        self.assertNotEqual(0, dailyList[0].next_serve_time)
        # Check if new timestamp is within next 24 hours
        self.assertTrue(current_timestamp+24*3600 > dailyList[0].next_serve_time)
        self.assertTrue(current_timestamp < dailyList[0].next_serve_time)
        
        self.assertEqual("da_zbur", dailyList[1].twitter_user)
        self.assertEqual(d2.key(), dailyList[1].dict_entry.key())
        self.assertNotEqual(0, dailyList[1].next_serve_time)

        self.assertEqual("da_zbur", dailyList[2].twitter_user)
        self.assertEqual(d3.key(), dailyList[2].dict_entry.key())
        self.assertNotEqual(0, dailyList[2].next_serve_time)

        self.assertEqual("mr_qizz", dailyList[3].twitter_user)
        self.assertEqual(0, dailyList[3].next_serve_time)
        
        self.assertEqual("mr_2_per_day", dailyList[4].twitter_user)
        self.assertEqual(d1.key(), dailyList[4].dict_entry.key())
        self.assertNotEqual(0, dailyList[4].next_serve_time)

        self.assertEqual("mr_2_per_day", dailyList[5].twitter_user)
        self.assertEqual(d2.key(), dailyList[5].dict_entry.key())
        self.assertNotEqual(0, dailyList[5].next_serve_time)

        # Now let's check if 2 messages for mr_2_per day got rescheduled 
        # for tomorrow. Plus there is a message for da_zbur scheduled for
        # tomorrow as well
        buildDailyList(tomorrow)
        dailyList = []
        for i in  LearnList.all().filter("next_serve_date =",tomorrow).run():
            dailyList.append(i)
        self.assertEqual(3, len(dailyList))

        self.assertEqual("da_zbur", dailyList[0].twitter_user)
        self.assertEqual(d4.key(), dailyList[0].dict_entry.key())
        self.assertNotEqual(0, dailyList[0].next_serve_time)
        

        self.assertEqual("mr_2_per_day", dailyList[1].twitter_user)
        self.assertEqual(d3.key(), dailyList[1].dict_entry.key())
        self.assertNotEqual(0, dailyList[1].next_serve_time)

        self.assertEqual("mr_2_per_day", dailyList[2].twitter_user)
        self.assertEqual(d4.key(), dailyList[2].dict_entry.key())
        self.assertNotEqual(0, dailyList[2].next_serve_time)

        # Finally let's check that building tomorrow's list didn't screw up
        # the today's list        
        dailyList = []
        for i in  LearnList.all().filter("next_serve_date =",today).run():
            dailyList.append(i)
        self.assertEqual(6, len(dailyList))

    def testPrepareTwitterMessage(self):
        self.createUser("da_zbur","enabled",10)
        # Test word with pronounciation
        d1 = self.createDictEntry("da_zbur",2,"lucrative",\
            u"profitable, moneymaking, remunerative","[LOO-kruh-tiv]")
        # Test word without pronounciation
        d2 = self.createDictEntry("da_zbur",2,"ferociously(en)",\
            u"жестоко, яростно, свирепо, дико, неистово. Ужасно, невыносимо.")
        today = datetime.date.today()    
        l1 = self.createLearnListItem("da_zbur",d1,today)
        l2 = self.createLearnListItem("da_zbur",d2,today)
        message = prepareTwitterMessage(l1)
        message2 = prepareTwitterMessage(l2)

        self.assertEqual("@da_zbur lucrative[LOO-kruh-tiv]: profitable, \
moneymaking, remunerative [1]", message)
        self.assertEqual(u"@da_zbur ferociously(en): жестоко, \
яростно, свирепо, дико, неистово. Ужасно, невыносимо. [1]", message2)

    def testSendMessages(self):
        Twitter = TwitterMockup()
        message = sendMessages(Twitter)
        self.assertEqual("blah!", message)


        


        
if __name__ == "__main__":
    unittest.main()        
        
