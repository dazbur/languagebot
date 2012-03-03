import twitter
import os
import cgi
import models
import random
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template
from google.appengine.ext import db

def getContent(contentType):
	if contentType == 'Cookie':
		id = random.randint(1, maxCookieID)
	if contentType == 'Quotations':
		id = random.randint(1, maxQuotationsID)
	
	contentList = db.GqlQuery("SELECT * FROM %s WHERE id = :1" % (contentType), id)
	contentEnt = contentList[0]	
	
	if contentType == 'Cookie':
		return contentEnt.cookie_text
	if contentType == 'Quotations':
		return contentEnt.content
	
	

class MainPage(webapp.RequestHandler):
	def get(self):
		path = os.path.join(os.path.dirname(__file__), 'index.html')
		template_args={}
		self.response.out.write(template.render(path, template_args))
		

class TwitterUpdater(webapp.RequestHandler):
	def get(self):
		text = getContent('Quotations')		
		api.PostUpdate(cgi.escape(text))
		self.response.out.write(text)

class Reply(webapp.RequestHandler):
	def get(self):
		
		replies = api.GetReplies()
		
		idQuery = db.GqlQuery("SELECT * FROM CurrentID")
		repliedToIdList = []
		for idEntity in idQuery:
			repliedToIdList.append(idEntity.id)
					
		for reply in  replies:
			if reply.id not in repliedToIdList:
				if reply.in_reply_to_screen_name == 'fortune_robot':
					replyText = getContent('Cookie')
					#self.response.out.write("Replying to %s with %s" % (reply.text, replyText))
					api.PostUpdate("@%s %s" % (reply.user.screen_name, cgi.escape(replyText)), reply.id)
				newID = models.CurrentID(id = reply.id)
				newID.put()

				
class CleanupCookies(webapp.RequestHandler):
	def get(self):
		cookieQuery = db.GqlQuery("SELECT * FROM Cookie WHERE id > 430")
		for cookie in cookieQuery:
			cookie.delete()
	
	
application = webapp.WSGIApplication(
                                     [('/', MainPage),
									  ('/send_update', TwitterUpdater),
									  ('/reply', Reply),
									  ('/clean_cookies', CleanupCookies)],
                                     debug=True)
api = twitter.Api(consumer_key='C5USXjmmoGr7m7S795KceQ',
                    consumer_secret='Nq81PlQs5Y2QYKMKK5ANqzOlFdm1py9NbEfSWGJQKE',
                    access_token_key='346270091-Kt4Tv3VMujY9GL8pyHzAZ7ncKdJqcQYTv8HIcw0k',
                    access_token_secret='mJWIflnqIOC03iTMue2ZyQuF49F9bPU7JuPbXUATa8')
	
maxQuotationsID = 3978
maxCookieID = 470

def main():
	run_wsgi_app(application)
	random.seed()

if __name__ == "__main__":
	main()
