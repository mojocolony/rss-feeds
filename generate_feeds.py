#!/usr/bin/env python3
import re
import sys
import json
from datetime import datetime, timezone
from email.utils import format_datetime
from html import unescape
from urllib.parse import urljoin, quote
from urllib.request import Request, urlopen
from xml.etree.ElementTree import Element, SubElement, ElementTree, fromstring

TIMEOUT = 30
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/153.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-CA,en;q=0.9",
}

def fetch(url):
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=TIMEOUT) as r:
        return r.read().decode("utf-8", errors="replace")

def clean(s):
    s = re.sub(r"<script\b[^>]*>.*?</script>", " ", s or "", flags=re.I | re.S)
    s = re.sub(r"<style\b[^>]*>.*?</style>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    s = unescape(s)
    return re.sub(r"\s+", " ", s).strip()

def extract_links(page_url, patterns, max_items=60):
    html = fetch(page_url)
    anchor_rx = re.compile(
        r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        re.I | re.S
    )
    regexes = [re.compile(p, re.I) for p in patterns]

    items = []
    seen = set()

    for href, inner in anchor_rx.findall(html):
        url = urljoin(page_url, href.split("#")[0])
        if not any(rx.search(url) for rx in regexes):
            continue

        title = clean(inner)
        if len(title) < 8:
            continue
        if title.lower() in {
            "read more", "learn more", "view more", "more", "watch now",
            "espn", "sportsnet"
        }:
            continue
        if url in seen:
            continue

        seen.add(url)
        items.append({"title": title, "url": url})
        if len(items) >= max_items:
            break

    return items

def extract_rss_items(feed_url, max_items=60):
    """Read the publisher's own feed instead of scraping webpage links."""
    root = fromstring(fetch(feed_url))
    result, seen = [], set()
    for entry in root.findall("./channel/item"):
        title = (entry.findtext("title") or "").strip()
        url = (entry.findtext("link") or "").strip()
        if len(title) < 8 or not url.startswith(("https://", "http://")) or url in seen:
            continue
        seen.add(url)
        result.append({"title": title, "url": url})
        if len(result) >= max_items:
            break
    if not result:
        raise RuntimeError("Publisher RSS feed returned no articles")
    return result


def extract_espn_news(max_items=60):
    """Use ESPN's tennis news JSON, preserving direct article URLs."""
    articles, seen, errors = [], set(), []
    for league in ("atp", "wta"):
        url = f"https://site.api.espn.com/apis/site/v2/sports/tennis/{league}/news?limit=50"
        try:
            data = json.loads(fetch(url))
            for item in data.get("articles", []):
                title = (item.get("headline") or "").strip()
                links = item.get("links") or {}
                href = (links.get("web") or {}).get("href") or ""
                if not href.startswith(("https://", "http://")) or len(title) < 8 or href in seen:
                    continue
                seen.add(href)
                articles.append({"title": title, "url": href})
        except Exception as exc:
            errors.append(f"{league}: {exc}")
    if not articles:
        raise RuntimeError("ESPN news API has no usable articles" +
                           (f" ({'; '.join(errors)})" if errors else ""))
    return articles[:max_items]


def get_items(job):
    """Try the most structured source first, then original HTML extraction."""
    if job.get("api") == "espn":
        try:
            return extract_espn_news()
        except Exception as exc:
            print(f"WARNING {job['title']} API: {exc}", file=sys.stderr)
        try:
            return extract_rss_items("https://www.espn.com/espn/rss/tennis/news")
        except Exception as exc:
            print(f"WARNING {job['title']} RSS: {exc}", file=sys.stderr)
    if job.get("feed"):
        try:
            return extract_rss_items(job["feed"])
        except Exception as exc:
            print(f"WARNING {job['title']} RSS: {exc}", file=sys.stderr)
    return extract_links(job["page"], job["patterns"])


def make_rss(items, title, site_url, description, out_path):
    if not items:
        raise RuntimeError(f"No article links found for {title}")

    rss = Element("rss", {"version": "2.0"})
    channel = SubElement(rss, "channel")
    SubElement(channel, "title").text = title
    SubElement(channel, "link").text = site_url
    SubElement(channel, "description").text = description
    SubElement(channel, "language").text = "en"
    SubElement(channel, "lastBuildDate").text = format_datetime(datetime.now(timezone.utc))

    for x in items:
        item = SubElement(channel, "item")
        SubElement(item, "title").text = x["title"]
        SubElement(item, "link").text = x["url"]
        SubElement(item, "guid", {"isPermaLink": "true"}).text = x["url"]

    ElementTree(rss).write(out_path, encoding="utf-8", xml_declaration=True)
    print(f"{title}: wrote {len(items)} items -> {out_path}")

def main():
    jobs = [
        {
            "title": "WTA Tennis News",
            "page": "https://www.wtatennis.com/news",
            "patterns": [r"^https://www\.wtatennis\.com/news/\d+/"],
            "description": "Current WTA tennis news.",
            "out": "feeds/wta.xml",
        },
        {
            "title": "ESPN Tennis",
            "api": "espn",
            "page": "https://africa.espn.com/tennis/",
            "patterns": [
                r"^https://africa\.espn\.com/tennis/story/_/id/\d+/",
                r"^https://www\.espn\.com/tennis/story/_/id/\d+/"
            ],
            "description": "Current ESPN tennis news.",
            "out": "feeds/espn-tennis.xml",
        },
        {
            "title": "Sportsnet Tennis",
            "feed": "https://www.sportsnet.ca/tennis/feed/",
            "page": "https://www.sportsnet.ca/?s=tennis",
            "patterns": [
                r"^https://www\.sportsnet\.ca/tennis/article/",
                r"^https://www\.sportsnet\.ca/atp/article/",
                r"^https://www\.sportsnet\.ca/wta/article/"
            ],
            "description": "Current Sportsnet tennis news.",
            "out": "feeds/sportsnet-tennis.xml",
        },
    ]

    failed = []
    succeeded = 0
    for job in jobs:
        try:
            items = get_items(job)
            make_rss(
                items,
                job["title"],
                job["page"],
                job["description"],
                job["out"],
            )
            succeeded += 1
        except Exception as e:
            failed.append(f'{job["title"]}: {e}')
            print(f'::warning title={job["title"]} unavailable::{e}', file=sys.stderr)

    if failed:
        print("\nSources not refreshed (previous XML, if any, was preserved):", file=sys.stderr)
        for f in failed:
            print(" - " + f, file=sys.stderr)
    if succeeded == 0:
        print("ERROR: No RSS sources could be refreshed.", file=sys.stderr)
        sys.exit(1)
    print(f"Updated {succeeded}/{len(jobs)} feeds.")

if __name__ == "__main__":
    main()
