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
# Иконки направлений в стиле чертежа (тот же порядок, что DIRECTIONS).
ICONS = ['<path d="M10 80 L10 20 Q10 10 20 10 L50 10 L50 30 Q50 40 60 40 L90 40 Q100 60 120 64 L140 66 L140 80 Z"/>', '<path d="M10 70 L140 70 M10 50 L140 50 M10 30 L140 30 M50 30 L50 50 M100 50 L100 70 M80 10 L80 30 M10 10 L140 10"/>', '<path d="M14 10 L14 80 M38 10 L38 80 M62 10 L62 80 M86 10 L86 80 M110 10 L110 80 M134 10 L134 80"/>', '<path d="M30 40 L120 40 Q120 70 75 74 Q30 70 30 40 Z M75 40 L75 14 L95 14"/>', '<path d="M40 80 L40 10 L110 10 L110 80 M52 22 L98 22 L98 70 L52 70 Z M90 46 L94 46"/>']

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
             "dir.others_list", "dir.extra", "dir.icon"}
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
    for _ in range(3):
        new = PLACEHOLDER.sub(sub, text)
        if new == text:
            break
        text = new
    return text, used


def direction_words(i, lang, words):
    """Значения для страницы направления (шаблон direction.html). Возвращает
    ключи словаря, которые ушли на страницу, — для проверки неиспользуемых."""
    d = DIRECTIONS[i]
    k = d["key"]
    esc = lambda t: html.escape(t, quote=True)
    t, desc = words["cat.%s_t" % k], words["cat.%s_d" % k]
    words["dir.n"] = "0%d" % (i + 1)
    words["dir.icon"] = ('<svg class="dicon" viewBox="0 0 150 90" fill="none" stroke="currentColor" '
                         'stroke-width="3" stroke-linejoin="round" stroke-linecap="round" aria-hidden="true">'
                         '%s</svg>' % ICONS[i])
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

    others = []
    for j, o in enumerate(DIRECTIONS):
        if j == i:
            continue
        others.append('<a class="dtile d%d" href="%s"><span class="dt-n">0%d</span>'
                      '<span class="dt-t">%s</span><span class="dt-go" aria-hidden="true">→</span></a>'
                      % (j + 1, path(lang, o["slug"]), j + 1, esc(words["cat.%s_t" % o["key"]])))
    words["dir.others_list"] = "\n      ".join(others)

    # Плинтусы и молдинги: ссылка на 3D-каталог TRIMLINE
    words["dir.extra"] = ""
    if d["slug"] == "plintusy":
        words["dir.extra"] = (
            '<section class="promo3d"><div class="wrap promo3d-in">'
            '<div><p class="eyebrow">TRIMLINE · 3D</p><h2>%s</h2><p>%s</p></div>'
            '<a class="btn btn-ink btn-lg" href="%s">%s</a></div></section>'
            % (esc(words["dir.3d_t"]), esc(words["dir.3d_d"]), path(lang, "3d"),
               esc(words["dir.3d_btn"])))
    used = {"cat.%s_t" % k, "cat.%s_d" % k, "dir.3d_t", "dir.3d_d", "dir.3d_btn"}
    used |= {"cat.%s_t" % o["key"] for o in DIRECTIONS}
    return used


def render(page, lang, words, templates):
    slug, doc = page["slug"], page["doc"]
    words = dict(words)
    words.update({
        "lang": lang,
        "canonical": url(lang, slug),
        "alternates": alternates(slug),
        "lang_switch": lang_switch(lang, slug, words["nav.lang_aria"]),
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

    templates = {p["template"]: (HERE / "src" / p["template"]).read_text(encoding="utf-8")
                 for p in PAGES}
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
