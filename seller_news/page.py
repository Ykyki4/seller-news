"""HTML-страница с новостями дня и недели. Один самодостаточный файл: данные вшиты в
страницу как JSON, вкладки и фильтры работают на JS без сервера."""
import json
from datetime import datetime
from pathlib import Path

from .ai import Digest, ItemNote
from .models import Marketplace, NewsItem


def in_period(it: NewsItem, since: datetime) -> bool:
    if it.date_only:
        return it.published.date() >= since.astimezone(it.published.tzinfo).date()
    return it.published >= since


def build(items: list[NewsItem], marketplaces: dict[str, Marketplace], selected: list[str],
          periods: dict[str, tuple[str, datetime]], notes: dict[int, ItemNote],
          digests: dict[str, dict[str, Digest]], errors: dict[str, str], model: str | None) -> str:
    """periods: ключ -> (подпись, since). digests: ключ периода -> маркетплейс -> Digest.
    id новости — индекс в items, как и в notes."""
    data = {
        "generated": datetime.now().astimezone().strftime("%d.%m.%Y %H:%M"),
        "model": model,
        "marketplaces": [{"key": k, "name": marketplaces[k].name} for k in selected],
        "periods": [
            {
                "key": key,
                "label": label,
                "since": since.astimezone().strftime("%d.%m.%Y %H:%M"),
                "digests": {
                    mp: {"overview": d.overview,
                         "highlights": [{"title": h.title, "text": h.text, "ids": h.item_ids} for h in d.highlights]}
                    for mp, d in digests.get(key, {}).items()
                },
            }
            for key, (label, since) in periods.items()
        ],
        "items": [
            {
                "id": i,
                "title": it.title,
                "url": it.url,
                "source": it.source_name,
                "mps": sorted(it.marketplaces),
                "date": it.published.astimezone().strftime("%Y-%m-%d"),
                "time": "" if it.date_only else it.published.astimezone().strftime("%H:%M"),
                "text": it.summary,
                "periods": [k for k, (_, since) in periods.items() if in_period(it, since)],
                **({"ai": n.summary, "topic": n.topic, "imp": n.importance, "dup": n.duplicate_of}
                   if (n := notes.get(i)) else {}),
            }
            for i, it in enumerate(items)
        ],
        "errors": errors,
    }
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return TEMPLATE.replace("/*DATA*/null", payload)


def write(path: Path, html: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path.resolve()


TEMPLATE = r"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Новости селлеров</title>
<style>
:root {
  --bg: #f6f6f4; --card: #ffffff; --text: #1d1d1b; --muted: #6b6b66; --line: #e3e2dd;
  --accent: #2f5bd3; --ozon: #005bff; --wb: #a3248f; --hot: #c2410c; --hot-bg: #fff1e8;
  --chip: #efeee9;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #161615; --card: #20201e; --text: #ecebe6; --muted: #9a9993; --line: #33332f;
    --accent: #7ea0ff; --ozon: #5b93ff; --wb: #e06ccd; --hot: #fb923c; --hot-bg: #3a2416;
    --chip: #2b2b28;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text);
  font: 15px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
.wrap { max-width: 920px; margin: 0 auto; padding: 24px 16px 64px; }
header h1 { font-size: 24px; margin: 0 0 4px; }
.meta { color: var(--muted); font-size: 13px; }
.bar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin: 20px 0 8px; }
.seg { display: inline-flex; background: var(--chip); border-radius: 10px; padding: 3px; }
.seg button { border: 0; background: none; color: var(--muted); font: inherit; padding: 6px 14px;
  border-radius: 8px; cursor: pointer; }
.seg button.on { background: var(--card); color: var(--text); font-weight: 600;
  box-shadow: 0 1px 2px rgba(0,0,0,.12); }
label.check { display: inline-flex; gap: 6px; align-items: center; color: var(--muted); cursor: pointer;
  margin-left: auto; }
.topics { display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0 20px; }
.topics button { border: 1px solid var(--line); background: var(--card); color: var(--text); font: inherit;
  font-size: 13px; padding: 3px 10px; border-radius: 999px; cursor: pointer; }
.topics button.on { background: var(--accent); border-color: var(--accent); color: #fff; }
.topics button span { color: var(--muted); margin-left: 4px; }
.topics button.on span { color: rgba(255,255,255,.8); }
h2 { font-size: 18px; margin: 28px 0 12px; display: flex; align-items: center; gap: 8px; }
h2 .dot { width: 10px; height: 10px; border-radius: 50%; }
.digest { background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 16px 18px;
  margin-bottom: 12px; }
.digest p.ov { margin: 0 0 10px; }
.digest ol { margin: 0; padding-left: 20px; }
.digest li { margin: 6px 0; }
.digest li b { display: block; }
.digest .refs a { white-space: nowrap; font-size: 12px; color: var(--accent); margin-right: 8px; text-decoration: none; }
.day { color: var(--muted); font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: .04em;
  margin: 20px 0 6px; }
.item { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 12px 14px;
  margin-bottom: 8px; scroll-margin-top: 16px; }
.item.flash { outline: 2px solid var(--accent); }
.item .top { display: flex; gap: 8px; align-items: baseline; flex-wrap: wrap; font-size: 13px; color: var(--muted); }
.item .time { font-variant-numeric: tabular-nums; }
.tag { background: var(--chip); border-radius: 6px; padding: 0 7px; color: var(--text); }
.hot { background: var(--hot-bg); color: var(--hot); font-weight: 600; }
.mp { font-weight: 600; }
.item a.title { display: block; color: var(--text); font-weight: 600; text-decoration: none; margin: 4px 0 2px; }
.item a.title:hover { color: var(--accent); }
.item .ai { margin: 2px 0 0; }
.item details { margin-top: 6px; font-size: 13px; color: var(--muted); }
.item summary { cursor: pointer; }
.item .src { font-size: 13px; color: var(--muted); margin-top: 6px; }
.item .src a { color: var(--accent); }
.empty { color: var(--muted); padding: 8px 0; }
.errors { margin-top: 32px; color: var(--hot); font-size: 13px; }
@media (max-width: 560px) { label.check { margin-left: 0; } }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>Новости для селлеров</h1>
    <div class="meta" id="meta"></div>
  </header>
  <div class="bar">
    <div class="seg" id="periods"></div>
    <div class="seg" id="mps"></div>
    <label class="check"><input type="checkbox" id="important"> только важные</label>
  </div>
  <div class="topics" id="topics"></div>
  <main id="main"></main>
  <div class="errors" id="errors"></div>
</div>
<script>
const DATA = /*DATA*/null;
const MONTHS = ["января","февраля","марта","апреля","мая","июня","июля","августа","сентября","октября","ноября","декабря"];
const WEEKDAYS = ["воскресенье","понедельник","вторник","среда","четверг","пятница","суббота"];
const state = { period: DATA.periods[0].key, mp: "all", topic: null, important: false };
try { Object.assign(state, JSON.parse(localStorage.getItem("seller-news-ui") || "{}"), { topic: null }); } catch (e) {}
if (!DATA.periods.some(p => p.key === state.period)) state.period = DATA.periods[0].key;
if (state.mp !== "all" && !DATA.marketplaces.some(m => m.key === state.mp)) state.mp = "all";
const byId = Object.fromEntries(DATA.items.map(i => [i.id, i]));
const hasAI = DATA.items.some(i => i.ai);

const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"})[c]);
const el = (id) => document.getElementById(id);
const mpName = k => (DATA.marketplaces.find(m => m.key === k) || {}).name || k;
function dayLabel(iso) {
  const d = new Date(iso + "T12:00:00");
  return `${d.getDate()} ${MONTHS[d.getMonth()]}, ${WEEKDAYS[d.getDay()]}`;
}
function save() { try { localStorage.setItem("seller-news-ui", JSON.stringify({ period: state.period, mp: state.mp, important: state.important })); } catch (e) {} }

function seg(container, options, current, onPick) {
  container.innerHTML = options.map(o => `<button data-k="${esc(o.key)}" class="${o.key === current ? "on" : ""}">${esc(o.label)}</button>`).join("");
  container.querySelectorAll("button").forEach(b => b.onclick = () => onPick(b.dataset.k));
}

function visibleItems() {
  return DATA.items.filter(i =>
    i.periods.includes(state.period) &&
    (state.mp === "all" || i.mps.includes(state.mp)) &&
    i.dup == null);
}

function render() {
  save();
  const period = DATA.periods.find(p => p.key === state.period);
  el("meta").textContent = `Обновлено ${DATA.generated} · период ${period.label}: с ${period.since}` +
    (DATA.model ? ` · обработано ${DATA.model}` : "");
  seg(el("periods"), DATA.periods.map(p => ({ key: p.key, label: p.label })), state.period, k => { state.period = k; state.topic = null; render(); });
  seg(el("mps"), [{ key: "all", label: "Все" }, ...DATA.marketplaces.map(m => ({ key: m.key, label: m.name }))], state.mp, k => { state.mp = k; render(); });
  el("important").checked = state.important;
  el("important").parentElement.style.display = hasAI ? "" : "none";

  const base = visibleItems();
  const counts = {};
  base.forEach(i => { if (i.topic) counts[i.topic] = (counts[i.topic] || 0) + 1; });
  const topics = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  el("topics").innerHTML = topics.map(([t, n]) =>
    `<button data-t="${esc(t)}" class="${t === state.topic ? "on" : ""}">${esc(t)}<span>${n}</span></button>`).join("");
  el("topics").querySelectorAll("button").forEach(b => b.onclick = () => { state.topic = state.topic === b.dataset.t ? null : b.dataset.t; render(); });

  const items = base.filter(i => (!state.topic || i.topic === state.topic) && (!state.important || (i.imp || 0) >= 3));
  const mps = state.mp === "all" ? DATA.marketplaces.map(m => m.key) : [state.mp];
  let html = "";
  for (const mp of mps) {
    const mine = items.filter(i => i.mps.includes(mp));
    html += `<h2><span class="dot" style="background:var(--${esc(mp)}, var(--accent))"></span>${esc(mpName(mp))} <span class="meta">${mine.length}</span></h2>`;
    const d = period.digests[mp];
    if (d && !state.topic) html += digestHTML(d);
    if (!mine.length) { html += `<div class="empty">Новостей нет.</div>`; continue; }
    let day = null;
    for (const i of mine) {
      if (i.date !== day) { day = i.date; html += `<div class="day">${dayLabel(day)}</div>`; }
      html += itemHTML(i, mp);
    }
  }
  el("main").innerHTML = html;
  el("main").querySelectorAll("a[data-jump]").forEach(a => a.onclick = (e) => {
    e.preventDefault();
    const target = document.querySelector(`[data-item="${a.dataset.jump}"]`);
    if (!target) return;
    target.scrollIntoView({ behavior: "smooth", block: "center" });
    target.classList.add("flash"); setTimeout(() => target.classList.remove("flash"), 1500);
  });
  const errs = Object.entries(DATA.errors);
  el("errors").innerHTML = errs.length ? "Не удалось получить: " + errs.map(([s, e]) => `<div>• ${esc(s)}: ${esc(e)}</div>`).join("") : "";
}

function digestHTML(d) {
  const refs = ids => ids.filter(id => byId[id]).map(id => {
    const it = byId[id].dup != null ? byId[byId[id].dup] || byId[id] : byId[id];
    return `<a href="#" data-jump="${it.id}">${esc(it.source)}</a>`;
  }).join("");
  return `<div class="digest"><p class="ov">${esc(d.overview)}</p>` +
    (d.highlights.length ? `<ol>${d.highlights.map(h => `<li><b>${esc(h.title)}</b>${esc(h.text)} <span class="refs">${refs(h.ids)}</span></li>`).join("")}</ol>` : "") +
    `</div>`;
}

function itemHTML(i, mp) {
  const dups = DATA.items.filter(d => d.dup === i.id);
  const tags = [
    i.time ? `<span class="time">${esc(i.time)}</span>` : "",
    i.imp === 3 ? `<span class="tag hot">важно</span>` : "",
    i.topic ? `<span class="tag">${esc(i.topic)}</span>` : "",
    i.mps.length > 1 ? `<span>${i.mps.map(mpName).map(esc).join(" · ")}</span>` : "",
  ].join("");
  const body = i.ai
    ? `<p class="ai">${esc(i.ai)}</p>` + (i.text ? `<details><summary>текст источника</summary>${esc(i.text)}</details>` : "")
    : (i.text ? `<p class="ai">${esc(i.text.length > 400 ? i.text.slice(0, 400) + " …" : i.text)}</p>` : "");
  const also = dups.length ? ` · также: ${dups.map(d => `<a href="${esc(d.url)}" target="_blank" rel="noopener">${esc(d.source)}</a>`).join(", ")}` : "";
  return `<article class="item" data-item="${i.id}"><div class="top">${tags}</div>` +
    `<a class="title" href="${esc(i.url)}" target="_blank" rel="noopener">${esc(i.title)}</a>${body}` +
    `<div class="src">${esc(i.source)} · <a href="${esc(i.url)}" target="_blank" rel="noopener">открыть</a>${also}</div></article>`;
}

el("important").onchange = e => { state.important = e.target.checked; render(); };
render();
</script>
</body>
</html>
"""
