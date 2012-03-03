import logging

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template

from current_session import current_user, set_current_user
from request_model_binder import model_from_request
from models.users import User
from twitter_auth import Twitter
from twitter import TwitterError


class Profile(webapp.RequestHandler):
    
    def __init__(self):
        super( Profile, self).__init__()
        user = current_user()

        # List of people you follow on twitter who are also languagebot users 
        self.friends_list = self.get_friends_list(user)  
        
        # List of users you are following on languagebot 
        self.i_follow_list = user.i_follow.split(',') 
        if '' in  self.i_follow_list: 
            self.i_follow_list.remove('')
 

    def get(self):
        user = current_user()
        model = ProfileModel()
        self.view(model, user)
    
    def post(self):
        model = model_from_request(self.request, ProfileModel)
        user = current_user()
        # validate data; on error, redisplay form with error messages
        if not model.validate():
            self.view(model, user)
            return
        user.message_type = "reply"
        user.repeat_times = int(model.repeat_times)
        user.messages_per_day = int(model.messages_per_day)

        # If checkbox is not checked model just doesn't have this attribute
        if hasattr(model, 'account_disabled'):
            user.account_status="disabled"
        else:
            user.account_status="enabled"

        # Building new list of people I follow based on checkboxes value
        new_i_follow_list = []
        for friend in self.friends_list:
            if hasattr(model, friend):
                new_i_follow_list.append(friend)

        # This is the list of users that were removed. Nedd to update
        # followed_by list for them
        removed_list = list(set(self.i_follow_list) - set(new_i_follow_list))

        self.update_followed_by_list(new_i_follow_list, removed_list, user.twitter)
        
        #user.followed_by = ""    
        user.i_follow = ",".join(new_i_follow_list)
        user.put()
        set_current_user(user)

        self.redirect("/")


    def view(self, model, user):
        self.response.out.write(template.render("views/profile.html",{"model":model,
        "user":user, "i_follow_list":self.i_follow_list,
        "friends_list":self.friends_list}))
    
    def get_friends_list(self, user):
        twitterApi = Twitter.getInstance()
        friends_list = []
        l = []
        
        # Very bad hack. Need to move all these to model.validate
        try:
            # Twitter API doesn't allow to get all friends infor at once.
            # Instead you can only get all friends Ids and the use UserLookup
            # to get full user infor but only in batches of 100 user at once
            follow_list = twitterApi.api.GetFriendIDs(user.twitter)["ids"]

            while len(follow_list) > 100:
                l = l + twitterApi.api.UsersLookup(follow_list[0:100])
                follow_list = follow_list[100:len(follow_list)]
            l = l + twitterApi.api.UsersLookup(follow_list[0:len(follow_list)])

            for friend in l:
                friend_in_db = User.all().filter("twitter =", friend.screen_name)
                if friend_in_db.count() == 1:
                    friends_list.append(friend.screen_name)
            
        except TwitterError: 
            friends_list = ['not_authorized']

        return friends_list

    def update_followed_by_list(self, add_list, remove_list, by_user):
        # First add current user to followed_by lists for all users he follows
        for user in add_list:
            
            dbUser =  User.all().filter("twitter =", user).fetch(1)[0]
            followed_by_list = dbUser.followed_by.split(',')
            if '' in followed_by_list:
                followed_by_list.remove('')
            if not by_user in followed_by_list:
                followed_by_list.append(by_user)
            dbUser.followed_by = ",".join(followed_by_list)
            dbUser.put()

        # Then remove current user from followed_by list for all user he
        # stopped following
        for user in remove_list:
            dbUser =  User.all().filter("twitter =", user).fetch(1)[0]
            followed_by_list = dbUser.followed_by.split(',')
            if '' in followed_by_list:
                followed_by_list.remove('')
            if by_user in followed_by_list:
                followed_by_list.remove(by_user)
            dbUser.followed_by = ",".join(followed_by_list)
            dbUser.put()


        
class ProfileModel:  
    def __init__(self):
        user = current_user()
        if user:
            if user.message_type == "reply":
                self.is_reply_checked = "checked"
            if user.message_type == "direct":
                self.is_direct_checked = "checked"
            if user.account_status == "disabled":
                self.is_account_disabled = "checked"
            else:
                self.is_account_disabled = ""

    def validate(self):
        self.repeat_times_empty = (self.repeat_times == "")
        self.messages_per_day_empty = (self.messages_per_day == "")

        return self.is_valid()

    def is_valid(self):
        return not (self.repeat_times_empty\
            or self.messages_per_day_empty)
               
