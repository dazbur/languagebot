# coding=utf8

import appcfg
import logging
appcfg.fix_sys_path()

import unittest
import datetime
import time
import sys
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
from controllers.learnlist  import calculateAnswerRating
from controllers.learnlist  import prepareEmailMessagesGenerator
from controllers.learnlist  import acknowledgeQuestions
from controllers.vocabulary import getParameters
from controllers.rpchandler import getLatestAnswers
from controllers.rpchandler import deleteDictEntry
from controllers.rpchandler import editDictEntry
from models.learnlist       import LearnList
from models.dictionary      import Dictionary
from models.users           import User
from models.questions       import Question
from langbot_globals        import *

from twitter                import Status, DirectMessage

class TestMessageParsing(unittest.TestCase):
    
    def testParsing1(self):
        message = "@LanguageBot capex: capital expenditures; капитальные затраты"
        result = parseMessage(message, "LanguageBot")
        self.assertEqual(result['word'], "capex")
        self.assertEqual(result['pronounce'], "")
        self.assertEqual(result['meaning'], "capital expenditures, капитальные затраты")

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
        user.username = "da_zbur"
        user.twitter =  "da_zbur"
        user.total_points = 0
        user.put()

    def tearDown(self):
        self.testbed.deactivate()

    def testProcessMessageNormalAddForExistingUser(self):
        json_file = open("files/direct_message1.json")
        message_json = simplejson.load(json_file)
        twitter_dm = DirectMessage.NewFromJsonDict(message_json)
        processMessage(twitter_dm)
        query = Dictionary.all()        
        results =   query.fetch(1)
        self.assertEqual(1, len(results))
        self.assertEqual("", results[0].pronounce)
        self.assertEqual("da_zbur", results[0].twitter_user)
        self.assertEqual(289180663729512448L, results[0].message_id)
        self.assertEqual("to advet", results[0].word)
        self.assertEqual(u"обращаться к,ссылаться на",\
         results[0].meaning)
        self.assertEqual(0, results[0].served)
        self.assertEqual(None, results[0].source_lang)
        self.assertEqual(1, User.all().filter("twitter =",\
         "da_zbur").get().total_points)
        # Test integration with LearnList
        query = LearnList.all()
        ll_results = query.fetch(2)
        self.assertEqual(1, len(ll_results))
        # Check if LearnList references same object
        self.assertEqual(ll_results[0].dict_entry.key(), results[0].key())

    def testProcessDuplicateWord(self):
        json_file = open("files/direct_message1.json")
        message_json = simplejson.load(json_file)
        twitter_dm = DirectMessage.NewFromJsonDict(message_json)
        processMessage(twitter_dm)
        
        json_file = open("files/direct_message1.json")
        message_json = simplejson.load(json_file)
        twitter_dm = DirectMessage.NewFromJsonDict(message_json)
        processMessage(twitter_dm)
        
        query = Dictionary.all()        
        results =   query.fetch(1)
        self.assertEqual(1, len(results))

    def testProcessMessageFromNonExistentUser(self):
        # Message from user "spammer" who doesn't exist in database
        # It must not be processed and must not be saved
        json_file = open("files/direct_message_spammer.json")
        message_json = simplejson.load(json_file)
        twitter_dm = DirectMessage.NewFromJsonDict(message_json)
        processMessage(twitter_dm)
        query = Dictionary.all()        
        results =   query.fetch(1)
        self.assertEqual(0, len(results))
        self.assertEqual("spammer", twitter_dm.sender_screen_name)
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
        user.total_points = 0
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
        l = [-2,-4,6,0]
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
        self.assertEqual(res, [{'new_interval': 2.5, 'new_efactor': 1.5},\
            {'new_interval': 3.75, 'new_efactor': 1.3},\
            {'new_interval': 4.88, 'new_efactor':1.6},\
            {'new_interval':7.81, 'new_efactor':1.9}])

    def testAddNewLearnListItem(self):
        # Preparing datastore by prepopulating some data
        user = User()
        user.username = "ny_blin"
        user.twitter =  "ny_blin"
        user.total_points = 0
        user.put()
        json_file = open("files/direct_message2.json")
        message_json = simplejson.load(json_file)
        twitter_dm = DirectMessage.NewFromJsonDict(message_json)
        processMessage(twitter_dm)
        query = LearnList.all().filter('twitter_user =','ny_blin')
        results = query.fetch(2)
        self.assertEqual(1, len(results))
        self.assertEqual('ny_blin', results[0].twitter_user)
        self.assertEqual(2.5, results[0].interval_days)
        self.assertEqual(1.5, results[0].efactor)
        self.assertEqual(1, results[0].total_served)
        now_plus_two = datetime.date.today() +\
            datetime.timedelta(days=2)
        self.assertEqual(now_plus_two, results[0].next_serve_date)      

    def testBuildDailyList(self):
        # Prepare 4 users: 3 active one disabled, one with 
        # limit of messages per day
        self.createUser("ny_blin","enabled",10)
        u = self.createUser("da_zbur","enabled",10)
        # Change timezone for da_zbur
        u.utc_offset = -5
        u.put()

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

        self.assertEqual("lucrative[LOO-kruh-tiv]: profitable, \
moneymaking, remunerative [1]", message)
        self.assertEqual(u"ferociously(en): жестоко, \
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
        self.assertEqual(2.5, ll.interval_days)
        self.assertEqual(1.5, ll.efactor)
        self.assertEqual(2, ll.total_served)
        self.assertEqual(today + datetime.timedelta(days=2), ll.next_serve_date)
        self.assertEqual(sys.maxint, ll.next_serve_time)

        self.assertEqual(["lucrative[LOO-kruh-tiv]: profitable, \
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
        self.assertEqual(sys.maxint, ll.next_serve_time)

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

        # No match == -POINTS_PER_GUESS
        res = calculateAnswerRating(original, '-');
        self.assertEqual(-POINTS_PER_GUESS, res)
        # One good match == POINTS_PER_GUESS 
        res = calculateAnswerRating(original, 'moneymaking');
        self.assertEqual(POINTS_PER_GUESS, res)
        # One partially good match 
        res = calculateAnswerRating(original, 'profetabl');
        self.assertTrue(POINTS_PER_GUESS, res)
        # Full match PPGx1 + PPGx2 + PPGx3
        res = calculateAnswerRating(original,\
             'profitable,moneymaking,remunerative');
        self.assertEqual(POINTS_PER_GUESS + 2*POINTS_PER_GUESS+\
            3*POINTS_PER_GUESS, res)
        # Full match with errors  80<= res <100
        res = calculateAnswerRating(original, 'profitable,monemeking');
        self.assertTrue(POINTS_PER_GUESS, res)
        # One correct and one wrong
        res = calculateAnswerRating(original, 'monemeking, expensive');
        self.assertTrue(POINTS_PER_GUESS, res)

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

        self.assertEqual(u"lucrative[LOO-kruh-tiv]:? [1]", message)
        self.assertEqual(u"ferociously(en):? [1]", message2)

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
        self.assertEqual(2653, q.question_message_id)
        self.assertEqual(today, q.question_sent)
        self.assertEqual(4, l1.total_served)
        self.assertEqual(sys.maxint, q.lli_ref.next_serve_time)
        self.assertEqual("lucrative[LOO-kruh-tiv]:? [4]", m_list[0])

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
        answer = "lucrative: moneymaking, profitable"
        m = Twitter.api.PostUpdate(answer, in_reply_to_s_id=q.question_message_id)
        parsed_dict = parseMessage(m.text)
        q2 = checkForAnswer(parsed_dict, u.twitter)
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
        d3 = self.createDictEntry("da_zbur",2,"confounder",\
            u"искажающий результаты фактор")

        l1 = self.createLearnListItem("da_zbur",d1,today,current_time)
        l2 = self.createLearnListItem("da_zbur",d2,today,current_time)        
        l3 = self.createLearnListItem("da_zbur",d3,today,current_time)

        # forcing question to be asked        
        l1.total_served = 4
        l2.total_served = 6
        l3.total_served = 8
        l1.interval_days = 3.2
        l1.efactor = 1.3
        l2.interval_days = 7.4
        l2.efactor = 0.98
        l3.interval_days = 17.4
        l3.efactor = 1.98
        l1.put()
        l2.put()
        l3.put()
       
        buildDailyList(today, logging)
        # Keep in mind building daily list means serve times will be 
        # randomly distributed throighout the day!
        l1.next_serve_time = current_time
        l2.next_serve_time = current_time
        l3.next_serve_time = current_time

        l2.put()
        l1.put()
        l3.put()

        messages_generator = sendMessagesGenerator(Twitter, logging)
        m_list = []
        while True:
            try:
                message = messages_generator.next()
            except StopIteration:
                break
            m_list.append(message)
       
        q1 = Question.all().fetch(3)[0]
        q2 = Question.all().fetch(3)[1]
        q3 = Question.all().fetch(3)[2]


        # This is a good answer
        a1 = "lucrative: moneymaking, profitable"
        # This is crappy answer
        a2 = u"ferociously(en): ---"
        # This is multiword answer
        a3 = u"Confounder: искажающий результаты фактор"
        m1 = Twitter.api.PostDirectMessage("LangBotStage", a1, "da_zbur")
        m2 = Twitter.api.PostDirectMessage("LangBotStage", a2, "da_zbur")
        m3 = Twitter.api.PostDirectMessage("LangBotStage", a3, "da_zbur")
        processMessage(m1)
        processMessage(m2)
        processMessage(m3)

        q1 = Question.all().fetch(3)[0]
        q2 = Question.all().fetch(3)[1]
        q3 = Question.all().fetch(3)[2]

        # For good question
        self.assertEqual(today, q1.answer_received)
        self.assertEqual(6, q1.answer_rating)
        self.assertEqual(6, q1.lli_ref.latest_answer_rating)
        self.assertEqual(sys.maxint, q1.lli_ref.next_serve_time)
        self.assertEqual(1.6, q1.lli_ref.efactor)
        self.assertEqual(3.2*1.3, q1.lli_ref.interval_days)
        self.assertEqual("moneymaking, profitable", q1.answer_text)

        # For bad question
        self.assertEqual(today, q2.answer_received)
        self.assertEqual(-2, q2.answer_rating)
        self.assertEqual(-2, q2.lli_ref.latest_answer_rating)
        self.assertEqual(0, q2.lli_ref.next_serve_time)
        self.assertEqual(today, q2.lli_ref.next_serve_date)
        self.assertEqual("---", q2.answer_text)

        # For multiword answer
        self.assertEqual(today, q3.answer_received)
        self.assertEqual(2, q3.answer_rating)
        self.assertEqual(2, q3.lli_ref.latest_answer_rating)
        self.assertEqual(sys.maxint, q3.lli_ref.next_serve_time)
        self.assertEqual(u"искажающий результаты фактор", q3.answer_text)

        # Check total user points, assuming he had 0
        self.assertEqual(6
            , User.all().filter("twitter =","da_zbur").\
            get().total_points)
        
    def testPrepareEmailMesaage(self):
        today = datetime.date.today()
        current_time = int(time.time())
        u = self.createUser("da_zbur","enabled",10)
        u.use_questions = "yes"
        u.use_daily_email = "yes"
        u.email = "zburivsky@gmail.com"
        u.put()

        d1 = self.createDictEntry("da_zbur",2,"lucrative",\
            u"profitable, moneymaking, remunerative","[LOO-kruh-tiv]")
        d2 = self.createDictEntry("da_zbur",2,"ferociously(en)",\
            u"жестоко, яростно, свирепо, дико, неистово. Ужасно, невыносимо.")

        g = prepareEmailMessagesGenerator()

        l1 = self.createLearnListItem("da_zbur",d1,today,current_time)
        l2 = self.createLearnListItem("da_zbur",d2,today,current_time)
        while True:
            try:
                message = g.next()
                
            except StopIteration:
                break
        f = open("files/email1.html","r")
        email = f.read()
        self.assertEqual({"email":"zburivsky@gmail.com", "message":email}, message)

    def testQuestionAcknowledge(self):
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
        l2.put()
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

        # Now imagine those question didn't get answers before next daily
        # list is build
        acknowledgeQuestions(today)

        unack_count = Question.all().filter("answer_received =", None).count()
        self.assertEqual(0, unack_count) 

class TestRPC(unittest.TestCase):
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

    def createQuestion(self, lli_ref, question_sent, twitter_user,\
        word, answer_text, question_message_id, answer_received, answer_rating):
        q = Question()
        q.lli_ref = lli_ref
        q.question_sent = question_sent
        q.twitter_user = twitter_user
        q.word = word
        q.answer_text = answer_text
        q.question_message_id = question_message_id
        q.answer_received = answer_received
        q.answer_rating = answer_rating
        q.put()
        return q

    def testGetLatestAnswers(self):
        today = datetime.date.today()
        current_time = int(time.time())

        u = self.createUser("da_zbur", "enabled", 10)
        u.use_questions = "yes"
        u.put()

        d1 = self.createDictEntry("da_zbur", 2, "lucrative", \
            u"profitable, moneymaking, remunerative", "[LOO-kruh-tiv]")
        d2 = self.createDictEntry("da_zbur", 2, "ferociously(en)", \
            u"жестоко, яростно, свирепо, дико, неистово. Ужасно, невыносимо.")

        l1 = self.createLearnListItem("da_zbur", d1, today, current_time)
        l2 = self.createLearnListItem("da_zbur", d2, today, current_time)

        self.createQuestion(l1, today, "da_zbur", d1.word,
             "profitable, moneymaking", 1, today, 100)
        self.createQuestion(l2, today, "da_zbur", d2.word,
             u"лажа", 2, today, 0)
        resultJSON = getLatestAnswers(u)
        self.assertEqual(resultJSON, """[{"rating": 100, "word": "lucrative", "answers": [{"status": "match", "answer_text": "profitable"}, {"status": "match", "answer_text": "moneymaking"}, {"status": "neutral", "answer_text": "remunerative"}]}, {"rating": 0, "word": "ferociously(en)", "answers": [{"status": "neutral", "answer_text": "\u044f\u0440\u043e\u0441\u0442\u043d\u043e"}, {"status": "neutral", "answer_text": "\u043d\u0435\u0438\u0441\u0442\u043e\u0432\u043e. \u0423\u0436\u0430\u0441\u043d\u043e"}, {"status": "neutral", "answer_text": "\u0436\u0435\u0441\u0442\u043e\u043a\u043e"}, {"status": "neutral", "answer_text": "\u0441\u0432\u0438\u0440\u0435\u043f\u043e"}, {"status": "neutral", "answer_text": "\u0434\u0438\u043a\u043e"}, {"status": "neutral", "answer_text": "\u043d\u0435\u0432\u044b\u043d\u043e\u0441\u0438\u043c\u043e."}, {"status": "wrong", "answer_text": "\u043b\u0430\u0436\u0430"}]}]""")

    def testDeleteDictEntry(self):
        today = datetime.date.today()
        current_time = int(time.time())
        u = self.createUser("da_zbur", "enabled", 10)
        u.use_questions = "yes"
        u.put()

        d1 = self.createDictEntry("da_zbur", 2, "lucrative", \
            u"profitable, moneymaking, remunerative", "[LOO-kruh-tiv]")
        d2 = self.createDictEntry("da_zbur", 2, "ferociously(en)", \
            u"жестоко, яростно, свирепо, дико, неистово. Ужасно, невыносимо.")

        l1 = self.createLearnListItem("da_zbur", d1, today, current_time)
        l2 = self.createLearnListItem("da_zbur", d2, today, current_time)

        self.createQuestion(l1, today, "da_zbur", d1.word,
             "profitable, moneymaking", 1, today, 100)
        self.createQuestion(l2, today, "da_zbur", d2.word,
             u"лажа", 2, today, 0)
        deleteDictEntry(u, "lucrative")

        self.assertEqual(None, Dictionary.all().\
            filter("word =", "lucrative").get())
        self.assertEqual(1, LearnList.all().count())
        self.assertEqual(1, Question.all().count())
        self.assertEqual(1, Dictionary.all().count())

    def testEditDictEntry(self):
        today = datetime.date.today()
        current_time = int(time.time())
        u = self.createUser("da_zbur", "enabled", 10)
        u.use_questions = "yes"
        u.put()

        d1 = self.createDictEntry("da_zbur", 2, "lucrative", \
            u"profitable, moneymaking, remunerative", "[LOO-kruh-tiv]")
        d2 = self.createDictEntry("da_zbur", 2, "ferociously(en)", \
            u"жестоко, яростно, свирепо, дико, неистово. Ужасно, невыносимо.")

        l1 = self.createLearnListItem("da_zbur", d1, today, current_time)
        l2 = self.createLearnListItem("da_zbur", d2, today, current_time)

        self.createQuestion(l1, today, "da_zbur", d1.word,
             "profitable, moneymaking", 1, today, 100)
        self.createQuestion(l2, today, "da_zbur", d2.word,
             u"лажа", 2, today, 0)
        editDictEntry(u, "lucrative", "lucrative[adj]:profitable")
        new_entry = Dictionary.all().filter("word =", "lucrative").get()

        self.assertEqual("profitable", new_entry.meaning)
        self.assertEqual("[adj]", new_entry.pronounce)


if __name__ == "__main__":
    unittest.main()
