from models.learnlist import LearnList
# It would be easier to just use this approach for now:
# if answer_rating=0 (no answer at all or completely incorrect answer) then ef'= -0.2
# if answer_rating=1 (correct answer for at least one meaning) then ef' = 0.1
# for each additional correct meaning add 0.05 to ef'
# Starting EF = 1.5
def get_next_interval(n,prev_interval,prev_efactor,answer_rating):
    if n == 1:
        return  {'new_interval':2, 'new_efactor':1.5}

    new_interval = prev_interval * prev_efactor
    new_efactor = prev_efactor
    if answer_rating == 0:
        new_efactor = prev_efactor - 0.2
    if answer_rating == 1:
        new_efactor = prev_efactor + 0.1

    return {'new_interval':round(new_interval,2),\
    'new_efactor':round(new_efactor,2)}

def add_new_item(twitter_user, word_id):
    l = LearnList()
    i = get_next_interval(1,0,0,0)
    l.twitter_user = twitter_user
    l.word_id = word_id
    l.interval_days = i['new_interval']
    l.efactor = i['new_efactor']
    l.total_served = 0
    l.put()


	
