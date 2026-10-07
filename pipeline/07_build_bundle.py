"""Шаг 7. Сборка всего приложения в ОДИН html-файл (удобно переносить на флешке и открывать офлайн).

Все скрипты и данные из web/ встраиваются внутрь страницы.
Результат: dist/Коннектом_выбора.html
Флаг --fragment дополнительно пишет версию без <html>/<head>/<body> (для публикации как Artifact).
"""
import argparse
import re

from config import ROOT, WEB


def inline(html: str) -> str:
    def repl(m):
        src = m.group(1)
        path = WEB / src
        if not path.exists():
            print("  пропущен (нет файла):", src)
            return ""
        code = path.read_text(encoding="utf-8").replace("</script", "<\\/script")
        return f"<script>/* {src} */\n{code}\n</script>"
    return re.sub(r'<script src="([^"]+)"></script>', repl, html)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fragment", help="путь для версии без обёртки html/head/body")
    args = ap.parse_args()
    html = inline((WEB / "index.html").read_text(encoding="utf-8"))
    out = ROOT / "dist" / "Коннектом_выбора.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"{out}  ({out.stat().st_size / 1e6:.2f} МБ)")
    if args.fragment:
        frag = re.sub(r"<!doctype html>\s*<html[^>]*>\s*<head>\s*", "", html, flags=re.I)
        frag = re.sub(r'<meta charset="utf-8">\s*<meta name="viewport"[^>]*>\s*', "", frag)
        frag = frag.replace("</head>\n<body>\n", "").replace("</body>\n</html>\n", "")
        with open(args.fragment, "w", encoding="utf-8") as f:
            f.write(frag)
        print("fragment:", args.fragment)


if __name__ == "__main__":
    main()
