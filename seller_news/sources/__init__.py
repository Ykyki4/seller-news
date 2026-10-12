"""Источники новостей. Все модули этого пакета импортируются автоматически,
так что для нового типа сайта достаточно положить сюда файл с классом,
помеченным @register("тип")."""
import importlib
import pkgutil

from .base import Source, register, source_class

for _m in pkgutil.iter_modules(__path__):
    if _m.name != "base":
        importlib.import_module(f"{__name__}.{_m.name}")

__all__ = ["Source", "register", "source_class"]
