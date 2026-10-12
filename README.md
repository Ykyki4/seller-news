# Новости для селлеров Ozon и Wildberries

Собирает новости за сутки или за неделю и печатает их в консоль, сгруппированными по маркетплейсу и дню.

```
pip install -r requirements.txt
python -m playwright install chromium   # браузер для seller.ozon.ru и dev.wildberries.ru
python -m seller_news            # за последние 24 часа
python -m seller_news week       # за 7 дней
python -m seller_news week -m wb --summary   # только WB, с текстом новостей
python -m seller_news --hours 6 -s ozon_tg   # 6 часов, один источник
python -m seller_news --list-sources
python -m seller_news week -o            # сохранить в news_<дата>_<время>.txt
python -m seller_news week -o news.txt   # сохранить в указанный файл
```

## Страница с обзором от нейросети

```
python -m seller_news page            # собрать неделю, обработать, открыть site/index.html
python -m seller_news page --no-ai    # то же без нейросети
python -m seller_news page -o D:/news.html --no-open
```

Страница — один HTML-файл без сервера: вкладки «сутки» / «неделя», фильтр по маркетплейсу,
темам и «только важные». Нейросеть (Claude, настройки в секции `[ai]` в `sources.toml`) для
каждой новости пишет выжимку, определяет тему и важность, склеивает дубли из разных
источников и составляет обзор главного по каждому маркетплейсу за сутки и за неделю.

Нужен ключ Anthropic API в переменной `ANTHROPIC_API_KEY`
(`setx ANTHROPIC_API_KEY sk-ant-...`, затем перезапустить терминал). api.anthropic.com из РФ
не открывается, поэтому запросы идут через системный прокси (`proxy` в `[ai]`). Если ключа
или доступа нет, страница всё равно строится, просто без обработки.

## Источники

| id | что | маркетплейс |
|---|---|---|
| `ozon_tg` | t.me/ozonmarketplace — официальный канал Ozon для продавцов | ozon |
| `wb_tg` | t.me/wbsellerofficial — «WB Партнёры», официальный | wb |
| `wb_api_tg` | t.me/wb_api_notifications — изменения WB API | wb |
| `ozon_site` | seller.ozon.ru/media/news — новости для продавцов на сайте Ozon | ozon |
| `wb_dev` | dev.wildberries.ru/release-notes — журнал изменений WB API | wb |
| `oborot` | RSS oborot.ru | по ключевым словам |
| `retail_ru` | RSS retail.ru | по ключевым словам |

Для источников с `marketplace = "auto"` маркетплейс определяется по ключевым словам из
`[marketplaces.*]` в `sources.toml`; новости, где не упомянут ни один маркетплейс, отбрасываются.

`ozon_site` и `wb_dev` закрыты JS-антиботом, поэтому открываются через Chromium (Playwright,
`seller_news/browser.py`). Каждый из них добавляет к сбору ~10 секунд. Куки антибота хранятся в
`.browser-profiles/`, эту папку можно удалить, она создастся заново. WB не пускает headless-браузер,
поэтому у `wb_dev` стоит `headless = false`: окно Chromium открывается за пределами экрана.
У новостей с этих сайтов есть только дата, поэтому время не показывается.

Новости из кабинета seller.wildberries.ru без входа недоступны, их можно получать только через
официальный API с токеном продавца.

## Как добавить сайт

- **Ещё один телеграм-канал или RSS-лента** — дописать блок `[[sources]]` в `sources.toml`.
- **Новый маркетплейс** (например, Яндекс Маркет) — блок `[marketplaces.ym]` с ключевыми словами;
  RSS-источники с `marketplace = "auto"` сразу начнут его находить.
- **Сайт нового типа** (HTML-страница, API) — файл в `seller_news/sources/`:

```python
from datetime import datetime
from ..http import get
from .base import Source, register

@register("mysite")            # type = "mysite" в sources.toml
class MySite(Source):
    def fetch(self, since: datetime):
        html = get(self.session, self.cfg["url"]).text
        # ... распарсить и вернуть [self.item(title, url, published_dt, summary), ...]
```

Модуль подхватывается автоматически. Любые поля из блока `[[sources]]` доступны через `self.cfg`.
Если один источник упал, остальные всё равно выводятся, а ошибка печатается внизу.

## Прокси

Параметр `proxy` у источника: `"direct"` (мимо прокси), `"system"` (системный прокси /
`HTTPS_PROXY`) или URL. Российские сайты рвут TLS при заходе через зарубежный прокси,
поэтому у них стоит `direct`. t.me из РФ без прокси может не открываться, поэтому у него `system`.
