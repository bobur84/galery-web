"""Локальный просмотр сайта вместе с каталогами брендов — как nginx на сервере.

Сайт берётся из dist/ (сначала `python3 build.py`), а /nmc/ /tim/ /rvk/ /marbet/
/primedecor/ /wassermann/ — из репозитория galereya-report (web/<бренд>/).
Чего нет в dist/, ищется в каталогах; иначе 404.

python3 tools/serve.py [порт] [путь к galereya-report/web]

По умолчанию порт 8010, каталоги — ../galereya-report/web рядом с этим репо
(или переменная GALEREYA_WEB). Без каталогов сайт тоже работает, просто
ссылки на бренды дадут 404.
"""
import http.server
import os
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
SITE = REPO / "dist"


def catalogs_dir(arg):
    p = arg or os.environ.get("GALEREYA_WEB") or REPO.parent / "galereya-report" / "web"
    return pathlib.Path(p).resolve()


class Handler(http.server.SimpleHTTPRequestHandler):
    roots = [str(SITE)]

    def translate_path(self, path):
        for root in self.roots:
            self.directory = root
            p = super().translate_path(path)
            if os.path.exists(p):
                return p
        self.directory = self.roots[0]
        return super().translate_path(path)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")  # правки видны сразу после build.py
        super().end_headers()


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8010
    cat = catalogs_dir(sys.argv[2] if len(sys.argv) > 2 else None)
    if not SITE.is_dir():
        sys.exit("нет dist/ — сначала: python3 build.py")
    if cat.is_dir():
        Handler.roots = [str(SITE), str(cat)]
        print(f"каталоги брендов: {cat}")
    else:
        print(f"каталоги не найдены ({cat}) — /nmc/, /tim/ … дадут 404")
    print(f"http://127.0.0.1:{port}/ru/")
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), lambda *a: Handler(*a, directory=str(SITE)))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
