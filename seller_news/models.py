from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class NewsItem:
    title: str
    url: str
    published: datetime  # всегда timezone-aware
    source_id: str
    source_name: str
    summary: str = ""
    marketplaces: set[str] = field(default_factory=set)
    date_only: bool = False  # у источника есть только дата, время 00:00 условное


@dataclass
class Marketplace:
    key: str
    name: str
    keywords: list[str]
