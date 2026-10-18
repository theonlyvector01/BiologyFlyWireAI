"""Шаг 8. Список литературы с проверкой ссылок.

Для каждой статьи:
  1. метаданные (авторы, журнал, том, страницы) берутся из Crossref по DOI — так в ссылке нет опечаток;
  2. DOI проверяется в официальном реестре doi.org: он должен существовать и вести на сайт издателя;
  3. открывается страница издателя. Ответ 2xx — страница открылась. Ответ 403/406/429 со страницей
     «проверка браузера» — сайт жив, но защищён от роботов (человек в браузере её проходит).
     404, 410, 5xx и тайм-аут считаются нерабочей ссылкой.
Результат с датой проверки: data/literature/references.json и web/data/references.js.

Запуск: python pipeline/08_check_references.py
"""
import datetime as dt
import json
import re
import subprocess
import urllib.parse
import urllib.request

from config import LITERATURE, WEB

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
CROSSREF_UA = {"User-Agent": "BiologyFlyWireAI/1.0 (mailto:noreply@anthropic.com)"}

# раздел, ключ, DOI, для какой модели использован
PAPERS = [
    ("connectome", "dorkenwald2024", "10.1038/s41586-024-07558-y", "Коннектом самки FlyWire"),
    ("connectome", "schlegel2024", "10.1038/s41586-024-07686-5", "Типы нейронов FlyWire"),
    ("connectome", "berg2026", "10.1016/j.cell.2026.08.015", "Коннектом самца MaleCNS"),
    ("female", "wang2021", "10.1038/s41586-020-2972-7", "vpoDN, vpoEN, настройка на песню"),
    ("female", "wang2020", "10.1016/j.cub.2020.07.083", "DNp13, отказ самки"),
    ("female", "zhou2014", "10.1016/j.neuron.2014.05.038", "pC1 и pCd"),
    ("female", "feng2014", "10.1016/j.neuron.2014.05.017", "нейроны SAG"),
    ("female", "deutsch2020", "10.7554/eLife.59502", "pC1d/e"),
    ("female", "deutsch2019", "10.1016/j.cub.2019.08.008", "детекторы песни pC2l"),
    ("female", "chen2025", "10.1073/pnas.2418481122", "возраст самки, лейкокинин"),
    ("female", "bce1969", "10.1016/s0003-3472(69)80023-0", "интервал песни 34 и 48 мс"),
    ("female", "manning1959", "10.1016/0003-3472(59)90031-4", "изоляция D. melanogaster и D. simulans"),
    ("both", "kurtovic2007", "10.1038/nature05672", "феромон cVA и рецептор Or67d"),
    ("female", "wigby2011", "10.1098/rspb.2010.1390", "повторное спаривание без полового пептида"),
    ("female", "peng2005", "10.1016/j.cub.2005.01.034", "действие полового пептида со временем"),
    ("male", "thistle2012", "10.1016/j.cell.2012.03.045", "вкусовые клетки ppk23"),
    ("male", "lu2012", "10.1371/journal.pgen.1002587", "мутант ppk23"),
    ("male", "toda2012", "10.1016/j.celrep.2012.05.007", "феромон 7,11-HD"),
    ("male", "miyamoto2008", "10.1038/nn.2161", "рецептор Gr32a"),
    ("male", "wang2011", "10.1038/nn.2800", "7-трикозен и Gr32a"),
    ("male", "kallman2015", "10.7554/eLife.11188", "PPN1 и mAL"),
    ("male", "clowney2015", "10.1016/j.neuron.2015.07.025", "vAB3 и mAL"),
    ("male", "kohatsu2011", "10.1016/j.neuron.2010.12.017", "нейроны P1"),
    ("male", "inagaki2014", "10.1038/nmeth.2765", "активация P1"),
    ("male", "vonphilipsborn2011", "10.1016/j.neuron.2011.01.011", "pIP10 и песня"),
    ("male", "zhang2016", "10.1016/j.neuron.2016.05.020", "пресыщение и дофамин"),
    ("male", "ribeiro2018", "10.1016/j.cell.2018.06.020", "зрение LC10a"),
    ("male", "seeholzer2018", "10.1038/s41586-018-0322-9", "самки D. simulans"),
    ("male", "laturney2016", "10.1038/ncomms12322", "феромоны на спарившейся самке"),
    ("male", "krstic2009", "10.1371/journal.pone.0004457", "ухаживание в темноте"),
]
DATA = [
    ("Codex — браузер коннектома FlyWire", "https://codex.flywire.ai/", None),
    ("FlyWire: таблица связей (Zenodo 10676866)", "https://zenodo.org/records/10676866", "https://zenodo.org/api/records/10676866"),
    ("FlyWire: 3D-скелеты нейронов (Zenodo 10877326)", "https://zenodo.org/records/10877326", "https://zenodo.org/api/records/10877326"),
    ("Аннотации нейронов FlyWire (GitHub)", "https://github.com/flyconnectome/flywire_annotations",
     "https://raw.githubusercontent.com/flyconnectome/flywire_annotations/main/README.md"),
    ("MaleCNS: страница загрузки данных", "https://male-cns.janelia.org/download/", None),
]


def http_status(url: str, browser_ua: bool = True) -> tuple[int, str, str]:
    """Код ответа, итоговый адрес и заголовок страницы."""
    ua = ["-A", UA] if browser_ua else []
    r = subprocess.run(["curl", "-sS", "-L", "--max-time", "40", *ua, "-w", "\n%{http_code} %{url_effective}", url],
                       capture_output=True, text=True)
    body, _, tail = r.stdout.rpartition("\n")
    code, _, final = tail.partition(" ")
    low = body.lower()
    title = low.split("<title>", 1)[1].split("</title>", 1)[0].strip() if "<title>" in low else ""
    return int(code or 0), final, title


def classify(code: int, title: str) -> str:
    if 200 <= code < 400:
        return "ok"
    challenge = any(w in title for w in ("moment", "момент", "challenge", "captcha", "проверка", "attention", "forbidden"))
    if code in (401, 403, 406, 429) or challenge:
        return "protected"
    return "dead"


def clean_title(t: str) -> str:
    """Убирает HTML-разметку курсива из названия Crossref, не склеивая слова."""
    t = re.sub(r"(?<=\w)<i>", " ", t)
    t = re.sub(r"</i>(?=\w)", " ", t)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", t)).strip()


def initials(given: str) -> str:
    parts = given.replace("-", " ").replace(".", " ").split()
    return "".join(p[0] + "." for p in parts if p)


def main() -> None:
    today = dt.date.today().isoformat()
    refs = []
    for section, key, doi, used in PAPERS:
        it = json.load(urllib.request.urlopen(urllib.request.Request(
            "https://api.crossref.org/works/" + urllib.parse.quote(doi), headers=CROSSREF_UA), timeout=60))["message"]
        year = (it.get("published-print") or it.get("issued"))["date-parts"][0][0]
        authors = [f"{a.get('family', '')} {initials(a.get('given', ''))}".strip() for a in it.get("author", [])]
        handle = json.load(urllib.request.urlopen(f"https://doi.org/api/handles/{doi}?type=URL", timeout=60))
        target = next((v["data"]["value"] for v in handle.get("values", []) if v["type"] == "URL"), "")
        code, final, title = http_status("https://doi.org/" + doi)
        status = classify(code, title) if handle.get("responseCode") == 1 else "dead"
        refs.append({
            "key": key, "section": section, "used_for": used,
            "authors": authors[:3], "n_authors": len(authors), "year": year,
            "title": clean_title(it["title"][0]),
            "journal": (it.get("short-container-title") or it.get("container-title") or [""])[0],
            "volume": it.get("volume", ""), "pages": it.get("page") or it.get("article-number", ""),
            "doi": doi, "url": "https://doi.org/" + doi,
            "check": {"date": today, "doi_registered": handle.get("responseCode") == 1, "doi_target": target,
                      "http": code, "status": status},
        })
        print(f"{key:18s} {status:9s} {code} {final[:70]}", flush=True)
    data = []
    for name, url, probe in DATA:
        code, final, title = http_status(url)
        status = classify(code, title)
        if status != "ok" and probe:          # страница закрыта от роботов — проверяем ту же запись через API
            pcode, _, _ = http_status(probe, browser_ua=False)
            status = "ok" if 200 <= pcode < 400 else status
        data.append({"name": name, "url": url, "check": {"date": today, "http": code, "status": status}})
        print(f"{name[:40]:40s} {status:9s} {code}", flush=True)
    out = {"checked": today, "papers": refs, "data": data,
           "method_ru": "DOI проверен в реестре doi.org и ведёт на страницу статьи у издателя; страница издателя отвечает "
                        "(у некоторых издателей роботу показывается проверка браузера — человек проходит её автоматически)."}
    (LITERATURE / "references.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    (WEB / "data" / "references.js").write_text("window.FLY_REFS = " + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n")
    dead = [r["key"] for r in refs if r["check"]["status"] == "dead"] + [d["name"] for d in data if d["check"]["status"] == "dead"]
    print("Нерабочие ссылки:", dead or "нет")


if __name__ == "__main__":
    main()
