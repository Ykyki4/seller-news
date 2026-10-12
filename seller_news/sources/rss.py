from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from ..http import get
from .base import Source, register


@register("rss")
class RssFeed(Source):
    """RSS 2.0 или Atom-лента."""

    def fetch(self, since: datetime):
        xml = get(self.session, self.cfg["url"]).content
        soup = BeautifulSoup(xml, "xml")
        items = []
        for entry in soup.find_all(["item", "entry"]):
            published = _parse_date(_text(entry, "pubDate", "published", "updated", "dc:date"))
            if not published or published < since:
                continue
            link = entry.find("link")
            url = (link.get("href") or link.get_text()) if link else ""
            summary = _text(entry, "description", "summary", "content")
            summary = BeautifulSoup(summary, "lxml").get_text(" ") if summary else ""
            items.append(self.item(_text(entry, "title"), _strip_utm(url.strip()), published, summary))
        return items


def _text(entry, *names) -> str:
    for n in names:
        tag = entry.find(n)
        if tag and tag.get_text(strip=True):
            return tag.get_text()
    return ""


def _parse_date(s: str):
    s = s.strip()
    if not s:
        return None
    try:
        dt = parsedate_to_datetime(s)
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _strip_utm(url: str) -> str:
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query) if not k.startswith("utm_")]
    return urlunsplit(parts._replace(query=urlencode(query)))
