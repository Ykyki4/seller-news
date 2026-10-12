from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup

from ..browser import Browser
from .base import Source, register

MSK = timezone(timedelta(hours=3))


@register("wb_release_notes")
class WbReleaseNotes(Source):
    """Журнал изменений WB API — dev.wildberries.ru/release-notes. Антибот WB не пускает
    headless-браузер, поэтому по умолчанию окно открывается за пределами экрана.
    На странице записи за последние ~2 месяца, у каждой только дата."""

    URL = "https://dev.wildberries.ru/release-notes"

    def fetch(self, since: datetime):
        since_day = since.astimezone(MSK).date()
        with Browser(self.id, self.cfg.get("proxy", "system"), self.cfg.get("headless", False)) as br:
            html = br.html(self.URL, wait_for='div[id^="note-"]')
        items = []
        for note in BeautifulSoup(html, "lxml").select('div[id^="note-"]'):
            date_tag = note.select_one('[class*="dateBlock"] > span')
            title_tag = note.select_one('[class*="styles_title"]')
            if not date_tag or not title_tag:
                continue
            published = datetime.strptime(date_tag.get_text(strip=True), "%d.%m.%Y").replace(tzinfo=MSK)
            if published.date() < since_day:
                continue
            kind = note.select_one('[class*="styles_type"]')
            scopes = [s.get_text(" ", strip=True) for s in note.select('[class*="scopeBlock"]')]
            body = note.select_one('[class*="styles_mdx"] > div:not([class*="styles_title"])')
            title = title_tag.get_text(" ", strip=True)
            if kind:
                title = f"[{kind.get_text(strip=True)}] {title}"
            summary = " · ".join(scopes)
            if body:
                summary += (". " if summary else "") + body.get_text(" ", strip=True)
            it = self.item(title, f"{self.URL}#{note['id']}", published, summary)
            it.date_only = True
            items.append(it)
        return items
