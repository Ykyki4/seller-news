import re
from abc import ABC, abstractmethod
from datetime import datetime

from ..http import make_session
from ..models import NewsItem

_REGISTRY: dict[str, type["Source"]] = {}


def register(type_name: str):
    """Регистрирует класс источника под именем, которое пишется в type = "..." в sources.toml."""
    def deco(cls):
        _REGISTRY[type_name] = cls
        cls.type_name = type_name
        return cls
    return deco


def source_class(type_name: str) -> type["Source"]:
    try:
        return _REGISTRY[type_name]
    except KeyError:
        known = ", ".join(sorted(_REGISTRY)) or "нет"
        raise ValueError(f"неизвестный тип источника '{type_name}' (есть: {known})") from None


class Source(ABC):
    type_name = ""

    def __init__(self, cfg: dict):
        self.id: str = cfg["id"]
        self.name: str = cfg.get("name", self.id)
        # "ozon", "wb", ... или "auto" — определять по ключевым словам
        self.marketplace: str = cfg.get("marketplace", "auto")
        self.session = make_session(cfg.get("proxy", "system"))
        self.cfg = cfg

    @abstractmethod
    def fetch(self, since: datetime) -> list[NewsItem]:
        """Вернуть новости, опубликованные не раньше since."""

    def item(self, title: str, url: str, published: datetime, summary: str = "") -> NewsItem:
        return NewsItem(
            title=clean_text(title),
            url=url,
            published=published,
            source_id=self.id,
            source_name=self.name,
            summary=clean_text(summary),
        )


def clean_text(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()
