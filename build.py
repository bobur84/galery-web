#!/usr/bin/env python3
"""Сборка публичного сайта galery.uz на трёх языках.

Из шаблонов src/*.html и словарей i18n/<язык>.json собирает готовые
страницы в dist/<язык>/: главную, политику конфиденциальности и условия
использования — по три версии каждой.

Почему отдельные страницы на язык, а не подмена текста на JS:
  * поисковик видит настоящий текст на нужном языке (у каждой версии свой
    адрес, свой <title>, свой hreflang) — иначе в индекс попадёт один язык;
  * посетителю не мигает чужой язык, пока грузится скрипт.

Какой язык показать с корня galery.uz — решает nginx (страна по IP + cookie
с выбором посетителя), см. deploy/nginx-report.conf в репозитории galereya-report.

Зависимостей нет, только стандартная библиотека. Сборка идёт в GitHub Actions
(.github/workflows/deploy.yml), на сервер уходит только готовый dist/.

Плейсхолдеры в шаблонах и в текстах документов:
    {{ключ}}   — значение из словаря, экранируется (безопасно и в тексте, и в атрибуте)
    {{!ключ}}  — значение вставляется как есть (для строк с <em> и <br>)
    {{js.имя}} — строка form.<имя> в виде литерала JavaScript (в кавычках)
Реквизиты компании (ключи co.*) — общие на все языки, лежат в company.json.
"""

import argparse
import html
import hashlib
import json
import pathlib
import re
import shutil
import sys

SITE = "https://galery.uz"
# Порядок = порядок кнопок в переключателе языков. Узбекский первым: это
# государственный язык страны, где работает компания.
# На выбор языка по стране этот список НЕ влияет — за него отвечает nginx
# (карта $lang_by_country в galereya-report/deploy/nginx-report.conf).
LANGS = ["uz", "ru", "en"]
LABELS = {"uz": "UZ", "ru": "RU", "en": "EN"}

# Страницы сайта. slug — адрес внутри языка: "" это /ru/, "privacy" это /ru/privacy/.
# doc — имя файла с текстом в legal/ (<doc>.<язык>.html); у главной его нет.
# ФОТО. Все места под фотографии перечислены в photos.json: номер → описание и файл.
# Пока файла нет, на сайте видна заглушка «ФОТО N» с описанием — так сразу ясно,
# какое фото куда ставить. Фото кладутся в img/photos/, имя — в поле file.
# В шаблоне место под фото пишется ключом {{ph.N}} (N — номер из photos.json).
PHOTOS = {}


def photo(pid, cls=""):
    """Место под фото: <img>, если файл уже есть, иначе подписанная заглушка."""
    if pid not in PHOTOS:
        raise KeyError("нет фото %s в photos.json" % pid)
    item = PHOTOS[pid]
    label = html.escape(item.get("label", pid))
    if item.get("file"):
        crop = ' class="crop-%s"' % item["crop"] if item.get("crop") else ""
        # "hover": второе фото — плавно появляется при наведении мыши
        # "hover_crop" — то же, что crop, но для второго фото
        hcrop = " crop-%s" % item["hover_crop"] if item.get("hover_crop") else ""
        hover = ('<img class="ph-hover%s" src="/img/photos/%s" alt="" loading="lazy">'
                 % (hcrop, html.escape(item["hover"], quote=True))) if item.get("hover") else ""
        return ('<figure class="ph has-img%s %s"><img src="/img/photos/%s" alt=""%s loading="lazy">%s</figure>'
                % (" has-hover" if hover else "", cls, html.escape(item["file"], quote=True), crop, hover))
    return ('<figure class="ph %s" data-photo="%s"><figcaption class="ph-cap">'
            '<b>ФОТО %s</b><span>%s</span></figcaption></figure>'
            % (cls, label, label, html.escape(item["desc"])))


# Схемы профилей по типу изделия — второе изображение карточки товара (при наведении)
# и чертёж в окне товара, пока нет настоящего чертежа.
PROFILE = {
    "moulding": '<path d="M20 10 L60 10 L60 30 Q80 40 80 50 Q80 60 60 70 L60 90 L20 90 Z"/>',
    "panel": '<path d="M15 10 L15 90 M35 10 L35 90 M55 10 L55 90 M75 10 L75 90 M15 10 L85 10 M15 90 L85 90"/>',
    "plinth": '<path d="M20 90 L20 10 L45 10 L45 40 Q60 45 70 60 L80 60 L80 90 Z"/>',
    "cornice": '<path d="M15 15 L85 15 L85 30 Q60 35 50 55 Q40 75 30 80 L15 85 Z"/>',
}

# Товары TRIMLINE — все модели 3D-каталога. Фото — из photos.json (id = код без дефиса).
# Размеры известны не у всех: остальные «по каталогу». Наличие (1 — есть, 0 — под заказ)
# указано только там, где оно известно; None — пометку не показываем.
# Описание: своё у части моделей (bk.i*), у остальных — общее для типа (show.d*).
SIZES = {"M11": "25×12", "M13": "40×18", "M21": "25×14", "P7": "80×15", "P10": "100×16",
         "C-1": "70×40", "C-2": "71×41", "C-3": "220×92"}
STOCK = {"M21": 1, "M13": 1, "W9": 1, "P7": 1, "P10": 1, "C-3": 1}
HITS = {"M21", "M13", "W9", "C-3"}
DESC = {"M21": "bk.i1", "M13": "bk.i2", "M56": "bk.i3", "W9": "bk.i4",
        "P7": "bk.i6", "P10": "bk.i7", "C-3": "bk.i8"}
TYPE_DESC = {"moulding": "show.d1", "panel": "show.d2", "plinth": "show.d3", "cornice": "show.d4"}
MODELS = [("moulding", ["M11", "M12", "M13", "M21", "M22", "M23", "M31", "M32", "M33",
                        "M41", "M42", "M43", "M51", "M52", "M53", "M54", "M55", "M56"]),
          ("panel", ["W%d" % i for i in range(1, 11)]),
          ("plinth", ["P%d" % i for i in range(1, 12)]),
          ("cornice", ["C-1", "C-2", "C-3"])]
# (код, фото-id, тип, размер, наличие, хит, ключ описания)
PRODUCTS = [(c, c.replace("-", ""), cat,
             "%s {{unit.mm}}" % SIZES[c] if c in SIZES else "{{bk.size_cat}}",
             STOCK.get(c), 1 if c in HITS else 0, DESC.get(c, TYPE_DESC[cat]))
            for cat, codes in MODELS for c in codes]
# Лента товаров на главной и на странице плинтусов
RIBBON = ["M11", "M13", "M21", "M33", "M42", "M56", "P1", "P5", "P7", "P10", "C-1", "C-3"]
# Витрина на главной: широкая лента фото товаров разных направлений.
# (номер фото из photos.json, номер направления в DIRECTIONS). Фото без файла пропускаются.
SHOWCASE = [("16", 0), ("19", 1), ("22", 2), ("7", 3), ("18", 0), ("23", 2),
            ("21", 1), ("26", 3), ("17", 0), ("24", 2), ("27", 3), ("5", 1)]


def profile_svg(cat):
    return ('<svg class="prof-svg" viewBox="0 0 100 100" fill="none" stroke="currentColor" stroke-width="2.5" '
            'stroke-linejoin="round" aria-hidden="true">%s</svg>' % PROFILE[cat])


# Пять направлений компании. У каждого — своя страница /<язык>/<slug>/, свой цвет
# (класс d1…d5 в css/home.css) и список брендов. Тексты направления — ключи cat.<key>_t/_d
# в i18n. Бренд с адресом ведёт на свой каталог; без адреса — просто название.
DIRECTIONS = [
    {"slug": "plintusy",   "key": "c1", "brands": [
        ("IDEAL", None), ("NMC", "/nmc/"), ("PRIME DECOR", "/primedecor/"),
        ("TRIMLINE", "trimline"), ("MARBET", "/marbet/")]},
    {"slug": "laminat",    "key": "c2", "brands": [("ART FLOOR", None)]},
    {"slug": "paneli",     "key": "c3", "brands": [("DELUX", None), ("JINHAO Bamboo", None)]},
    {"slug": "santehnika", "key": "c5", "brands": [
        ("WASSERMANN", "/wassermann/"), ("RVK", "/rvk/"), ("TIM", "/tim/")]},
    {"slug": "dveri",      "key": "c6", "brands": [("RUDA", None)]},
]

PAGES = [
    {"slug": "",        "template": "index.html", "doc": None},
    {"slug": "privacy", "template": "legal.html", "doc": "privacy"},
    {"slug": "terms",   "template": "legal.html", "doc": "terms"},
] + [
    {"slug": d["slug"], "template": "direction.html", "doc": None, "dir": i}
    for i, d in enumerate(DIRECTIONS)
] + [
    # 3D-каталог TRIMLINE: отдельная страница, чтобы главная не грузила 3D.
    {"slug": "3d",      "template": "showroom.html", "doc": None},
    # Каталог бренда TRIMLINE — образец оформления для всех каталогов брендов.
    {"slug": "trimline", "template": "brand.html", "doc": None},
]

HERE = pathlib.Path(__file__).resolve().parent
PLACEHOLDER = re.compile(r"\{\{(!?)([a-z][\w.]*)\}\}")
# Ключи, которые вычисляет сама сборка. Это готовая разметка — не экранируются.
GENERATED = {"lang", "canonical", "alternates", "lang_switch", "legal_body",
             "page.title", "page.desc", "page.h1",
             "dir.n", "dir.cls", "dir.t", "dir.d", "dir.tags", "dir.brand_list",
             "dir.others_list", "dir.extra", "dir.gallery", "dir.photo",
             "site_header", "site_footer", "dir_strip", "foot_dirs", "dir_tiles", "products",
             "bk_items", "showcase"}
# Заполняются вручную в company.json; пока не заполнены — сборка предупреждает.
UNSET = "— уточнить —"


def url(lang, slug):
    return "%s/%s/" % (SITE, lang) if not slug else "%s/%s/%s/" % (SITE, lang, slug)


def path(lang, slug):
    return "/%s/" % lang if not slug else "/%s/%s/" % (lang, slug)


def alternates(slug):
    """Ссылки hreflang: говорят поисковику, что это одна страница на трёх языках."""
    out = ['<link rel="alternate" hreflang="%s" href="%s">' % (code, url(code, slug))
           for code in LANGS]
    out.append('<link rel="alternate" hreflang="x-default" href="%s/">' % SITE)
    return "\n".join(out)


def lang_switch(lang, slug, aria):
    """Переключатель языков в шапке. Ведёт на ту же страницу на другом языке."""
    items = "".join(
        '<a href="%s" hreflang="%s" lang="%s"%s>%s</a>' % (
            path(code, slug), code, code,
            ' class="on" aria-current="true"' if code == lang else "",
            LABELS[code])
        for code in LANGS)
    return '<div class="langs" role="group" aria-label="%s">%s</div>' % (
        html.escape(aria, quote=True), items)


def expand(text, words, lang, where):
    """Подставить плейсхолдеры. Возвращает (результат, множество использованных ключей)."""
    used = set()

    def sub(m):
        raw, key = m.group(1), m.group(2)
        if key.startswith("ph."):
            return photo(key[3:])
        used.add(key)
        lookup = "form." + key[3:] if key.startswith("js.") else key
        if lookup not in words:
            raise KeyError("%s (%s): нет ключа %s" % (where, lang, lookup))
        if key.startswith("js."):
            # строка формы как литерал JS — json.dumps сам ставит кавычки и экранирует
            return json.dumps(words[lookup], ensure_ascii=False)
        if raw or key in GENERATED:
            return words[key]
        return html.escape(words[key], quote=True)

    # Несколько проходов: значения словаря сами могут содержать плейсхолдеры —
    # например, текст согласия со ссылкой на /{{lang}}/privacy/.
    # Шапка — общий кусок с ключами внутри, в ней полоса направлений — тоже с ключами,
    # поэтому проходов больше одного.
    for _ in range(6):
        new = PLACEHOLDER.sub(sub, text)
        if new == text:
            break
        text = new
    left = PLACEHOLDER.search(text)
    if left:
        raise KeyError("%s (%s): не подставлен %s" % (where, lang, left.group(0)))
    return text, used


def brand_names(i):
    """Подпись «бренды» направления. У дверей — переводимая строка cat.c6_tags."""
    d = DIRECTIONS[i]
    if d["key"] == "c6":
        return "{{cat.c6_tags}}"
    return html.escape(" · ".join(n for n, _ in d["brands"]))


def dir_links(lang, active):
    """Ссылки на пять направлений (текущее подсвечено)."""
    return "".join('<a href="%s"%s>{{cat.%s_t}}</a>' % (
        path(lang, d["slug"]), ' class="on" aria-current="page"' if d["slug"] == active else "",
        d["key"]) for d in DIRECTIONS)


def dir_strip(lang, active):
    """Полоса под шапкой: пять направлений, справа отдельно — кнопка 3D-шоурума."""
    return ('<div class="strip-dirs">%s</div><a class="strip-3d%s" href="%s">'
            '<span class="strip-3d-i" aria-hidden="true">3D</span>{{bk.showroom}}</a>'
            % (dir_links(lang, active), " on" if active == "3d" else "", path(lang, "3d")))


def dir_tiles(lang, skip=None):
    """Плитки пяти направлений с фото (ФОТО 4–8). На странице направления — без текущего."""
    out = []
    for i, d in enumerate(DIRECTIONS):
        if i == skip:
            continue
        out.append('<a class="tile" href="%s">%s<div class="tile-b"><span class="tile-n">0%d</span>'
                   '<h3>{{cat.%s_t}}</h3><p>{{cat.%s_d}}</p><span class="tile-br">{{cat.brands_lbl}}: %s</span>'
                   '<span class="tile-go">{{hero.btn_catalog}} <i aria-hidden="true">→</i></span></div></a>'
                   % (path(lang, d["slug"]), photo(str(4 + i)), i + 1, d["key"], d["key"],
                      brand_names(i)))
    return "\n      ".join(out)


def showcase(lang):
    """Витрина главной: фото + подпись направления, ссылка на его страницу.
    Ряд повторён дважды — так лента крутится по кругу без шва."""
    items = []
    for pid, di in SHOWCASE:
        item = PHOTOS.get(pid, {})
        if not item.get("file"):
            continue
        d = DIRECTIONS[di]
        crop = ' class="crop-%s"' % item["crop"] if item.get("crop") else ""
        items.append('<a class="sc-item" href="%s"><img src="/img/photos/%s" alt=""%s loading="lazy">'
                     '<span class="sc-cap"><i>0%d</i>{{cat.%s_t}}</span></a>'
                     % (path(lang, d["slug"]), html.escape(item["file"], quote=True), crop, di + 1, d["key"]))
    row = "".join(items)
    return '<div class="sc-row">%s</div><div class="sc-row" aria-hidden="true">%s</div>' % (row, row)


def products_row(lang):
    """Лента товаров TRIMLINE. Без фото — заглушка, при наведении схема профиля."""
    out = []
    for code, pid, cat, size, stock, hit, _ in PRODUCTS:
        if code not in RIBBON:
            continue
        prof = "" if PHOTOS[pid].get("file") else '<span class="pc-prof">%s</span>' % profile_svg(cat)
        out.append('<a class="pcard" href="%s?q=%s"><div class="pc-img">%s%s%s</div>'
                   '<div class="pc-b"><span class="pc-code">%s<i>|</i>{{bk.n_%s}}</span>'
                   '<span class="pc-size">%s</span></div></a>'
                   % (path(lang, "trimline"), code, photo(pid), prof,
                      '<span class="pc-hit">{{bk.hit}}</span>' if hit else "", code, cat, size))
    return "\n        ".join(out)


def bk_items():
    """Список товаров для каталога TRIMLINE (его читает скрипт страницы)."""
    out = []
    for code, pid, cat, size, stock, hit, desc in PRODUCTS:
        item = PHOTOS[pid]
        src = "/img/photos/" + item["file"] if item.get("file") else ""
        out.append('<li data-code="%s" data-cat="%s" data-size="%s" data-len="2400 {{unit.mm}}" '
                   'data-stock="%s" data-hit="%d" data-photo="%s" data-crop="%s" data-ph="%s" data-desc="%s">'
                   '<span class="n">TRIMLINE %s · {{bk.n_%s}}</span><span class="d">{{%s}}</span></li>'
                   % (code, cat, size, "" if stock is None else stock, hit,
                      html.escape(src, quote=True), html.escape(item.get("crop", ""), quote=True),
                      html.escape(item.get("label", pid), quote=True),
                      html.escape(item["desc"], quote=True), code, cat, desc))
    return "\n  ".join(out)


def direction_words(i, lang, words):
    """Значения для страницы направления (шаблон direction.html). Возвращает
    ключи словаря, которые ушли на страницу, — для проверки неиспользуемых."""
    d = DIRECTIONS[i]
    k = d["key"]
    esc = lambda t: html.escape(t, quote=True)
    t, desc = words["cat.%s_t" % k], words["cat.%s_d" % k]
    words["dir.n"] = "0%d" % (i + 1)
    words["dir.photo"] = photo(str(4 + i), "ph-hero")
    words["dir.gallery"] = "".join(photo(str(16 + 3 * i + j)) for j in range(3))
    words["dir.cls"] = "d%d" % (i + 1)
    words["dir.t"] = esc(t)
    words["dir.d"] = esc(desc)
    words["page.title"] = esc("%s — Galereya Best" % t)
    words["page.desc"] = esc(desc)

    cards = []
    for name, href in d["brands"]:
        if href == "3d":
            href = path(lang, "3d")
            cls = "brand-card brand-in"
        elif href == "trimline":            # каталог TRIMLINE внутри этого сайта
            href = path(lang, "trimline")
            cls = "brand-card brand-in"
        elif href:
            cls = "brand-card brand-ext"
        if href:
            cards.append('<a class="%s" href="%s"><span>%s</span><i aria-hidden="true">→</i></a>'
                         % (cls, href, esc(name)))
        else:
            cards.append('<div class="brand-card"><span>%s</span><i aria-hidden="true">·</i></div>' % esc(name))
    words["dir.brand_list"] = "\n        ".join(cards)
    words["dir.tags"] = esc(" · ".join(n for n, _ in d["brands"]))

    words["dir.others_list"] = dir_tiles(lang, skip=i)

    # Плинтусы и молдинги: ссылка на 3D-каталог TRIMLINE
    # Плинтусы и молдинги: лента товаров TRIMLINE и ссылка на 3D-каталог
    words["dir.extra"] = ""
    if d["slug"] == "plintusy":
        words["dir.extra"] = (
            '<section class="section section-soft"><div class="wrap">'
            '<div class="row-head"><div><p class="eyebrow">TRIMLINE · 3D</p><h2>%s</h2><p class="sub">%s</p></div>'
            '<a class="btn btn-dark" href="%s">%s</a></div>'
            '<div class="prow">%s</div></div></section>'
            % (esc(words["dir.3d_t"]), esc(words["dir.3d_d"]), path(lang, "3d"),
               esc(words["dir.3d_btn"]), products_row(lang)))
    return {"cat.%s_t" % k, "cat.%s_d" % k, "dir.3d_t", "dir.3d_d", "dir.3d_btn"}


def render(page, lang, words, templates):
    slug, doc = page["slug"], page["doc"]
    words = dict(words)
    # какой пункт полосы направлений подсветить: каталог TRIMLINE — это плинтусы
    active = "plintusy" if slug == "trimline" else slug
    words.update({
        "lang": lang,
        "canonical": url(lang, slug),
        "alternates": alternates(slug),
        "lang_switch": lang_switch(lang, slug, words["nav.lang_aria"]),
        # общие куски всех страниц: шапка с полосой направлений и подвал
        "site_header": templates["partials/header.html"],
        "site_footer": templates["partials/footer.html"],
        "dir_strip": dir_strip(lang, active),
        "foot_dirs": dir_links(lang, active),
        "dir_tiles": dir_tiles(lang),
        "products": products_row(lang),
        "showcase": showcase(lang),
        "bk_items": bk_items(),
    })

    used = set()
    if "dir" in page:
        used |= direction_words(page["dir"], lang, words)
    if page["template"] == "showroom.html":
        words["page.title"] = html.escape("%s — Galereya Best" % words["dir.3d_t"], quote=True)
        words["page.desc"] = html.escape(words["show.sub"], quote=True)
    if page["template"] == "brand.html":
        words["page.title"] = html.escape("TRIMLINE — %s — Galereya Best" % words["bk.title"], quote=True)
        words["page.desc"] = html.escape(words["bk.lead"], quote=True)
        used |= {"bk.title"}
    if doc:
        # Текст документа сам содержит реквизиты компании — прогоняем и его.
        body = (HERE / "legal" / ("%s.%s.html" % (doc, lang))).read_text(encoding="utf-8")
        words["legal_body"], used = expand(body, words, lang, "legal/%s" % doc)
        for field in ("title", "desc", "h1"):
            words["page." + field] = words["%s.%s" % (doc, field)]

    page_html, used_tpl = expand(templates[page["template"]], words, lang,
                                 "src/" + page["template"])

    # Браузер ищет кодировку в первом килобайте страницы. Если её там нет, кириллица
    # и узбекские буквы превращаются в мусор. Так уже ломалось: ключ, случайно
    # оставленный в комментарии шаблона, раздул его и утащил <head> внутрь.
    if b'<meta charset="utf-8">' not in page_html.encode("utf-8")[:1024]:
        raise ValueError("%s (%s): <meta charset> не попал в первый килобайт страницы —"
                         " проверьте комментарии и порядок тегов в шаблоне"
                         % (page["template"], lang))
    return page_html, used | used_tpl


def sitemap():
    """Только страницы, которые нужны в поиске: юридические помечены noindex."""
    slugs = [p["slug"] for p in PAGES if not p["doc"]]
    urls = "".join(
        "  <url><loc>%s</loc>%s</url>\n" % (
            url(code, slug),
            "".join('<xhtml:link rel="alternate" hreflang="%s" href="%s"/>'
                    % (alt, url(alt, slug)) for alt in LANGS))
        for slug in slugs for code in LANGS)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n'
            '        xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
            '%s</urlset>\n' % urls)


def main():
    ap = argparse.ArgumentParser(description="Собрать сайт galery.uz на трёх языках")
    ap.add_argument("--out", default=str(HERE / "dist"), help="куда положить результат")
    args = ap.parse_args()

    templates = {t: (HERE / "src" / t).read_text(encoding="utf-8")
                 for t in [p["template"] for p in PAGES]
                 + ["partials/header.html", "partials/footer.html"]}
    company = {k: v for k, v in json.loads(
        (HERE / "company.json").read_text(encoding="utf-8")).items()
        if not k.startswith("_")}

    PHOTOS.update({k: v for k, v in json.loads(
        (HERE / "photos.json").read_text(encoding="utf-8")).items() if not k.startswith("_")})
    missing = [k for k, v in PHOTOS.items() if v.get("file") and
               not (HERE / "img" / "photos" / v["file"]).is_file()]
    if missing:
        raise SystemExit("photos.json: нет файлов в img/photos/ для фото %s" % ", ".join(missing))

    out = pathlib.Path(args.out)
    if out.exists():
        shutil.rmtree(out)          # чтобы не остались файлы от прошлой сборки
    out.mkdir(parents=True)

    for lang in LANGS:
        words = json.loads((HERE / "i18n" / ("%s.json" % lang)).read_text(encoding="utf-8"))
        words.update(company)
        used = set()
        for page in PAGES:
            page_dir = out / lang / page["slug"] if page["slug"] else out / lang
            page_dir.mkdir(parents=True, exist_ok=True)
            page_html, used_here = render(page, lang, words, templates)
            # версия файлов в ссылке: браузер не покажет старые стили после правок
            for asset in ("css/home.css", "css/style.css", "js/site.js"):
                if (HERE / asset).exists():
                    ver = hashlib.md5((HERE / asset).read_bytes()).hexdigest()[:8]
                    page_html = page_html.replace('/%s"' % asset, '/%s?v=%s"' % (asset, ver))
            (page_dir / "index.html").write_text(page_html, encoding="utf-8")
            used |= used_here
            print("  %sindex.html" % path(lang, page["slug"]))

        # Ключ, который никуда не подставился, — почти всегда опечатка в шаблоне
        # или забытая правка словаря. Лучше узнать на сборке, чем на сайте.
        extra = set(words) - used - GENERATED
        extra -= {"form." + k[3:] for k in used if k.startswith("js.")}
        extra -= {"%s.%s" % (p["doc"], f) for p in PAGES if p["doc"] for f in
                  ("title", "desc", "h1")}
        extra -= {"nav.lang_aria",   # уходит в подпись переключателя языков
                  "meta.lang_name"}  # запас на будущее: полное название языка
        if extra:
            print("  ! %s.json: ключи не используются: %s"
                  % (lang, ", ".join(sorted(extra))), file=sys.stderr)

    unset = sorted(k for k, v in company.items() if v == UNSET)
    if unset:
        print("\n  ! РЕКВИЗИТЫ НЕ ЗАПОЛНЕНЫ — на юридических страницах будет «%s»:\n"
              "    %s\n    заполнить в company.json"
              % (UNSET, ", ".join(unset)), file=sys.stderr)

    shutil.copytree(HERE / "css", out / "css")
    shutil.copytree(HERE / "js", out / "js")
    if (HERE / "img").is_dir():                     # фото из photos.json
        shutil.copytree(HERE / "img", out / "img")
    # 3D-модели изделий (Trimline) для страницы /<язык>/3d/.
    if (HERE / "models").is_dir():
        shutil.copytree(HERE / "models", out / "models")
    # Старые адреса черновика каталога ведут на русскую версию каталога TRIMLINE
    for old in ("trimline", "shablon/brend-katalog.html"):
        target = out / old / "index.html" if not old.endswith(".html") else out / old
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=/ru/trimline/">'
                          '<link rel="canonical" href="/ru/trimline/"><a href="/ru/trimline/">TRIMLINE</a>\n', encoding="utf-8")

    # Каталоги брендов (/nmc/, /tim/, /rvk/ …) сюда НЕ входят: их собирает
    # galereya-report из снимков базы (web/<бренд>/snapshot.py) и кладёт в
    # /opt/report-web. nginx отдаёт их оттуда, а всё остальное — отсюда.

    (out / "sitemap.xml").write_text(sitemap(), encoding="utf-8")
    (out / "robots.txt").write_text(
        "User-agent: *\nAllow: /\nSitemap: %s/sitemap.xml\n" % SITE, encoding="utf-8")
    print("собрано в %s" % out)


if __name__ == "__main__":
    main()
