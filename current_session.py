
from appengine_utilities.sessions import Session

from models.users import User

session_key = "current_user"

def current_user():
  session = Session()
  if session.has_key(session_key):
    return session[session_key]
  else:
    return None

def registration_code():
    session = Session()
    if session.has_key("registration_code"):
        return session["registration_code"]
    else:
        return None

def delete_session():
    session = Session()
    session.delete()
  
def set_current_user(user):
  session = Session()
  session[session_key] = user

def set_registration_code(code):
    session = Session()
    session["registration_code"] = code

def words_iter():
    session = Session()
    if session.has_key("words_iter"):
        return session["words_iter"]
    else:
        return None

def set_words_iter(words_iter):
    session = Session()
    session["words_iter"] = words_iter
