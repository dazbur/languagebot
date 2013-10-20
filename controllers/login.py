import hashlib

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext import db

from current_session import set_current_user

from models.users import User

class Login(webapp.RequestHandler):
    def get(self):
        model = {}
        model["user_name"] = ""
        model["password"] = ""
        self.response.out.write(template.render("views/login.html", model))
        
    def post(self):
        model = {}
        username = self.request.get("username")
        password = self.request.get("password")
        
        model["user_name"] = username
        model["password"] = password
        pwd_hash = hashlib.md5()
        pwd_hash.update(password)

        # load user by username and password...
        user = User.all()\
                   .filter("username =", username)\
                   .filter("password =", pwd_hash.hexdigest())\
                   .get()
        if user:
            set_current_user(user)
            self.redirect("/details")
        else:
            model["login"] = "fail"
            self.response.out.write(template.render("views/login.html", model))
