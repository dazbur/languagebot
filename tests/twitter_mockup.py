import hashlib

class User(object):
	def __init__(self,
		screen_name=None):
		self.screen_name = screen_name

# This is Status class copied fomr twitter.py
class Status(object):
	def __init__(self,
    	created_at=None,
        favorited=None,
        id=None,
        text=None,
        location=None,
        user=None,
        in_reply_to_screen_name=None,
        in_reply_to_user_id=None,
        in_reply_to_status_id=None,
        truncated=None,
        source=None,
		now=None,
		urls=None,
		user_mentions=None,
		hashtags=None,
		geo=None,
		place=None,
		coordinates=None,
		contributors=None,
		retweeted=None,
		retweeted_status=None,
		retweet_count=None):
	
		self.created_at = created_at
		self.favorited = favorited
		self.id = id
		self.text = text
		self.location = location
		self.user = user
		self.now = now
		self.in_reply_to_screen_name = in_reply_to_screen_name
		self.in_reply_to_user_id = in_reply_to_user_id
		self.in_reply_to_status_id = in_reply_to_status_id
		self.truncated = truncated
		self.retweeted = retweeted
		self.source = source
		self.urls = urls
		self.user_mentions = user_mentions
		self.hashtags = hashtags
		self.geo = geo
		self.place = place
		self.coordinates = coordinates
		self.contributors = contributors
		self.retweeted_status = retweeted_status
		self.retweet_count = retweet_count

class DirectMessage(object):
 
  def __init__(self,
               id=None,
               created_at=None,
               sender_id=None,
               sender_screen_name=None,
               recipient_id=None,
               recipient_screen_name=None,
               text=None):
    self.id = id
    self.created_at = created_at
    self.sender_id = sender_id
    self.sender_screen_name = sender_screen_name
    self.recipient_id = recipient_id
    self.recipient_screen_name = recipient_screen_name
    self.text = text

class APIMockUp:
	def PostUpdate(self, message, in_reply_to_s_id=None,
			user_screen_name=None, in_reply_to_screen_name=None):
		# We will return a naive hash of the message as a status_id
		u = User(screen_name=user_screen_name)
		s = 0
		for i in  message:
			s = s + ord(i)
		status = Status(id=s, in_reply_to_status_id=in_reply_to_s_id,\
			 text=message, user=u, in_reply_to_screen_name=in_reply_to_screen_name)
		return status

	def PostDirectMessage(self, to_user, message, from_user=None):
		# We will return a naive hash of the message as a status_id
		s = 0
		for i in message:
			s = s + ord(i)
		dm = DirectMessage(id=s, sender_screen_name=from_user,\
			recipient_screen_name=to_user, text=message)
		return dm



class TwitterMockup:
	def __init__(self):
		self.api = APIMockUp()
