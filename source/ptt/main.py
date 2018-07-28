#!/usr/bin/env python3
"""
A PTT Crawler that downloads PTT posts from its web interface then saves the
parsed information into a file, which is developed for analysing the used
camera market on PTT.
"""

import csv
import re
import queue as queue
import os.path
import requests
from dateutil import parser
from bs4 import BeautifulSoup


class Record:
    """
    An abstract class that holds the meta information of a camera being sold
    such as its price.
    """

    def __init__(self, name, price, source, author, date, url):
        self.name = name
        self.price = price
        self.source = source
        self.author = author
        self.date = date
        self.url = url

    def __str__(self):
        return "<%s %sNTD %s>" % (self.name, self.price, self.date)

    @property
    def serialized(self):
        """
        Gets a serialized data of this record.
        """
        return [self.name, self.price, self.source, self.author, self.date,
                self.url]


class PttRecord(Record):
    """
    A Ptt record of an used camera sold.
    """

    def __init__(self, dom, url):

        # Gets the header and the content of this post
        header = dom.select(".article-metaline .article-meta-value")
        content = " ".join(dom.select("#main-content")[0].findAll(
            text=True, recursive=False))

        name = self.__format_name(header[1].text)
        author = header[0].text.split()[0]
        date = parser.parse(header[2].text)
        price = int(re.search("(\\d+00)", content).group(0))

        if price == 0:
            raise PttRecordException("Invalid price (%s)" % name)

        Record.__init__(self, name, price, "ptt", author, date, url)

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


class PttCrawler(Crawler):
    """
    A Ptt crawler that fetches used camera data from Ptt.
    """

    URL_PREFIX = "http://www.ptt.cc"
    INDEX_SUFFIX = "/index979.html"
    PAGES = 100

    SAVED_CSV = "records/%s.csv"

    class Cache:
        """
        A disk cache controller for logging the next page to fetch.
        """

        CACHE_FILE = "cache"

        def __init__(self):
            if os.path.isfile(self.CACHE_FILE):
                with open(self.CACHE_FILE) as fin:
                    self.__next_page = fin.read().strip()
            else:
                self.__next_page = None

        def write_next_page(self, next_page):
            """
            Writes the url of the next page into disk.
            """
            self.__next_page = next_page
            with open(self.CACHE_FILE, "w") as fout:
                fout.write("%s" % self.__next_page)

        def read_next_page(self):
            """
            Reads the url of the next page from disk.
            """
            return self.__next_page

        @property
        def is_cached(self):
            """
            Returns true if there's any page had done.
            """
            return self.__next_page is not None

    def __init__(self, board_name):
        self.board_name = board_name
        self.cache = self.Cache()

    def fetch(self):
        """
        Download all posts of the given PTT board.
        """

        # Gets the starting url
        if self.cache.is_cached:
            page_url = self.cache.read_next_page()
        else:
            page_url = self.URL_PREFIX + "/bbs/" + self.board_name + \
                self.INDEX_SUFFIX

        # Scans each page of this board
        for _ in range(self.PAGES):

            # Initializes a url queue for the posts of this page
            post_urls = queue.Queue()
            next_page_url, page_post_urls = self.__fetch_page_urls(page_url)
            while page_post_urls.qsize() > 0:
                post_urls.put(page_post_urls.get())

            # Fetches the post contents of this page
            page_records = self.__fetch_page_records(post_urls)

            # Saves the records to disk
            self.__save_page_records(page_records,
                                     tag=self.__parge_page_tag(page_url))

            # Gets the url for the next page
            page_url = self.URL_PREFIX + next_page_url

            # Caches the next page url
            self.cache.write_next_page(page_url)

    @classmethod
    def __fetch_page_urls(cls, url):

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
    def __fetch_page_records(cls, post_urls):

        # Fetches each post
        page_records = []
        while post_urls.qsize() > 0:
            post_url = cls.URL_PREFIX + post_urls.get()
            try:
                page_records.append(cls.__fetch_post(post_url))
            except AttributeError:
                print("Skipped, unable to parse")
                continue
            except PttRecordException as ptt_exception:
                print("Skipped, ptt post error", ptt_exception)
                continue
            except Exception as exception:
                print("Skipped, unseen exception", exception)
                continue

        return page_records

    @classmethod
    def __fetch_post(cls, post_url):
        return PttRecord(cls.__get_dom(post_url), post_url)

    @classmethod
    def __get_dom(cls, url):
        print("Fetching %s" % url)
        html = requests.get(url)
        return BeautifulSoup(html.text, 'html.parser')

    @classmethod
    def __save_page_records(cls, page_records, tag=""):

        filename = cls.SAVED_CSV % tag if tag else cls.SAVED_CSV

        with open(filename, "w") as fout:
            writer = csv.writer(fout)
            for record in page_records:
                writer.writerow(record.serialized)

        print("Saved %s" % filename)

    @classmethod
    def __parge_page_tag(cls, url):
        return re.search("(\\d+).html", url).group(1)


def main():
    """
    Main entry of this script.
    """
    crawler = PttCrawler("photo-buy")
    crawler.fetch()


if __name__ == "__main__":
    main()
