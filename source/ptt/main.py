#!/usr/bin/env python3
"""
A PTT Crawler that downloads PTT posts from its web interface then saves the
parsed information into a file, which is developed for analysing the used
camera market on PTT.
"""

import csv
import re
import queue as queue
import requests
from dateutil import parser
from bs4 import BeautifulSoup


class Record:
    """
    An abstract class that holds the meta information of a camera being sold
    such as its price.
    """

    def __init__(self, name, price, source, author, date):
        self.name = name
        self.price = price
        self.source = source
        self.author = author
        self.date = date

    def __str__(self):
        return "<%s %sNTD %s>" % (self.name, self.price, self.date)

    @property
    def serialized(self):
        """
        Gets a serialized data of this record.
        """
        return [self.name, self.price, self.source, self.author, self.date]


class PttRecord(Record):
    """
    A Ptt record of an used camera sold.
    """

    def __init__(self, dom):

        # Gets the header and the content of this post
        header = dom.select(".article-metaline .article-meta-value")
        content = " ".join(dom.select("#main-content")[0].findAll(
            text=True, recursive=False))

        name = self.__format_name(header[1].text)
        author = header[0].text.split()[0]
        date = parser.parse(header[2].text)
        price = int(re.search("(\\d+00)", content).group(0))

        Record.__init__(self, name, price, "ptt", author, date)

    @classmethod
    def __format_name(cls, name):

        # Raises error on invalid record
        if u"出售" not in name:
            raise PttRecordException("Not a sale post (%s)" % name)

        if name.startswith("Re:"):
            raise PttRecordException("Not an original post (%s)" % name)

        # Trims unused part in name
        return name[max(name.rfind("]"), name.rfind("］")) + 1:].strip()


class PttRecordException(Exception):
    """
    Exceptions that triggered in methods of PttRecord.
    """
    pass


class Crawler:
    """
    An abstract crawler class that fetches used camera data from the Internet.
    """

    def fetch(self):
        """
        Fetches the content from the source.
        """
        raise NotImplementedError

    def read(self):
        """
        Reads the fetched content.
        """
        raise NotImplementedError

    def save(self):
        """
        Saves the result into file.
        """
        raise NotImplementedError


class PttCrawler(Crawler):
    """
    A Ptt crawler that fetches used camera data from Ptt.
    """

    URL_PREFIX = "http://www.ptt.cc"
    INDEX_SUFFIX = "/index.html"
    PAGES = 5

    SAVED_CSV = "records.csv"

    def __init__(self, board_name):
        self.board_name = board_name
        self.__records = []

    def fetch(self):
        """
        Download all posts of the given PTT board.
        """

        url = self.URL_PREFIX + "/bbs/" + self.board_name + self.INDEX_SUFFIX
        post_urls = queue.Queue()

        # Fetches post urls from each page
        for _ in range(self.PAGES):
            next_page_url, page_post_urls = self.__fetch_page(url)
            while page_post_urls.qsize() > 0:
                post_urls.put(page_post_urls.get())
            url = self.URL_PREFIX + next_page_url

        # Fetches each post
        self.__records = []
        while post_urls.qsize() > 0:
            post_url = self.URL_PREFIX + post_urls.get()
            try:
                self.__records.append(self.__fetch_post(post_url))
            except AttributeError:
                print("Skipped, unable to parse")
                continue
            except PttRecordException as ptt_exception:
                print("Skipped, ptt post error", ptt_exception)
                continue

    @classmethod
    def __fetch_page(cls, url):

        dom = cls.__get_dom(url)

        # Gets the post urls on this page
        rows = dom.find_all("div", {"class": "r-ent"})
        page_post_urls = queue.Queue()
        for row in rows:
            row_url = row.find("a")
            if row_url:
                post_url = row_url["href"]
                print("Found: %s" % post_url)
                page_post_urls.put(post_url)
            else:
                print("Skipped")

        # Gets the link for the next page
        next_page_url = dom.select(
            "#action-bar-container .btn-group-paging a")[1]["href"]

        return next_page_url, page_post_urls

    @classmethod
    def __fetch_post(cls, post_url):
        return PttRecord(cls.__get_dom(post_url))

    @classmethod
    def __get_dom(cls, url):
        print("Fetching %s" % url)
        html = requests.get(url)
        return BeautifulSoup(html.text, 'html.parser')

    def read(self):
        return self.__records

    def save(self):
        with open(self.SAVED_CSV, "w") as fout:
            writer = csv.writer(fout)
            for record in self.__records:
                writer.writerow(record.serialized)


def main():
    """
    Main entry of this script.
    """
    crawler = PttCrawler("photo-buy")
    crawler.fetch()
    records = crawler.read()
    for record in records:
        print(record)
    crawler.save()


if __name__ == "__main__":
    main()
