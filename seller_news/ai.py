"""Обработка собранных новостей через Claude: короткая выжимка и тема для каждой новости,
важность, поиск дублей между источниками и обзор «главного» по каждому маркетплейсу."""
import json
from dataclasses import dataclass, field

from .models import Marketplace, NewsItem

DEFAULT_MODEL = "claude-opus-5-5"

TOPICS = [
    "Тарифы и комиссии", "Логистика и склады", "Продвижение и реклама", "Акции и цены",
    "Финансы и выплаты", "Правила и штрафы", "Карточки и контент", "Аналитика",
    "API и интеграции", "Мероприятия и обучение", "Рынок и конкуренты", "Другое",
]

SYSTEM = """Ты — редактор дайджеста для продавцов (селлеров) маркетплейсов Ozon и Wildberries.
Тебе дают новости, собранные из официальных каналов маркетплейсов, их сайтов и отраслевых СМИ.
Читатель — владелец или менеджер магазина на маркетплейсе. Ему важно быстро понять, что изменилось
в правилах, тарифах, логистике, выплатах и инструментах и что ему нужно сделать.

Пиши по-русски, коротко и по делу, без рекламных оборотов. Не выдумывай факты, которых нет
в тексте новости: если в новости нет подробностей, так и пиши кратко."""

ITEMS_TASK = """Для каждой новости заполни:
- summary: 1–2 предложения — что произошло и что это значит для продавца (сроки, суммы, если есть);
- topic: одна тема из списка;
- importance: 3 — затрагивает многих продавцов и требует действий или меняет деньги (тарифы,
  штрафы, выплаты, обязательные правила); 2 — полезно знать; 1 — мелочь, анонсы мероприятий,
  реклама, общие рыночные новости;
- duplicate_of: если это та же новость, что и другая в списке (например, канал и сайт написали
  об одном и том же), укажи id более полной версии; иначе null."""

DIGEST_TASK = """Для каждого маркетплейса из списка составь обзор:
- overview: 2–3 предложения — общая картина за период;
- highlights: 3–7 главных изменений по убыванию важности. title — короткий заголовок,
  text — 1–2 предложения, что изменилось и что делать продавцу, item_ids — id новостей,
  на которых основан пункт. Если новостей мало, пунктов может быть меньше.
Если по маркетплейсу новостей нет, overview — «Новостей нет», highlights — пустой список."""


def _schema(with_items: bool, marketplace_keys: list[str]) -> dict:
    digest = {
        "type": "object",
        "properties": {
            "key": {"type": "string", "enum": marketplace_keys},
            "overview": {"type": "string"},
            "highlights": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "text": {"type": "string"},
                        "item_ids": {"type": "array", "items": {"type": "integer"}},
                    },
                    "required": ["title", "text", "item_ids"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["key", "overview", "highlights"],
        "additionalProperties": False,
    }
    props = {"digests": {"type": "array", "items": digest}}
    if with_items:
        props["items"] = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "summary": {"type": "string"},
                    "topic": {"type": "string", "enum": TOPICS},
                    "importance": {"type": "integer", "enum": [1, 2, 3]},
                    "duplicate_of": {"type": ["integer", "null"]},
                },
                "required": ["id", "summary", "topic", "importance", "duplicate_of"],
                "additionalProperties": False,
            },
        }
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


@dataclass
class Highlight:
    title: str
    text: str
    item_ids: list[int]


@dataclass
class Digest:
    overview: str
    highlights: list[Highlight] = field(default_factory=list)


@dataclass
class ItemNote:
    summary: str
    topic: str
    importance: int
    duplicate_of: int | None


class Editor:
    """ai_cfg — секция [ai] из sources.toml: model, effort, proxy."""

    def __init__(self, ai_cfg: dict):
        try:
            import anthropic
        except ImportError:
            raise RuntimeError("нужен пакет anthropic: pip install anthropic") from None
        self._anthropic = anthropic
        proxy = ai_cfg.get("proxy", "system")
        http_client = None
        if proxy == "direct":
            http_client = anthropic.DefaultHttpxClient(trust_env=False)
        elif proxy != "system":
            http_client = anthropic.DefaultHttpxClient(proxy=proxy)
        # ключ — из ANTHROPIC_API_KEY (или профиль `ant auth login`)
        self.client = anthropic.Anthropic(http_client=http_client)
        self.model = ai_cfg.get("model", DEFAULT_MODEL)
        self.effort = ai_cfg.get("effort", "medium")

    def annotate(self, items: list[NewsItem], marketplaces: dict[str, Marketplace], period: str):
        """Заметки по каждой новости + обзоры. Возвращает (dict id -> ItemNote, dict key -> Digest).
        id новости — её индекс в items."""
        data = self._ask(items, marketplaces, period, with_items=True)
        notes = {}
        for n in data["items"]:
            if 0 <= n["id"] < len(items):
                dup = n["duplicate_of"]
                notes[n["id"]] = ItemNote(n["summary"], n["topic"], n["importance"],
                                          dup if dup is not None and dup != n["id"] and 0 <= dup < len(items) else None)
        return notes, self._digests(data)

    def digest(self, items: list[NewsItem], marketplaces: dict[str, Marketplace], period: str):
        """Только обзоры (для короткого периода, когда заметки по новостям уже есть)."""
        return self._digests(self._ask(items, marketplaces, period, with_items=False))

    def _ask(self, items, marketplaces, period, with_items):
        news = [
            {
                "id": i,
                "marketplaces": sorted(it.marketplaces),
                "source": it.source_name,
                "date": it.published.astimezone().strftime("%d.%m.%Y" if it.date_only else "%d.%m.%Y %H:%M"),
                "title": it.title,
                "text": it.summary,
            }
            for i, it in enumerate(items)
        ]
        mp_list = ", ".join(f"{k} — {mp.name}" for k, mp in marketplaces.items())
        task = (ITEMS_TASK + "\n\n" if with_items else "") + DIGEST_TASK
        prompt = (
            f"Период: {period}.\nМаркетплейсы: {mp_list}.\n\n{task}\n\n"
            f"Новости (JSON):\n{json.dumps(news, ensure_ascii=False)}"
        )
        with self.client.beta.messages.stream(
            model=self.model,
            max_tokens=64000,
            system=SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            output_config={
                "effort": self.effort,
                "format": {"type": "json_schema", "schema": _schema(with_items, list(marketplaces))},
            },
            # при отказе фильтров безопасности запрос сам перезапускается на резервной модели
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        ) as stream:
            msg = stream.get_final_message()
        if msg.stop_reason == "refusal":
            raise RuntimeError(f"модель отказалась обрабатывать новости: {msg.stop_details}")
        if msg.stop_reason == "max_tokens":
            raise RuntimeError("ответ модели обрезан по max_tokens — слишком много новостей за период")
        text = next(b.text for b in msg.content if b.type == "text")
        return json.loads(text)

    @staticmethod
    def _digests(data) -> dict[str, Digest]:
        return {
            d["key"]: Digest(d["overview"], [Highlight(h["title"], h["text"], h["item_ids"]) for h in d["highlights"]])
            for d in data["digests"]
        }
