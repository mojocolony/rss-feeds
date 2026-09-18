#!/usr/bin/env python3
import json
import re
import sys
import time
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from xml.etree.ElementTree import Element, SubElement, ElementTree

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/152 Safari/537.36 RSSFeedBuilder/1.0"
TIMEOUT = 25


def get(url):
    req = Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/json,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "en-CA,en;q=0.9",
    })
    with urlopen(req, timeout=TIMEOUT) as r:
        return r.read(), r.headers.get("Content-Type", "")


def text(url):
    body, _ = get(url)
    return body.decode("utf-8", errors="replace")


def parse_dt(value):
    if not value:
        return None
    value = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def first_group(patterns, s, flags=re.I | re.S):
    for p in patterns:
        m = re.search(p, s, flags)
        if m:
            return m.group(1).strip()
    return None


def clean_html(s):
    if not s:
        return ""
    s = re.sub(r"<script\b[^>]*>.*?</script>", "", s, flags=re.I | re.S)
    s = re.sub(r"<style\b[^>]*>.*?</style>", "", s, flags=re.I | re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def extract_metadata(html, url):
    title = first_group([
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\']twitter:title["\'][^>]+content=["\']([^"\']+)["\']',
        r"<title[^>]*>(.*?)</title>",
    ], html)

    desc = first_group([
        r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']*)["\']',
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)["\']',
    ], html) or ""

    image = first_group([
        r'<meta[^>]+property=["\']og:image(?::secure_url)?["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
    ], html)

    published = first_group([
        r'<meta[^>]+property=["\']article:published_time["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\']date["\'][^>]+content=["\']([^"\']+)["\']',
        r'"datePublished"\s*:\s*"([^"]+)"',
    ], html)

    author = first_group([
        r'<meta[^>]+name=["\']author["\'][^>]+content=["\']([^"\']+)["\']',
        r'"author"\s*:\s*\{[^{}]*"name"\s*:\s*"([^"]+)"',
    ], html)

    return {
        "title": clean_html(title) if title else url,
        "description": clean_html(desc),
        "url": url,
        "published": parse_dt(published),
        "image": image,
        "author": clean_html(author) if author else None,
    }


def rss(items, title, site_url, description, out_path):
    items = [x for x in items if x.get("title") and x.get("url")]
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    items.sort(key=lambda x: x.get("published") or epoch, reverse=True)

    rss_el = Element("rss", {"version": "2.0", "xmlns:media": "http://search.yahoo.com/mrss/"})
    channel = SubElement(rss_el, "channel")
    SubElement(channel, "title").text = title
    SubElement(channel, "link").text = site_url
    SubElement(channel, "description").text = description
    SubElement(channel, "language").text = "en"
    SubElement(channel, "lastBuildDate").text = format_datetime(datetime.now(timezone.utc))

    for x in items[:60]:
        it = SubElement(channel, "item")
        SubElement(it, "title").text = x["title"]
        SubElement(it, "link").text = x["url"]
        SubElement(it, "guid", {"isPermaLink": "true"}).text = x["url"]
        if x.get("description"):
            SubElement(it, "description").text = x["description"]
        if x.get("published"):
            SubElement(it, "pubDate").text = format_datetime(x["published"])
        if x.get("author"):
            SubElement(it, "author").text = x["author"]
        if x.get("image"):
            SubElement(it, "{http://search.yahoo.com/mrss/}content", {
                "url": x["image"], "medium": "image"
            })

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    ElementTree(rss_el).write(out, encoding="utf-8", xml_declaration=True)


def espn():
    urls = [
        "https://site.api.espn.com/apis/site/v2/sports/tennis/atp/news",
        "https://site.api.espn.com/apis/site/v2/sports/tennis/wta/news",
    ]
    by_id = {}
    for u in urls:
        body, _ = get(u)
        data = json.loads(body.decode("utf-8"))
        for a in data.get("articles", []):
            aid = str(a.get("id") or a.get("headline"))
            web = (((a.get("links") or {}).get("web") or {}).get("href"))
            if not web:
                continue
            images = a.get("images") or []
            image = images[0].get("url") if images else None
            by_id[aid] = {
                "title": a.get("headline") or "ESPN Tennis",
                "description": a.get("description") or "",
                "url": web,
                "published": parse_dt(a.get("published") or a.get("lastModified")),
                "image": image,
            }
    return list(by_id.values())


def links_from_page(page_url, include_regex):
    html = text(page_url)
    hrefs = re.findall(r'href=["\']([^"\']+)["\']', html, re.I)
    found, seen = [], set()
    rx = re.compile(include_regex, re.I)
    for href in hrefs:
        full = urljoin(page_url, href.split("#")[0])
        if rx.search(full) and full not in seen:
            seen.add(full)
            found.append(full)
    return found


def scrape_articles(index_url, link_regex, limit=45):
    urls = links_from_page(index_url, link_regex)[:limit]
    items = []
    for u in urls:
        try:
            items.append(extract_metadata(text(u), u))
        except Exception as e:
            print(f"WARN {u}: {e}", file=sys.stderr)
        time.sleep(0.15)
    return items


def main():
    failures = []
    jobs = [
        ("feeds/espn-tennis.xml", espn, "ESPN Tennis", "https://www.espn.com/tennis/",
         "Current ESPN tennis news, generated from ESPN's live tennis news APIs."),
        ("feeds/wta.xml", lambda: scrape_articles(
            "https://www.wtatennis.com/news", r"^https://www\.wtatennis\.com/news/\d+/"
        ), "WTA Tennis News", "https://www.wtatennis.com/news",
         "Current WTA news articles from wtatennis.com."),
        ("feeds/sportsnet-tennis.xml", lambda: scrape_articles(
            "https://www.sportsnet.ca/tennis/", r"^https://www\.sportsnet\.ca/(?:atp|wta|tennis)/article/"
        ), "Sportsnet Tennis", "https://www.sportsnet.ca/tennis/",
         "Current Sportsnet tennis articles with corrected per-article links."),
    ]

    for path, producer, title, site, desc in jobs:
        try:
            items = producer()
            if not items:
                raise RuntimeError("No items found")
            rss(items, title, site, desc, path)
            print(f"{title}: wrote {len(items)} items -> {path}")
        except Exception as e:
            failures.append(f"{title}: {e}")
            print(f"ERROR {title}: {e}", file=sys.stderr)

    if failures:
        for f in failures:
            print(" - " + f, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
