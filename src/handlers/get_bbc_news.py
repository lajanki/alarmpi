import feedparser

from src import apcontent


class NewsParser(apcontent.AlarmpiContent):

    def __init__(self, section_data):
        super().__init__(section_data)

    def build(self):
        url = "https://feeds.bbci.co.uk/news/world/rss.xml"
        rss = feedparser.parse(url)

        if rss.bozo:
            newsfeed = 'Failed to reach BBC News'

        else:
            newsfeed = 'And now, The latest stories from the World section of the BBC News.\n\n'
            for entry in rss.entries[:4]:
                # append each item to the feed string
                newsfeed += "{}.\n{}\n\n".format(entry["title"], entry["description"])

        self.content = newsfeed
