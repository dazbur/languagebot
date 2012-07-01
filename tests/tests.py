# coding=utf8

import appcfg
import logging
appcfg.fix_sys_path()

import unittest
import datetime
import time
from google.appengine.ext   import webapp
from google.appengine.ext   import db
from google.appengine.ext   import testbed
from django.utils           import simplejson
from twitter_mockup         import TwitterMockup

from controllers.incoming   import parseMessage 
from controllers.incoming   import processMessage
from controllers.incoming   import checkForAnswer
from controllers.learnlist  import getNextInterval
from controllers.learnlist  import addNewLearnListItem
from controllers.learnlist  import buildDailyList
from controllers.learnlist  import prepareTwitterMessage
from controllers.learnlist  import prepareQuestionMessage
from controllers.learnlist  import sendMessagesGenerator
from controllers.details    import getParameters
from controllers.learnlist  import calculateAnswerRating
from models.learnlist       import LearnList
from models.dictionary      import Dictionary
from models.users           import User
from models.questions       import Question

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

    def createLearnListItem(self, twitter_user, dict_entry,\
        next_serve_date, next_serve_time=0):
        learnListItem = LearnList()
        learnListItem.twitter_user = twitter_user
        learnListItem.dict_entry = dict_entry
        learnListItem.next_serve_date = next_serve_date
        learnListItem.next_serve_time = next_serve_time
        learnListItem.total_served = 1
        learnListItem.put()
        return learnListItem        
    
    def testGetNextInterval(self):
        l = [60,55,90,87]
        n = 0
        res = []
        prev_interval = 0
        prev_efactor = 0

        for i in l:
            n = n + 1
            r = getNextInterval(n, prev_interval, prev_efactor,i)
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
        self.assertEqual(1, results[0].total_served)
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
        
        buildDailyList(today, logging)
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
        buildDailyList(tomorrow, logging)
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
        today = datetime.date.today()

        self.createUser("da_zbur","enabled",10)
        d1 = self.createDictEntry("da_zbur",2,"lucrative",\
            u"profitable, moneymaking, remunerative","[LOO-kruh-tiv]")
        current_time = int(time.time())
        l1 = self.createLearnListItem("da_zbur",d1,today, current_time)
        messages_generator = sendMessagesGenerator(Twitter, logging)
        m_list = []
        while True:
            try:
                message = messages_generator.next()
            except StopIteration:
                break
            m_list.append(message)
        # Testing that LearnListItem was rescheduled properly
        ll = LearnList.all().fetch(1)[0]
        self.assertEqual(2, ll.interval_days)
        self.assertEqual(1.5, ll.efactor)
        self.assertEqual(2, ll.total_served)
        self.assertEqual(today + datetime.timedelta(days=2), ll.next_serve_date)
        self.assertEqual(None, ll.next_serve_time)

        self.assertEqual(["@da_zbur lucrative[LOO-kruh-tiv]: profitable, \
moneymaking, remunerative [1]"], m_list)

    def testSendMessagesDisabled(self):
        # Testing that message for disabled user is not sent
        # But rescheduled to next day
        Twitter = TwitterMockup()
        today = datetime.date.today()

        self.createUser("da_zbur","disabled",10)
        d1 = self.createDictEntry("da_zbur",2,"lucrative",\
            u"profitable, moneymaking, remunerative","[LOO-kruh-tiv]")
        current_time = int(time.time())
        l1 = self.createLearnListItem("da_zbur",d1,today, current_time)
        messages_generator = sendMessagesGenerator(Twitter, logging)
        m_list = []
        while True:
            try:
                message = messages_generator.next()
            except StopIteration:
                break
            m_list.append(message)
        # Testing that LearnListItem was rescheduled properly
        ll = LearnList.all().fetch(1)[0]
        self.assertEqual(1, ll.total_served)
        self.assertEqual(today + datetime.timedelta(days=1), ll.next_serve_date)
        self.assertEqual([None], m_list)
        self.assertEqual(None, ll.next_serve_time)

    def testDetailsViewGetParameters(self):
        today = datetime.date.today()
        date2 = today + datetime.timedelta(days=5)
        today_str = today.strftime("%B %d")
        date2_str = date2.strftime("%B %d")

        u = self.createUser("da_zbur","enabled",10)
        d1 = self.createDictEntry("da_zbur",2,"lucrative",\
            u"profitable, moneymaking, remunerative","[LOO-kruh-tiv]")
        d2 = self.createDictEntry("da_zbur",2,"amaranthine",\
            u"неувядающий, вечный")

        current_time = int(time.time())
        l1 = self.createLearnListItem("da_zbur",d1, today, current_time)
        l2 = self.createLearnListItem("da_zbur",d2, date2)
        params = getParameters(u)

        self.assertEqual(["lucrative [LOO-kruh-tiv]","profitable, moneymaking, remunerative",
            today_str], params["dict_row"][0])
        self.assertEqual(["amaranthine ",u"неувядающий, вечный",
            date2_str], params["dict_row"][1])

    def testCalculateAnswerRating(self):
        original = 'profitable, moneymaking, remunerative'

        # No match -- 0%
        res = calculateAnswerRating(original, '-');
        self.assertEqual(0, res)
        # One good match -- 80%
        res = calculateAnswerRating(original, 'moneymaking');
        self.assertEqual(80, res)
        # One partially good match < 80%
        res = calculateAnswerRating(original, 'profetabl');
        self.assertTrue(res < 80)
        # Full match -- 100%
        res = calculateAnswerRating(original, 'profitable,moneymaking,remunerative');
        self.assertEqual(100, res)
        # Full match with errors  80<= res <100
        res = calculateAnswerRating(original, 'profitable,monemeking');
        self.assertTrue(res <100 and res >= 80)

    def testQuestionAdding(self):
        # This is testing buildDailyList method to make sure that
        # every second serving a Question opbject is added. 
        today = datetime.date.today()
        u = self.createUser("da_zbur","enabled",10)
        d1 = self.createDictEntry("da_zbur",2,"dog",u"собачка")
        lli = self.createLearnListItem("da_zbur",d1,today)
        u.use_questions = "yes"
        u.put()
        lli.total_served = 6 
        lli.put()
        buildDailyList(today, logging)
        question_list = []
        for q in Question.all().filter("lli_ref =", lli):
            question_list.append(q)
        self.assertEqual(1, len(question_list))
        self.assertEqual(d1.key(), question_list[0].lli_ref.dict_entry.key())

    def testPrepareQuestionMessage(self):
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
        message = prepareQuestionMessage(l1)
        message2 = prepareQuestionMessage(l2)

        self.assertEqual("@da_zbur lucrative[LOO-kruh-tiv]:? [1]", message)
        self.assertEqual(u"@da_zbur ferociously(en):? [1]", message2)

    def testTwitterMockupStatusId(self):
        Twitter = TwitterMockup()
        status = Twitter.api.PostUpdate("This is a test message")
        self.assertEqual(2042, status.id)

    def testSendQuestion(self):
        Twitter = TwitterMockup()
        today = datetime.date.today()
        current_time = int(time.time())
        
        u = self.createUser("da_zbur","enabled",10)
        u.use_questions = "yes"
        u.put()

        d1 = self.createDictEntry("da_zbur",2,"lucrative",\
            u"profitable, moneymaking, remunerative","[LOO-kruh-tiv]")
        d2 = self.createDictEntry("da_zbur",2,"ferociously(en)",\
            u"жестоко, яростно, свирепо, дико, неистово. Ужасно, невыносимо.")

        l1 = self.createLearnListItem("da_zbur",d1,today,current_time)
        l2 = self.createLearnListItem("da_zbur",d2,today,current_time)        
        
        # forcing question to be asked        
        l1.total_served = 4
        l1.put()
       
        buildDailyList(today, logging)
        # Keep in mind building daily list means serve times will be 
        # randomly distributed throighout the day!
        l1.next_serve_time = current_time
        l2.next_serve_time = current_time
        l2.put()
        l1.put()

        messages_generator = sendMessagesGenerator(Twitter, logging)
        m_list = []
        while True:
            try:
                message = messages_generator.next()
            except StopIteration:
                break
            m_list.append(message)
        # Testing that proper Question entity was created
        q = Question.all().fetch(1)[0]
        self.assertEqual(3492, q.question_message_id)
        self.assertEqual(today, q.question_sent)
        self.assertEqual(4, l1.total_served)
        self.assertEqual(None, q.lli_ref.next_serve_time)
        self.assertEqual("@da_zbur lucrative[LOO-kruh-tiv]:? [4]", m_list[0])

    def testCheckForAnswer(self):
        # I should collapse this code into something reusable
        Twitter = TwitterMockup()
        today = datetime.date.today()
        current_time = int(time.time())
        
        u = self.createUser("da_zbur","enabled",10)
        u.use_questions = "yes"
        u.put()

        d1 = self.createDictEntry("da_zbur",2,"lucrative",\
            u"profitable, moneymaking, remunerative","[LOO-kruh-tiv]")
        
        l1 = self.createLearnListItem("da_zbur",d1,today,current_time)
        
        # forcing question to be asked        
        l1.total_served = 4
        l1.put()
       
        buildDailyList(today, logging)
        # Keep in mind building daily list means serve times will be 
        # randomly distributed throighout the day!
        l1.next_serve_time = current_time
        l1.put()

        messages_generator = sendMessagesGenerator(Twitter, logging)
        m_list = []
        while True:
            try:
                message = messages_generator.next()
            except StopIteration:
                break
            m_list.append(message)

        q = Question.all().fetch(1)[0]

        # Question for word d1 was genereated and sent
        # Now user prepares an answer
        answer = "@LanguageBot moneymaking, profitable"
        m = Twitter.api.PostUpdate(answer, in_reply_to_s_id=q.question_message_id)
        q2 = checkForAnswer(u, m)
        self.assertEqual(q.key(), q2.key())

    def testAnswersIntegration(self):
        # I should collapse this code into something reusable

        # This is a big integration test for question/answers
        # Idea is that there are two answers: good and bad
        # Need to check if messages are being properly rescheduled and send

        Twitter = TwitterMockup()
        today = datetime.date.today()
        current_time = int(time.time())
        
        u = self.createUser("da_zbur","enabled",10)
        u.use_questions = "yes"
        u.put()

        d1 = self.createDictEntry("da_zbur",2,"lucrative",\
            u"profitable, moneymaking, remunerative","[LOO-kruh-tiv]")
        d2 = self.createDictEntry("da_zbur",2,"ferociously(en)",\
            u"жестоко, яростно, свирепо, дико, неистово. Ужасно, невыносимо.")

        l1 = self.createLearnListItem("da_zbur",d1,today,current_time)
        l2 = self.createLearnListItem("da_zbur",d2,today,current_time)        
        
        # forcing question to be asked        
        l1.total_served = 4
        l2.total_served = 6
        l1.interval_days = 3.2
        l1.efactor = 1.3
        l2.interval_days = 7.4
        l2.efactor = 0.98
        l1.put()
        l2.put()
       
        buildDailyList(today, logging)
        # Keep in mind building daily list means serve times will be 
        # randomly distributed throighout the day!
        l1.next_serve_time = current_time
        l2.next_serve_time = current_time
        l2.put()
        l1.put()

        messages_generator = sendMessagesGenerator(Twitter, logging)
        m_list = []
        while True:
            try:
                message = messages_generator.next()
            except StopIteration:
                break
            m_list.append(message)

        q1 = Question.all().fetch(2)[0]
        q2 = Question.all().fetch(2)[1]

        # This is a good answer
        a1 = "@LanguageBot moneymaking, profitable"
        # This is crappy answer
        a2 = u"@LanguageBot ---"
        m1 = Twitter.api.PostUpdate(a1, in_reply_to_s_id=q1.question_message_id,\
            user_screen_name="da_zbur",in_reply_to_screen_name="LanguageBot")
        m2 = Twitter.api.PostUpdate(a2, in_reply_to_s_id=q2.question_message_id,\
            user_screen_name="da_zbur",in_reply_to_screen_name="LanguageBot")
        processMessage(m1)
        processMessage(m2)

        q1 = Question.all().fetch(2)[0]
        q2 = Question.all().fetch(2)[1]
        
        # For good question
        self.assertEqual(today, q1.answer_received)
        self.assertEqual(90, q1.answer_rating)
        self.assertEqual(90, q1.lli_ref.latest_answer_rating)
        self.assertEqual(None, q1.lli_ref.next_serve_time)
        self.assertEqual(1.4, q1.lli_ref.efactor)
        self.assertEqual(3.2*1.3, q1.lli_ref.interval_days)

        # For bad question
        self.assertEqual(today, q2.answer_received)
        self.assertEqual(0, q2.answer_rating)
        self.assertEqual(0, q2.lli_ref.latest_answer_rating)
        self.assertEqual(0, q2.lli_ref.next_serve_time)
        self.assertEqual(today, q2.lli_ref.next_serve_date)
        
        




        

        
if __name__ == "__main__":
    unittest.main()        
        
