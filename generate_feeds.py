#!/usr/bin/env python3
import re
import sys
from datetime import datetime, timezone
from email.utils import format_datetime
from html import unescape
from urllib.parse import urljoin, quote
from urllib.request import Request, urlopen
from xml.etree.ElementTree import Element, SubElement, ElementTree

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
    for job in jobs:
        try:
            items = extract_links(job["page"], job["patterns"])
            make_rss(
                items,
                job["title"],
                job["page"],
                job["description"],
                job["out"],
            )
        except Exception as e:
            failed.append(f'{job["title"]}: {e}')
            print(f'ERROR {job["title"]}: {e}', file=sys.stderr)

    if failed:
        print("\nFailures:", file=sys.stderr)
        for f in failed:
            print(" - " + f, file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
