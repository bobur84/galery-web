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
PAGES = [
    {"slug": "",        "template": "index.html", "doc": None},
    {"slug": "privacy", "template": "legal.html", "doc": "privacy"},
    {"slug": "terms",   "template": "legal.html", "doc": "terms"},
]

HERE = pathlib.Path(__file__).resolve().parent
PLACEHOLDER = re.compile(r"\{\{(!?)([a-z][\w.]*)\}\}")
# Ключи, которые вычисляет сама сборка. Это готовая разметка — не экранируются.
GENERATED = {"lang", "canonical", "alternates", "lang_switch", "legal_body",
             "page.title", "page.desc", "page.h1"}
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
    urls = "".join(
        "  <url><loc>%s</loc>%s</url>\n" % (
            url(code, ""),
            "".join('<xhtml:link rel="alternate" hreflang="%s" href="%s"/>'
                    % (alt, url(alt, "")) for alt in LANGS))
        for code in LANGS)
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

    # Каталоги брендов (/nmc/, /tim/, /rvk/ …) сюда НЕ входят: их собирает
    # galereya-report из снимков базы (web/<бренд>/snapshot.py) и кладёт в
    # /opt/report-web. nginx отдаёт их оттуда, а всё остальное — отсюда.

    (out / "sitemap.xml").write_text(sitemap(), encoding="utf-8")
    (out / "robots.txt").write_text(
        "User-agent: *\nAllow: /\nSitemap: %s/sitemap.xml\n" % SITE, encoding="utf-8")
    print("собрано в %s" % out)


if __name__ == "__main__":
    main()
