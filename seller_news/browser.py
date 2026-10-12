"""Загрузка страниц через настоящий Chromium (Playwright) — для сайтов с JS-антиботом,
которые не отдают содержимое обычному HTTP-запросу (seller.ozon.ru, dev.wildberries.ru)."""
from pathlib import Path

PROFILES_DIR = Path(__file__).resolve().parent.parent / ".browser-profiles"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)


class Browser:
    """Один Chromium на источник. Профиль хранится в .browser-profiles/<profile>, чтобы
    куки антибота переживали запуски и проверка проходилась реже.

    proxy: "system" / "direct" / URL — как у обычных источников.
    headless=False — окно за пределами экрана: антибот WB распознаёт headless-режим."""

    def __init__(self, profile: str, proxy: str = "system", headless: bool = True):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise RuntimeError(
                "нужен Playwright: pip install playwright && python -m playwright install chromium"
            ) from None
        args = ["--disable-blink-features=AutomationControlled"]
        kwargs = {}
        if proxy == "direct":
            args.append("--no-proxy-server")
        elif proxy != "system":
            kwargs["proxy"] = {"server": proxy}
        if not headless:
            args.append("--window-position=-32000,-32000")
        self._pw = sync_playwright().start()
        try:
            self._ctx = self._pw.chromium.launch_persistent_context(
                PROFILES_DIR / profile, headless=headless, args=args,
                user_agent=USER_AGENT, locale="ru-RU", **kwargs,
            )
        except Exception:
            self._pw.stop()
            raise
        self._page = self._ctx.pages[0] if self._ctx.pages else self._ctx.new_page()

    def html(self, url: str, wait_for: str, timeout: float = 60) -> str:
        """Открыть url и дождаться появления элемента wait_for (CSS) — признака,
        что антибот пройден и контент отрисован."""
        self._page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
        self._page.wait_for_selector(wait_for, timeout=timeout * 1000)
        return self._page.content()

    def close(self):
        self._ctx.close()
        self._pw.stop()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
