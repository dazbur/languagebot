import twitter

api =  twitter.Api(consumer_key='C5USXjmmoGr7m7S795KceQ',
                    consumer_secret='Nq81PlQs5Y2QYKMKK5ANqzOlFdm1py9NbEfSWGJQKE',
                    access_token_key='346270091-Kt4Tv3VMujY9GL8pyHzAZ7ncKdJqcQYTv8HIcw0k',
                    access_token_secret='mJWIflnqIOC03iTMue2ZyQuF49F9bPU7JuPbXUATa8')

replies = api.GetReplies()
print [x for x in replies]
