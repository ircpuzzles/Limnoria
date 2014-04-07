
class Channel(object):
    def __init__(self, name, topic):
        self.name = name
        self.topic = topic

    def __str__(self):
        return '<Channel %s [%s]>' % (self.name, self.topic)

