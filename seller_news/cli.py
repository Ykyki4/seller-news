import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

from .collector import collect, load_config
from .render import render

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "sources.toml"
DEFAULT_PAGE = ROOT / "site" / "index.html"
PERIODS = {"day": (timedelta(days=1), "за сутки"), "week": (timedelta(days=7), "за неделю")}


def main(argv=None):
    # консоль Windows по умолчанию в cp1252/cp866 — кириллица и эмодзи падают
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")

    p = argparse.ArgumentParser(prog="seller_news", description="Новости для селлеров маркетплейсов")
    p.add_argument("period", nargs="?", choices=[*PERIODS, "page"], default="day",
                   help="day — последние 24 часа, week — последние 7 дней (по умолчанию day); "
                        "page — HTML-страница с новостями дня и недели и обзором от нейросети")
    p.add_argument("--hours", type=int, help="произвольный период в часах вместо day/week")
    p.add_argument("-m", "--marketplace", action="append",
                   help="только этот маркетплейс (ozon, wb); можно несколько раз")
    p.add_argument("-s", "--source", action="append", help="только этот источник по id; можно несколько раз")
    p.add_argument("--summary", action="store_true", help="показывать текст новости, а не только заголовок")
    p.add_argument("--no-color", action="store_true", help="без цвета (например, для вывода в файл)")
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="путь к sources.toml")
    p.add_argument("-o", "--output", nargs="?", const="", type=str, metavar="ФАЙЛ",
                   help="сохранить текст в файл (без цвета); без имени — news_<дата>_<время>.txt")
    p.add_argument("--no-ai", action="store_true", help="page: без обработки нейросетью")
    p.add_argument("--no-open", action="store_true", help="page: не открывать страницу в браузере")
    p.add_argument("--list-sources", action="store_true", help="показать источники и выйти")
    args = p.parse_args(argv)

    config = load_config(args.config)

    if args.list_sources:
        for s in config.sources:
            print(f"{s.id:12} {s.type_name:16} {s.marketplace:5} {s.name}")
        return 0

    selected = args.marketplace or list(config.marketplaces)
    unknown = [m for m in selected if m not in config.marketplaces]
    if unknown:
        p.error(f"неизвестный маркетплейс: {', '.join(unknown)} (есть: {', '.join(config.marketplaces)})")
    if args.source:
        config.sources = [s for s in config.sources if s.id in args.source]
        if not config.sources:
            p.error("ни один источник не подошёл под --source")
    config.sources = [s for s in config.sources if s.marketplace in ("auto", *selected)]

    if args.period == "page":
        return make_page(args, config, selected)

    if args.hours:
        delta, label = timedelta(hours=args.hours), f"за {args.hours} ч"
    else:
        delta, label = PERIODS[args.period]
    since = datetime.now().astimezone() - delta

    print(f"Собираю новости из {len(config.sources)} источников…", file=sys.stderr)
    result = collect(config, since)
    color = not args.no_color and sys.stdout.isatty()
    print(render(result, config.marketplaces, selected, since, label, args.summary, color))
    if args.output is not None:
        path = Path(args.output or f"news_{datetime.now():%Y-%m-%d_%H%M}.txt")
        text = render(result, config.marketplaces, selected, since, label, args.summary, False)
        path.write_text(text + "\n", encoding="utf-8")
        print(f"Сохранено в {path.resolve()}", file=sys.stderr)
    return 1 if result.errors and not result.items else 0


def make_page(args, config, selected):
    import webbrowser

    from . import page

    now = datetime.now().astimezone()
    periods = {"day": ("сутки", now - PERIODS["day"][0]), "week": ("неделя", now - PERIODS["week"][0])}
    print(f"Собираю новости за неделю из {len(config.sources)} источников…", file=sys.stderr)
    result = collect(config, periods["week"][1])
    items = [it for it in result.items if it.marketplaces & set(selected)]
    marketplaces = {k: config.marketplaces[k] for k in selected}

    notes, digests, model = {}, {}, None
    if not args.no_ai and items and config.ai.get("enabled", True):
        from .ai import Editor

        try:
            editor = Editor(config.ai)
            print(f"Обрабатываю {len(items)} новостей в {editor.model} (неделя)…", file=sys.stderr)
            notes, digests["week"] = editor.annotate(items, marketplaces, "последние 7 дней")
            day_ids = [i for i, it in enumerate(items) if page.in_period(it, periods["day"][1])]
            if day_ids:
                print(f"Обзор за сутки ({len(day_ids)} новостей)…", file=sys.stderr)
                # id в обзоре дня — индексы в day_items, переводим обратно в общие
                day_digest = editor.digest([items[i] for i in day_ids], marketplaces, "последние 24 часа")
                for d in day_digest.values():
                    for h in d.highlights:
                        h.item_ids = [day_ids[j] for j in h.item_ids if 0 <= j < len(day_ids)]
                digests["day"] = day_digest
            model = editor.model
        except Exception as e:  # без нейросети страница всё равно нужна
            print(f"Нейросеть недоступна, страница без обработки: {type(e).__name__}: {e}", file=sys.stderr)
            if "authentication" in str(e):
                print("Задайте ключ: setx ANTHROPIC_API_KEY sk-ant-... (и перезапустите терминал)", file=sys.stderr)
            notes, digests, model = {}, {}, None

    html = page.build(items, config.marketplaces, selected, periods, notes, digests, result.errors, model)
    path = page.write(Path(args.output) if args.output else DEFAULT_PAGE, html)
    print(f"Страница: {path}", file=sys.stderr)
    if not args.no_open:
        webbrowser.open(path.as_uri())
    return 0
