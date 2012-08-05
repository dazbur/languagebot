from google.appengine.ext import db


class User(db.Model):
    username            = db.StringProperty()
    twitter             = db.StringProperty()
    password            = db.StringProperty()
    utc_offset          = db.IntegerProperty()
    email               = db.StringProperty()
    next_run_time       = db.IntegerProperty()
    message_type        = db.StringProperty()
    account_status      = db.StringProperty()
    repeat_times        = db.IntegerProperty()
    followed_by         = db.StringProperty()
    i_follow            = db.StringProperty()
    messages_per_day    = db.IntegerProperty() 
    default_source_lang = db.StringProperty()
    follow_lang_list    = db.StringProperty()
    use_questions       = db.StringProperty()
    use_daily_email     = db.StringProperty()
    
