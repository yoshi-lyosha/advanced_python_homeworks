# https://github.com/alexopryshko/advancedpython/blob/master/5/homework3.txt

# http://www.aosabook.org/en/500L/a-web-crawler-with-asyncio-coroutines.html
# https://github.com/igorzakhar/Web-crawler-with-asyncio-coroutines/blob/master/Part_3.md
# https://github.com/aosabook/500lines/blob/master/crawler/code/crawling.py

# rate limiting
# http://qaru.site/questions/2459262/aiohttp-rate-limiting-requests-per-second-by-domain
# https://github.com/tomasbasham/ratelimit/blob/master/ratelimit/decorators.py
# https://github.com/RazerM/ratelimiter/blob/master/ratelimiter/_async.py

# todo: remove weird shit with max_redirect and do flex with max_depth + depth
import os
import re
import time
import asyncio
import logging
import urllib.parse
from dataclasses import dataclass
from typing import Tuple, Optional
from concurrent.futures.process import ProcessPoolExecutor

import bs4
import aiohttp
from aioelasticsearch import Elasticsearch

from hw_3_aio_web_crawler.config import config as c


@dataclass
class CrawlerConfig:
    """ Just a container for storing crawler configuration """

    max_workers: int
    max_rps_per_domain: int
    max_retries: int


class CrawlerHelper:
    # todo: inherit CrawlerQueue, CrawlerReporter, CrawlerParser
    # and maybe AsyncCrawler from this class
    def __init__(self, logger=None, loop=None):
        self.loop = loop or asyncio.get_event_loop()
        self.logger = logger or logging.getLogger(f"hw_3.{type(self).__name__}")

    async def init(self, loop=None):
        self.loop = loop or asyncio.get_event_loop()

    async def close(self):
        pass


class CrawlerQueue:
    """
    Just an interface for a queue
    in case if i will move to redis/rabbit queue instead of simple asyncio.Queue()
    """

    def __init__(self, logger=None, loop=None):
        self.loop = loop or asyncio.get_event_loop()
        self.logger = logger or logging.getLogger(f"hw_3.{type(self).__name__}")

    async def init(self, loop=None):
        self.loop = loop or asyncio.get_event_loop()

    async def get(self) -> Tuple[str, str]:
        raise NotImplementedError

    async def put(self, url, depth=None):
        raise NotImplementedError

    async def ack(self, task=None):
        raise NotImplementedError

    async def join(self):
        raise NotImplementedError

    async def len(self):
        raise NotImplementedError

    async def purge(self):
        raise NotImplementedError


class CrawlerQueueAsyncioQueue(CrawlerQueue):
    """ CrawlerQueue implementation by asyncio.Queue() """

    def __init__(self, logger=None, loop=None):
        super().__init__(logger, loop)
        self._queue: asyncio.Queue = None

    async def init(self, loop=None):
        await super().init(loop=loop)
        self._queue = asyncio.Queue(loop=self.loop)

    async def get(self) -> Tuple[str, str]:
        return await self._queue.get()

    async def put(self, url, depth=None):
        self._queue.put_nowait((url, depth))

    async def ack(self, task=None):
        self._queue.task_done()

    async def join(self):
        await self._queue.join()

    async def len(self):
        return self._queue.qsize()

    async def purge(self):
        del self._queue
        await self.init()


@dataclass
class FetchReport:
    """ Simple container for the reports after url fetching """

    root_url: str
    url: str
    status: int
    text: Optional[str]

    unsuccess_msg: Optional[str] = None

    exception: Optional[Exception] = None


class CrawlerReporter:
    """ Base class for reporters """

    def __init__(self, logger=None, loop=None):
        self.loop = loop or asyncio.get_event_loop()
        self.logger = logger or logging.getLogger(f"hw_3.{type(self).__name__}")

    async def init(self, loop=None):
        self.loop = loop or asyncio.get_event_loop()

    async def close(self):
        pass

    async def do_report(self, report: FetchReport):
        # todo: think about necessity of reporting non 200 fetch results
        raise NotImplementedError


class StdOutCrawlerReporter(CrawlerReporter):
    """ Simple reporting to stdout for debug purposes """

    async def do_report(self, report: FetchReport):
        if report.status == 200 and report.text:
            print(f"Url {report.url} text: {report.text!r}")


class ElasticSearchCrawlerReporter(CrawlerReporter):
    """ Reporter that indexes fetch reports """

    def __init__(self, host, port, index, doc_type, logger=None, loop=None):
        super().__init__(logger, loop)
        self.host = host
        self.port = port

        self.es: Elasticsearch = None

        self.index = index
        self.doc_type = doc_type

    async def init(self, loop=None):
        await super().init(loop)
        self.es = Elasticsearch(
            hosts=[{"host": self.host, "port": self.port}], loop=self.loop
        )

    async def close(self):
        await self.es.close()

    async def do_report(self, report: FetchReport):
        if report.status == 200 and report.text:
            self.logger.debug('Indexing "ok" fetching result to elasticsearch')
            body = {"root_url": report.root_url, "url": report.url, "text": report.text}
            indexing_result = await self.es.index(
                index=self.index, doc_type=self.doc_type, body=body
            )
            self.logger.debug("Indexing result: %s", indexing_result)
        else:
            self.logger.debug(
                "Report is not suitable for indexing: %s", report.unsuccess_msg
            )


class CrawlerParser:
    """ Html parser for getting urls list and getting text from html """

    parsable_content_types = ["text/html", "application/xml"]
    # during html parsing you better ignore this elements bc they have no text
    ignore_text_elements_list = [
        "style",
        "script",
        "head",
        "title",
        "meta",
        "[document]",
    ]

    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(f"hw_3.{type(self).__name__}")

    def parse_text_and_urls_from_html(
        self, html: str, base_url: str, root_domain: str
    ) -> Tuple[str, set]:
        raise NotImplementedError

    async def parse(
        self,
        html: str,
        base_url: str,
        root_domain: str,
        url_exclude_pattern=None,
        pool=None,
        loop=None,
    ) -> Tuple[str, set]:
        loop = loop or asyncio.get_event_loop()
        return await loop.run_in_executor(
            pool,
            self.parse_text_and_urls_from_html,
            html,
            base_url,
            root_domain,
            url_exclude_pattern,
        )

    def is_parsable(self, content_type):
        if content_type in self.parsable_content_types:
            return True
        return False

    @staticmethod
    def trim_and_cleanup_text(text: str) -> str:
        # e.g. '\n\n\nsome\ntext     with\nspaces\n\n'

        # trimming leading and trailing whitespace at each line
        lines = (line.strip() for line in text.splitlines())
        # finding space chains ('     ') and reducing them
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        # creating test with a lot of line terminators
        result = "\n".join(chunk for chunk in chunks if chunk)
        return result

    @staticmethod
    def normalize_urls(urls: set, base_url: str) -> set:
        normalized_urls = set()
        for url in urls:
            normalized_url = urllib.parse.urljoin(base_url, url)
            normalized_url, _ = urllib.parse.urldefrag(normalized_url)
            normalized_urls.add(normalized_url)
        return normalized_urls

    def filter_urls(self, urls: set, root_domain: str, url_exclude_pattern=None):
        filtered_urls = set()
        for url in urls:
            if self.is_url_allowed(url, root_domain, url_exclude_pattern):
                filtered_urls.add(url)
        return filtered_urls

    @staticmethod
    def is_redirect(response):
        # decided that this function will fit ok in that class instead of
        # creating utils.py with a single function
        return response.status in (300, 301, 302, 303, 307)

    @staticmethod
    def is_url_allowed(url, root_domain, exclude_pattern=None):
        if exclude_pattern and re.search(exclude_pattern, url):
            # contains smth that we excluding
            return False

        parsed_url = urllib.parse.urlparse(url)
        if parsed_url.scheme not in ("http", "https"):
            # not http scheme, will skip url
            return False

        host, _ = urllib.parse.splitport(parsed_url.netloc)
        host = host.lower()
        if host != root_domain:
            # not root host, will skip url
            return False

        return True

    @staticmethod
    def is_url_valid(url):
        try:
            parsed_url = urllib.parse.urlparse(url)
            return all([parsed_url.scheme, parsed_url.netloc])
        except (AttributeError, TypeError):
            return False


class BSCrawlerParser(CrawlerParser):
    """ Parser implementation by BeautifulSoup """

    html_parser = "html.parser"

    def _tag_visible(self, element):
        if element.parent.name in self.ignore_text_elements_list:
            return False
        if isinstance(element, bs4.element.Comment):
            return False
        return True

    def parse_text_and_urls_from_html(
        self, html: str, base_url: str, root_domain: str, url_exclude_pattern=None
    ) -> Tuple[str, set]:
        soup = bs4.BeautifulSoup(html, self.html_parser)

        links = set()
        for link in soup.find_all("a"):
            href = link.get("href")
            if href:
                links.add(href)
        links = self.normalize_urls(links, base_url)
        links = self.filter_urls(links, root_domain, url_exclude_pattern)

        # better than [s.extract() for s in soup(self.ignore_text_elements_list)]
        tags_with_text = soup.find_all(text=True)
        tags_with_visible_text = filter(self._tag_visible, tags_with_text)
        text = "".join(tags_with_visible_text)
        text = self.trim_and_cleanup_text(text)

        return text, links


class AsyncRateLimiter:
    """ RPS limiter """

    def __init__(self, max_calls: int, period=1.0, logger=None, loop=None):
        self.logger = logger or logging.getLogger(f"hw_3.{type(self).__name__}")
        self.loop = loop or asyncio.get_event_loop()

        self.max_calls = max_calls
        self.period = period

        self.last_reset = time.time()
        self.num_calls = 0

        self.lock = asyncio.Lock(loop=self.loop)

    async def __aenter__(self):
        while True:
            async with self.lock:
                now = time.time()
                elapsed = now - self.last_reset
                period_remaining = self.period - elapsed

                if period_remaining <= 0:
                    self.num_calls = 0
                    self.last_reset = time.time()

                self.num_calls += 1

                if self.num_calls > self.max_calls:
                    self.logger.debug(
                        "Rate limit is exceeded, will sleep for %s", period_remaining
                    )
                    await asyncio.sleep(period_remaining)
                    continue
                else:
                    return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class AsyncCrawler:
    """
    Finally, the thing that composes all this guys up

    Crawls the domain, reports it's text, has rps limiting, depth limiting
    """

    def __init__(
        self,  # NOSONAR
        root_url: str,
        max_rps: int,
        max_depth: int,
        config: CrawlerConfig,
        crawling_queue: CrawlerQueue,
        parser: CrawlerParser,
        parser_pool_executor: ProcessPoolExecutor,
        reporter: CrawlerReporter,
        logger=None,
        loop=None,
    ):
        # todo: exclude_pattern. e.g. for static
        self.loop = loop or asyncio.get_event_loop()
        self.logger = logger or logging.getLogger(f"hw_3.{type(self).__name__}")

        self.root_url = root_url
        self.max_rps = max_rps
        self.max_depth = max_depth

        self.limiter: AsyncRateLimiter = None

        self.config = config

        self.session: aiohttp.ClientSession = None

        self.queue = crawling_queue
        self.parser = parser
        self.parser_pool_executor = parser_pool_executor
        self.reporter = reporter

        # for the next storing
        self.workers_tasks: list = None

        # pretty interesting set
        # the point is that we need to control not only fetched urls, but also
        # urls that currently in queue. so we will add urls to that set before
        # their fetching for queue purity
        self.known_urls = set()

        parsed_host_url = urllib.parse.urlparse(self.root_url)
        host, _ = urllib.parse.splitport(parsed_host_url.netloc)
        self.root_domain = host.lower()

        # some validation
        if not self.root_domain:
            raise TypeError(  # or AttributeError, or ValueError? hmm…
                f"Bad root_domain {self.root_domain!r} for url {self.root_url}"
            )
        if not self.parser.is_url_valid(self.root_url):
            raise TypeError(f"Bad url for crawling {self.root_url!r}")

    async def init(self, loop=None):
        self.logger.info("Crawler initialisation")
        self.loop = loop or asyncio.get_event_loop()

        self.limiter = AsyncRateLimiter(self.max_rps, loop=self.loop)
        self.session = aiohttp.ClientSession(loop=self.loop)

        await self.queue.init(loop=self.loop)
        await self.reporter.init(loop=self.loop)

        self.logger.info(
            "Init crawler with putting root_domain %r to the queue", self.root_domain
        )
        await self.add_url(self.root_url)

    async def close(self):
        await self.session.close()
        await self.queue.purge()
        await self.reporter.close()
        self.parser_pool_executor.shutdown(wait=False)

    async def run(self, blocking=False):
        self.logger.info("Spawn crawlers")
        self.workers_tasks = [
            self.loop.create_task(self.crawler())
            for _ in range(self.config.max_workers)
        ]
        if blocking:
            await self.queue.join()
            for w in self.workers_tasks:
                w.cancel()

    async def crawler(self):
        self.logger.info("Start crawler infinite loop")
        while True:
            url = None
            try:
                url, depth = await self.queue.get()
                self.logger.debug("Got url from queue %r", url)
                if url not in self.known_urls:
                    self.logger.debug(
                        "Somehow there is an url %r not from known urls", url
                    )
                    continue
                await self.fetch(url, depth)
            except asyncio.CancelledError:
                break
            except Exception as unexpected_exception:
                await self._process_unexpected_exception(unexpected_exception)
            finally:
                if url:
                    await self.queue.ack()

    async def fetch(self, url, depth):
        self.logger.debug("Fetch %r, current depth: %s", url, depth)
        try:
            response = await self._get_url_with_retries(url)
        except aiohttp.ClientError as client_error:
            await self._process_bad_response(client_error, url)
            return None
        try:
            if self.parser.is_redirect(response):
                await self._process_redirect(response, depth)
            else:
                await self._process_ok_response(response, depth)
        finally:
            await response.release()

    async def _get_url_with_retries(self, url) -> aiohttp.ClientResponse:
        # get url with retries
        last_client_error = None
        for attempt in range(1, self.config.max_retries + 1):
            try:
                async with self.limiter:
                    response = await self.session.get(url, allow_redirects=False)
                return response
            except aiohttp.ClientError as client_error:
                self.logger.info("try %r for %r raised %r", attempt, url, client_error)
                last_client_error = client_error
        else:  # if all attempts are out
            self.logger.info(
                "Out of attempts %r to reach %r, last exception: %r",
                self.config.max_retries,
                url,
                last_client_error,
            )
            raise last_client_error  # just re-raising last exception

    async def _process_ok_response(self, response: aiohttp.ClientResponse, depth):
        url = str(response.url)
        status = response.status
        content_type = response.content_type

        if status != 200:
            report = FetchReport(  # http status is not 200
                self.root_url,
                url,
                status,
                None,
                unsuccess_msg=f"status is not 200 - {status}",
            )

        elif not self.parser.is_parsable(content_type):
            report = FetchReport(  # resp is not parsable
                self.root_url,
                url,
                status,
                None,  # (bad content type)
                unsuccess_msg=f"content is not parsable, {content_type!r}",
            )
        else:  # if all is ok we will
            html = await response.text()
            text, urls = await self.parser.parse(  # parse html and get text and urls
                html, url, self.root_domain
            )
            if depth < self.max_depth:
                for link in urls.difference(self.known_urls):
                    await self.add_url(
                        link, depth + 1
                    )  # put these urls in crawling queue
            else:
                self.logger.info(
                    "depth limit (%s) reached on new urls from %r", self.max_depth, url
                )
            report = FetchReport(
                self.root_url, url, status, text
            )  # finally - generate positive report

        await self.reporter.do_report(report)

    async def _process_redirect(self, response: aiohttp.ClientResponse, depth):
        location = response.headers.get("location", "")
        url_from = str(response.url)
        self.logger.debug(
            "got redirect from %r , location header is %r", url_from, location
        )
        next_url = urllib.parse.urljoin(url_from, location)
        if next_url in self.known_urls:  # for the lack of optimisation
            self.logger.debug("redirection url %r is already known", next_url)
            return
        if depth < self.max_depth:
            self.logger.info("redirect to %r from %r", next_url, url_from)
            await self.add_url(next_url, depth + 1)
        else:
            self.logger.info(
                "depth limit (%s) reached on redirect to %r from %r",
                self.max_depth,
                next_url,
                url_from,
            )

    async def _process_bad_response(self, client_error: aiohttp.ClientError, url: str):
        # the only thing we can do i guess
        self.logger.exception(
            "got aiohttp.ClientError %r during the fetching url %r", client_error, url
        )

    async def _process_unexpected_exception(self, exception: Exception):
        # the only thing we can do i guess
        self.logger.exception(
            "got an unexpected exception at crawler loop, %r", exception
        )

    async def add_url(self, url, depth=0):
        self.logger.debug(
            "Adding url %r to the queue, depth %r, max_depth %r",
            url,
            depth,
            self.max_depth,
        )
        self.known_urls.add(url)
        await self.queue.put(url, depth)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)-8s %(name)-35s %(funcName)-30s %(message)s",
        datefmt="[%Y-%m-%d %H:%M:%S %z]",
    )
    logging.getLogger("chardet").setLevel(logging.WARNING)
    logging.getLogger("elasticsearch").setLevel(logging.WARNING)

    # some_site_url = 'http://localhost:8841'
    some_site_url = "https://docs.python.org"
    some_site_max_rps = 10
    some_site_max_depth = 10

    crawler_config = CrawlerConfig(
        c.CRAWLER_MAX_WORKERS, c.CRAWLER_MAX_RPS_PER_DOMAIN, c.CRAWLER_MAX_RETRIES
    )
    queue = CrawlerQueueAsyncioQueue()
    crawler_parser = BSCrawlerParser(c.CRAWLER_MAX_PARSING_WORKERS)
    crawler_reporter = ElasticSearchCrawlerReporter(
        c.CRAWLER_ELASTICSEARCH_HOST,
        c.CRAWLER_ELASTICSEARCH_PORT,
        c.CRAWLER_ELASTICSEARCH_INDEX,
        c.CRAWLER_ELASTICSEARCH_DOC_TYPE,
    )
    # crawler_reporter = StdOutCrawlerReporter()
    parser_process_pool = ProcessPoolExecutor(os.cpu_count())

    crawler = AsyncCrawler(
        some_site_url,
        some_site_max_rps,
        some_site_max_depth,
        crawler_config,
        queue,
        crawler_parser,
        parser_process_pool,
        crawler_reporter,
    )

    async def main():
        print("Initializing crawler")
        await crawler.init()
        try:
            print("Starting crawling")
            await crawler.run(blocking=True)
        except KeyboardInterrupt:
            print("KeyboardInterrupt")
        finally:
            print("Stop crawler and close all connections")
            await crawler.close()

    try:
        asyncio.run(main())
    finally:
        parser_process_pool.shutdown(wait=False)
