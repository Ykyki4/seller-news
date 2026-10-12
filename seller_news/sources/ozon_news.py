import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..browser import Browser
from .base import Source, register

MSK = timezone(timedelta(hours=3))
DATE = re.compile(r"^\d\d\.\d\d\.\d\d$")
CARD_HREF = re.compile(r"^/media/news/[^/?]+/$")


@register("ozon_news")
class OzonSellerNews(Source):
    """Раздел «Новости» на seller.ozon.ru/media/news/. Закрыт JS-антиботом, поэтому
    страница грузится через Chromium. У новостей есть только дата, без времени."""

    BASE = "https://seller.ozon.ru/media/news/"
    MAX_PAGES = 5

    def fetch(self, since: datetime):
        since_day = since.astimezone(MSK).date()
        category = self.cfg.get("category", "sellers")  # sellers / pvz / "" — все
        items = []
        with Browser(self.id, self.cfg.get("proxy", "system"), self.cfg.get("headless", True)) as br:
            for page in range(1, self.MAX_PAGES + 1):
                params = [f"category={category}"] if category else []
                if page > 1:
                    params.append(f"page={page}")
                url = self.BASE + ("?" + "&".join(params) if params else "")
                cards = self._parse(br.html(url, wait_for='a[href^="/media/news/"]'))
                if not cards:
                    break
                items += [c for c in cards if c.published.date() >= since_day]
                # вверху первой страницы закреплены «главные новости» не по порядку,
                # поэтому смотрим на самую старую на странице, а не на последнюю
                if min(c.published for c in cards).date() < since_day:
                    break
        return items

    def _parse(self, html: str):
        soup = BeautifulSoup(html, "lxml")
        cards = []
        for a in soup.find_all("a", href=CARD_HREF):
            for cat in a.select("[href]"):  # плашка категории «Продавцам»
                cat.decompose()
            date, title, tags = None, "", []
            for span in a.find_all("span"):
                text = span.get_text(" ", strip=True)
                if DATE.match(text):
                    date = datetime.strptime(text, "%d.%m.%y").replace(tzinfo=MSK)
                elif text.startswith("#"):
                    tags.append(text)
                elif len(text) > len(title):
                    title = text
            if date and title:
                it = self.item(title, urljoin(self.BASE, a["href"]), date, " ".join(tags))
                it.date_only = True
                cards.append(it)
        return cards
