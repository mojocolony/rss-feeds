import unittest
from unittest.mock import patch
import json
import io
from xml.etree.ElementTree import ParseError

import generate_feeds as g


class FeedGenerationTests(unittest.TestCase):
    def test_sportsnet_rss_extracts_real_article_links(self):
        data = """<rss version="2.0"><channel><item><title>Tennis finals in Canada</title><link>https://www.sportsnet.ca/tennis/article/example/</link></item></channel></rss>"""
        with patch.object(g, "fetch", return_value=data):
            items = g.extract_rss_items("https://www.sportsnet.ca/tennis/feed/")
        self.assertEqual(items, [{"title": "Tennis finals in Canada", "url": "https://www.sportsnet.ca/tennis/article/example/"}])

    def test_espn_api_extracts_direct_urls_and_deduplicates(self):
        article = {"headline": "Tennis tournament coverage", "links": {"web": {"href": "https://www.espn.com/tennis/story/_/id/1234/example"}}}
        with patch.object(g, "fetch", return_value=json.dumps({"articles": [article]})):
            items = g.extract_espn_news()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["url"], article["links"]["web"]["href"])

    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    def test_successful_feed_does_not_fail_entire_job(self, _err, _out):
        with patch.object(g, "get_items", side_effect=[
            [{"title": "Fresh WTA tournament report", "url": "https://www.wtatennis.com/news/1234/test"}],
            RuntimeError("ESPN unavailable"),
            RuntimeError("Sportsnet unavailable")
        ]), patch.object(g, "make_rss") as write, patch.object(g.sys, "exit") as exit_:
            g.main()
        self.assertEqual(write.call_count, 1)
        exit_.assert_not_called()

    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    def test_total_failure_exits_nonzero(self, _err, _out):
        with patch.object(g, "get_items", side_effect=RuntimeError("source unavailable")), patch.object(g.sys, "exit", side_effect=SystemExit(1)):
            with self.assertRaises(SystemExit):
                g.main()


if __name__ == "__main__":
    unittest.main()
