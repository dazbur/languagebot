class APIMockUp:
	def PostUpdate(self, message):
		return message

class TwitterMockup:
	def __init__(self):
		self.api = APIMockUp()
