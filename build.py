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
# Дизайн «Тёплая классика». Для каждого направления (тот же порядок, что DIRECTIONS):
#   ICONS — линейная иконка вкладки «Пять направлений» (viewBox 0 0 48 48);
#   ART   — рисунок в круге (viewBox 0 0 120 120). Это заглушки: когда появятся фото
#           товаров, круг можно заменить на <img> (класс .circ-img в css/home.css).
ICONS = [
    '<path d="M6 8h9v32H6zM19.5 8h9v32h-9zM33 8h9v32h-9z"/>',
    '<path d="M5 10h38v8H5zM5 22h38v8H5zM5 34h38v6H5M18 10v8M30 22v8M14 34v6"/>',
    '<path d="M8 6v36M15 6v36M22 6v36M29 6v36M36 6v36"/>',
    '<path d="M6 24h36q0 12-18 12T6 24zM24 24v-12h8v4"/>',
    '<path d="M12 42V6h24v36M8 42h32M31 25h.5"/>',
]
ART = [
    '<rect x="14" y="52" width="92" height="16" rx="2" fill="#fff" stroke="#c9bfb2" stroke-width="2"/>'
    '<path d="M106 52l4 4-4 4" fill="none" stroke="#c9bfb2" stroke-width="2"/>',
    '<g stroke="#a8754b" stroke-width="1.5"><rect x="14" y="40" width="92" height="40" fill="#c99a6b"/>'
    '<path d="M14 53h92M14 67h92M44 40v13M78 53v14M36 67v13M90 67v13" fill="none"/></g>',
    '<g fill="#efe9df" stroke="#c9bfb2" stroke-width="1.5"><rect x="22" y="30" width="14" height="60"/>'
    '<rect x="38" y="30" width="14" height="60"/><rect x="54" y="30" width="14" height="60"/>'
    '<rect x="70" y="30" width="14" height="60"/><rect x="86" y="30" width="12" height="60"/></g>',
    '<path d="M24 62h72q0 22-36 22T24 62z" fill="#fff" stroke="#9b9187" stroke-width="2"/>'
    '<path d="M64 62V44h10v6" fill="none" stroke="#9b9187" stroke-width="2.5"/>',
    '<rect x="40" y="22" width="40" height="76" rx="1" fill="#efe9df" stroke="#c9bfb2" stroke-width="2"/>'
    '<circle cx="73" cy="62" r="2" fill="#8a7d70"/>',
]
# Тон стены на заглушке «фото в интерьере» — свой у каждого направления.
WALLS = ["#8f8070", "#94826c", "#8c8676", "#8a8580", "#8e7f72"]


def scene(i=0):
    """Заглушка фотографии: интерьер с молдингами на стене, диваном и деревом.
    Когда будет настоящее фото — заменить вызов на <img> (класс .ph остаётся)."""
    w = WALLS[i % len(WALLS)]
    return (
        '<svg class="ph-svg" viewBox="0 0 1440 600" preserveAspectRatio="xMidYMid slice" aria-hidden="true">'
        '<rect width="1440" height="600" fill="%s"/>'
        '<rect width="1440" height="600" fill="#fff" opacity=".08"/>'
        '<g fill="none" stroke="#d8cfc3" stroke-width="12" opacity=".9">'
        '<rect x="210" y="50" width="460" height="350"/><rect x="770" y="50" width="460" height="350"/></g>'
        '<rect y="470" width="1440" height="130" fill="#d9d1c6"/><rect y="470" width="1440" height="10" fill="#c8bdb0"/>'
        '<g fill="#cfc3b3"><rect x="350" y="300" width="600" height="110" rx="28"/>'
        '<rect x="326" y="345" width="650" height="140" rx="26"/></g>'
        '<rect x="1090" y="215" width="12" height="270" fill="#7a6a5a"/>'
        '<circle cx="1096" cy="180" r="66" fill="#6f8a68"/>'
        '</svg>' % w)


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
             "dir.others_list", "dir.extra", "dir.scene",
             "site_header", "site_footer", "dir_strip", "dir_circles", "dir_tabs",
             "dir_panels", "hero_scene"}
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


def dir_strip(lang, active):
    """Полоса направлений под шапкой (на всех страницах) + 3D-шоурум."""
    items = [(path(lang, d["slug"]), "{{cat.%s_t}}" % d["key"], d["slug"] == active)
             for d in DIRECTIONS]
    items.append((path(lang, "3d"), "{{bk.showroom}}", active == "3d"))
    return "".join('<a href="%s"%s>%s</a>' % (
        href, ' class="on" aria-current="page"' if on else "", label)
        for href, label, on in items)


def dir_circles(lang, skip=None):
    """Круги с товарами: на главной — пять под героем, на странице направления —
    «другие направления» (без текущего)."""
    out = []
    for i, d in enumerate(DIRECTIONS):
        if i == skip:
            continue
        out.append('<a class="circ d%d" href="%s"><span class="circ-img">'
                   '<svg viewBox="0 0 120 120" aria-hidden="true">%s</svg></span>'
                   '<span class="circ-t">{{cat.%s_t}}</span></a>'
                   % (i + 1, path(lang, d["slug"]), ART[i], d["key"]))
    return "\n      ".join(out)


def line_icon(i):
    return ('<svg class="ticon" viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="2" '
            'stroke-linejoin="round" aria-hidden="true">%s</svg>' % ICONS[i])


def dir_tabs(lang):
    """Главная: вкладки «Пять направлений» и панели под ними (без JS видны все панели)."""
    tabs, panels = [], []
    for i, d in enumerate(DIRECTIONS):
        n = i + 1
        tabs.append('<a class="dtab%s" href="#dp-%d" role="tab" aria-controls="dp-%d" aria-selected="%s">'
                    '%s<span>{{cat.%s_t}}</span></a>'
                    % (" on" if i == 0 else "", n, n, "true" if i == 0 else "false",
                       line_icon(i), d["key"]))
        panels.append('<div class="dpanel d%d" id="dp-%d" role="tabpanel">'
                      '<div class="ph">%s</div><div class="wrap"><div class="dcard">'
                      '<h3>{{cat.%s_t}}</h3><p>{{cat.%s_d}}</p>'
                      '<p class="dbrands">{{cat.brands_lbl}}: %s</p>'
                      '<a class="btn btn-white" href="%s">{{hero.btn_catalog}}</a></div></div></div>'
                      % (n, n, scene(i), d["key"], d["key"], brand_names(i),
                         path(lang, d["slug"])))
    return "\n      ".join(tabs), "\n    ".join(panels)


def direction_words(i, lang, words):
    """Значения для страницы направления (шаблон direction.html). Возвращает
    ключи словаря, которые ушли на страницу, — для проверки неиспользуемых."""
    d = DIRECTIONS[i]
    k = d["key"]
    esc = lambda t: html.escape(t, quote=True)
    t, desc = words["cat.%s_t" % k], words["cat.%s_d" % k]
    words["dir.n"] = "0%d" % (i + 1)
    words["dir.scene"] = scene(i)
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
            cards.append('<div class="brand-card"><span>%s</span></div>' % esc(name))
    words["dir.brand_list"] = "\n        ".join(cards)
    words["dir.tags"] = esc(" · ".join(n for n, _ in d["brands"]))

    words["dir.others_list"] = dir_circles(lang, skip=i)

    # Плинтусы и молдинги: ссылка на 3D-каталог TRIMLINE
    words["dir.extra"] = ""
    if d["slug"] == "plintusy":
        words["dir.extra"] = (
            '<section class="promo3d"><div class="wrap promo3d-in">'
            '<div><p class="eyebrow">TRIMLINE · 3D</p><h2>%s</h2><p>%s</p></div>'
            '<a class="btn btn-green btn-lg" href="%s">%s</a></div></section>'
            % (esc(words["dir.3d_t"]), esc(words["dir.3d_d"]), path(lang, "3d"),
               esc(words["dir.3d_btn"])))
    return {"cat.%s_t" % k, "cat.%s_d" % k, "dir.3d_t", "dir.3d_d", "dir.3d_btn"}


def render(page, lang, words, templates):
    slug, doc = page["slug"], page["doc"]
    words = dict(words)
    # какой пункт полосы направлений подсветить: каталог TRIMLINE — это плинтусы
    active = "plintusy" if slug == "trimline" else slug
    tabs, panels = dir_tabs(lang)
    words.update({
        "lang": lang,
        "canonical": url(lang, slug),
        "alternates": alternates(slug),
        "lang_switch": lang_switch(lang, slug, words["nav.lang_aria"]),
        # общие куски всех страниц: шапка с полосой направлений и подвал
        "site_header": templates["partials/header.html"],
        "site_footer": templates["partials/footer.html"],
        "dir_strip": dir_strip(lang, active),
        "dir_circles": dir_circles(lang),
        "dir_tabs": tabs,
        "dir_panels": panels,
        "hero_scene": scene(0),
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
