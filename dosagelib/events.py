# -*- coding: iso-8859-1 -*-
# Copyright (C) 2004-2005 Tristan Seligmann and Jonathan Jacobs
import os
import time
import urllib
import codecs
from . import rss, util, configuration

class EventHandler(object):
    """Base class for writing events to files. The currently defined events are
    start(), comicDownloaded() and end()."""

    def __init__(self, basepath, baseurl):
        """Initialize base path and url."""
        self.basepath = basepath
        self.baseurl = baseurl or self.getBaseUrl()

    def getBaseUrl(self):
        '''Return a file: URL that probably points to the basedir.

        This is used as a halfway sane default when the base URL is not
        provided; not perfect, but should work in most cases.'''
        components = util.splitpath(os.path.abspath(self.basepath))
        url = '/'.join([urllib.quote(component, '') for component in components])
        return 'file:///' + url + '/'

    def getUrlFromFilename(self, filename):
        """Construct URL from filename."""
        components = util.splitpath(util.getRelativePath(self.basepath, filename))
        url = '/'.join([urllib.quote(component, '') for component in components])
        return self.baseurl + url

    def start(self):
        """Emit a start event. Should be overridden in subclass."""
        pass

    def comicDownloaded(self, comic, filename):
        """Emit a comic downloaded event. Should be overridden in subclass."""
        pass

    def end(self):
        """Emit an end event. Should be overridden in subclass."""
        pass


class RSSEventHandler(EventHandler):
    """Output in RSS format."""

    name = 'rss'

    def getFilename(self):
        """Return RSS filename."""
        return os.path.abspath(os.path.join(self.basepath, 'dailydose.rss'))

    def start(self):
        """Log start event."""
        today = time.time()
        yesterday = today - 86400
        today = time.localtime(today)
        yesterday = time.localtime(yesterday)

        link = configuration.Url

        self.rssfn = self.getFilename()

        if os.path.exists(self.rssfn):
            self.newfile = False
            self.rss = rss.parseFeed(self.rssfn, yesterday)
        else:
            self.newfile = True
            self.rss = rss.Feed('Daily Dosage', link, 'Comics for %s' % time.strftime('%Y/%m/%d', today))

    def comicDownloaded(self, comic, filename):
        """Write RSS entry for downloaded comic."""
        imageUrl = self.getUrlFromFilename(filename)
        title = '%s - %s' % (comic.name, os.path.basename(filename))
        pageUrl = comic.referrer
        description = '<img src="%s"/><br/><a href="%s">View Comic</a>' % (imageUrl, pageUrl)
        args = (
            title,
            imageUrl,
            description,
            util.rfc822date(time.time())
        )

        if self.newfile:
            self.newfile = False
            self.rss.addItem(*args)
        else:
            self.rss.addItem(*args, append=False)

    def end(self):
        """Write RSS data to file."""
        self.rss.write(self.rssfn)


class HtmlEventHandler(EventHandler):
    """Output in HTML format."""

    name = 'html'

    def fnFromDate(self, date):
        """Get filename from date."""
        fn = time.strftime('comics-%Y%m%d.html', date)
        fn = os.path.join(self.basepath, 'html', fn)
        fn = os.path.abspath(fn)
        return fn

    def start(self):
        """Start HTML output."""
        today = time.time()
        yesterday = today - 86400
        tomorrow = today + 86400
        today = time.localtime(today)
        yesterday = time.localtime(yesterday)
        tomorrow = time.localtime(tomorrow)

        fn = self.fnFromDate(today)
        if os.path.exists(fn):
            raise ValueError('output file %r already exists' % fn)

        d = os.path.dirname(fn)
        if not os.path.isdir(d):
            os.makedirs(d)

        yesterdayUrl = self.getUrlFromFilename(self.fnFromDate(yesterday))
        tomorrowUrl = self.getUrlFromFilename(self.fnFromDate(tomorrow))

        self.html = codecs.open(fn, 'w', 'utf-8')
        self.html.write(u'''<!DOCTYPE html>
<html lang="en">
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
<meta name="generator" content="%s"/>
<title>Comics for %s</title>
</head>
<body>
<a href="%s">Previous Day</a> | <a href="%s">Next Day</a>
<ul>
''' % (configuration.App, time.strftime('%Y/%m/%d', today),
       yesterdayUrl, tomorrowUrl))
        # last comic name (eg. CalvinAndHobbes)
        self.lastComic = None
        # last comic strip URL (eg. http://example.com/page42)
        self.lastUrl = None

    def comicDownloaded(self, comic, filename):
        """Write HTML entry for downloaded comic."""
        if self.lastComic != comic.name:
            self.newComic(comic)
        imageUrl = self.getUrlFromFilename(filename)
        pageUrl = comic.referrer
        if pageUrl != self.lastUrl:
            self.html.write(u'<li><a href="%s">%s</a>\n' % (pageUrl, pageUrl))
        self.html.write(u'<br/><img src="%s"/>\n' % imageUrl)
        self.lastComic = comic.name
        self.lastUrl = pageUrl

    def newComic(self, comic):
        """Start new comic list in HTML."""
        if self.lastUrl is not None:
            self.html.write(u'</li>\n')
        if self.lastComic is not None:
            self.html.write(u'</ul>\n')
        self.html.write(u'<li>%s</li>\n' % comic.name)
        self.html.write(u'<ul>\n')

    def end(self):
        """End HTML output."""
        if self.lastUrl is not None:
            self.html.write(u'</li>\n')
        if self.lastComic is not None:
            self.html.write(u'</ul>\n')
        self.html.write(u'''</ul>
</body>
</html>''')
        self.html.close()


_handler_classes = {}

def addHandlerClass(clazz):
    if not issubclass(clazz, EventHandler):
        raise ValueError("%s must be subclassed from %s" % (clazz, EventHandler))
    _handler_classes[clazz.name] = clazz

addHandlerClass(HtmlEventHandler)
addHandlerClass(RSSEventHandler)


def getHandlerNames():
    """Get sorted handler names."""
    return sorted(_handler_classes.keys())


_handlers = []

def addHandler(name, basepath=None, baseurl=None):
    """Install a global handler with given name."""
    if basepath is None:
        basepath = '.'
    _handlers.append(_handler_classes[name](basepath, baseurl))


class MultiHandler(object):
    """Encapsulate a list of handlers."""

    def start(self):
        """Emit a start event. Should be overridden in subclass."""
        for handler in _handlers:
            handler.start()

    def comicDownloaded(self, comic, filename):
        """Emit a comic downloaded event. Should be overridden in subclass."""
        for handler in _handlers:
            handler.comicDownloaded(comic, filename)

    def end(self):
        """Emit an end event. Should be overridden in subclass."""
        for handler in _handlers:
            handler.end()


multihandler = MultiHandler()

def getHandler():
    """Get installed event handler."""
    return multihandler
