import os
import shutil
import textwrap
from datetime import datetime

from .collector import Result
from .models import Marketplace

MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля",
          "августа", "сентября", "октября", "ноября", "декабря"]
WEEKDAYS = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]


class Style:
    def __init__(self, enabled: bool):
        if enabled and os.name == "nt":
            os.system("")  # включает ANSI-последовательности в консоли Windows
        self.on = enabled

    def _c(self, code, s):
        return f"\033[{code}m{s}\033[0m" if self.on else s

    def bold(self, s): return self._c("1", s)
    def dim(self, s): return self._c("2", s)
    def cyan(self, s): return self._c("36", s)
    def yellow(self, s): return self._c("33", s)
    def red(self, s): return self._c("31", s)
    def mp(self, key, s): return self._c({"ozon": "1;34", "wb": "1;35"}.get(key, "1;32"), s)


def render(result: Result, marketplaces: dict[str, Marketplace], selected: list[str],
           since: datetime, period_label: str, show_summary: bool, color: bool) -> str:
    st = Style(color)
    width = min(shutil.get_terminal_size((100, 20)).columns, 110)
    now = datetime.now().astimezone()
    out = [
        st.bold(f"Новости для селлеров {period_label}"),
        st.dim(f"{since.astimezone():%d.%m.%Y %H:%M} — {now:%d.%m.%Y %H:%M}"),
        "",
    ]

    for key in selected:
        mp = marketplaces[key]
        items = [i for i in result.items if key in i.marketplaces]
        out.append(st.mp(key, f"━━ {mp.name.upper()} ({len(items)}) " + "━" * max(0, width - len(mp.name) - 12)))
        if not items:
            out += [st.dim("  Новостей нет."), ""]
            continue
        day = None
        for it in items:
            local = it.published.astimezone()
            if local.date() != day:
                day = local.date()
                out.append("")
                out.append(st.yellow(f"  {day.day} {MONTHS[day.month - 1]}, {WEEKDAYS[day.weekday()]}"))
            head = "  " + ("     " if it.date_only else f"{local:%H:%M}") + "  "
            pad = " " * len(head)
            title = textwrap.wrap(it.title, width - len(head)) or [""]
            out.append(st.dim(head) + st.bold(title[0]))
            out += [pad + st.bold(t) for t in title[1:]]
            if show_summary and it.summary:
                summary = textwrap.shorten(it.summary, 400, placeholder=" …")
                out += [pad + line for line in textwrap.wrap(summary, width - len(pad))]
            out.append(pad + st.dim(it.source_name + "  ") + st.cyan(it.url))
        out.append("")

    if result.errors:
        out.append(st.red("Не удалось получить:"))
        out += [st.red(f"  • {name}: {err}") for name, err in result.errors.items()]
    return "\n".join(out)
