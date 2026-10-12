import re
from datetime import datetime

from bs4 import BeautifulSoup

from ..http import get
from .base import Source, register

HASHTAGS_ONLY = re.compile(r"^(#\w+\s*)+$")


@register("telegram")
class TelegramChannel(Source):
    """Публичный канал через веб-превью t.me/s/<channel> (без API и авторизации).
    Страница отдаёт ~20 последних постов, старше — через ?before=<id>."""

    MAX_PAGES = 10

    def fetch(self, since: datetime):
        channel = self.cfg["channel"]
        items, before = [], None
        for _ in range(self.MAX_PAGES):
            params = {"before": before} if before else None
            html = get(self.session, f"https://t.me/s/{channel}", params=params).text
            posts = self._parse(html)
            if not posts:
                break
            items += [p for p in posts if p.published >= since]
            oldest = min(posts, key=lambda p: p.published)
            if oldest.published < since:
                break
            before = int(oldest.url.rsplit("/", 1)[1])
        return items

    def _parse(self, html: str):
        soup = BeautifulSoup(html, "lxml")
        posts = []
        for msg in soup.select(".tgme_widget_message[data-post]"):
            time_tag = msg.select_one(".tgme_widget_message_date time[datetime]")
            if not time_tag:
                continue
            published = datetime.fromisoformat(time_tag["datetime"])
            url = f"https://t.me/{msg['data-post']}"
            text_tag = msg.select_one(".tgme_widget_message_text")
            if not text_tag:
                # пост только с картинкой/видео — всё равно нужен для пагинации
                posts.append(self.item("", url, published))
                continue
            for br in text_tag.find_all("br"):
                br.replace_with("\n")
            lines = [l.strip() for l in text_tag.get_text().split("\n") if l.strip()]
            # строка из одних хэштегов (#дайджест, #dbs) — не заголовок, приклеиваем к следующей
            tags = []
            while len(lines) > 1 and HASHTAGS_ONLY.match(lines[0]):
                tags.append(lines.pop(0))
            title = " ".join(tags + lines[:1])
            posts.append(self.item(title, url, published, " ".join(lines[1:])))
        return posts
