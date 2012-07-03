import twitter

#api =  twitter.Api(consumer_key='C5USXjmmoGr7m7S795KceQ',
#                    consumer_secret='Nq81PlQs5Y2QYKMKK5ANqzOlFdm1py9NbEfSWGJQKE',
#                    access_token_key='346270091-Kt4Tv3VMujY9GL8pyHzAZ7ncKdJqcQYTv8HIcw0k',
#                    access_token_secret='mJWIflnqIOC03iTMue2ZyQuF49F9bPU7JuPbXUATa8')
api = twitter.Api(consumer_key='8hUziMDlvgoMLOPskIrIA',
                consumer_secret='qU86upQ36NogZw7y5HvXvR1Ki6uvH4P7GXlYwpas4',
                access_token_key='361573893-OuCJBZNnHGjprS0dQxwXeey0GcEjsjdJ3phEc3VH',
                access_token_secret='4qqahAmLF230ooXE9FRtaWg69cilhvPGzVNJ8IrMhLQ',
                debugHTTP=True)

replies = api.GetReplies()
print [x.text for x in replies]
