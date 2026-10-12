import re
import tomllib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .models import Marketplace, NewsItem
from .sources import Source, source_class


@dataclass
class Config:
    marketplaces: dict[str, Marketplace]
    sources: list[Source]
    ai: dict = field(default_factory=dict)  # секция [ai]


def load_config(path: Path) -> Config:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    marketplaces = {
        key: Marketplace(key, mp.get("name", key), mp.get("keywords", []))
        for key, mp in data.get("marketplaces", {}).items()
    }
    sources = []
    for cfg in data.get("sources", []):
        if cfg.get("enabled", True):
            sources.append(source_class(cfg["type"])(cfg))
    return Config(marketplaces, sources, data.get("ai", {}))


@dataclass
class Result:
    items: list[NewsItem]
    errors: dict[str, str] = field(default_factory=dict)  # имя источника -> ошибка


def collect(config: Config, since: datetime) -> Result:
    patterns = {
        key: re.compile(r"(?<!\w)(?:" + "|".join(mp.keywords) + r")(?!\w)", re.IGNORECASE)
        for key, mp in config.marketplaces.items() if mp.keywords
    }
    items, errors = [], {}

    def run(src: Source):
        return src, src.fetch(since)

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(run, s) for s in config.sources]
        for src, fut in zip(config.sources, futures):
            try:
                _, fetched = fut.result()
            except Exception as e:  # один упавший сайт не должен ронять весь сбор
                errors[src.name] = f"{type(e).__name__}: {e}"
                continue
            for it in fetched:
                if not it.title:
                    continue
                if src.marketplace == "auto":
                    text = f"{it.title} {it.summary}"
                    it.marketplaces = {k for k, p in patterns.items() if p.search(text)}
                    if not it.marketplaces:
                        continue
                else:
                    it.marketplaces = {src.marketplace}
                items.append(it)

    return Result(_dedupe(items), errors)


def _dedupe(items: list[NewsItem]) -> list[NewsItem]:
    seen, out = set(), []
    for it in sorted(items, key=lambda i: i.published, reverse=True):
        key = it.url or it.title.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out
