"""Шаг 1. Скачивание открытых данных FlyWire (коннектом мозга самки дрозофилы, релиз 783).

Файлы:
  * neuron_annotations.tsv          — типы нейронов, медиаторы, координаты (~32 МБ)
  * proofread_connections_783.feather — все проверенные связи между нейронами (~850 МБ)
  * sk_lod1_783_healed_ds2.parquet  — 3D-скелеты нейронов для визуализации (~5.4 ГБ, опционально)

Для самца (--male) — коннектом MaleCNS v1.0 (Berg et al., Cell 2026, лицензия CC-BY):
  * аннотации, медиаторы и таблица связей (~570 МБ). Скелеты самца скачивает 05b_skeletons_male.py.

Запуск:  python pipeline/01_download.py [--skeletons] [--male]
"""
import argparse
import shutil
import urllib.request

from config import RAW, RAW_MALE, ANNOTATIONS_URL, ZENODO_CONNECTIONS, ZENODO_SKELETONS, MALECNS_BASE, MALECNS_FILES


def fetch(url: str, name: str, folder=RAW) -> None:
    dst = folder / name
    if dst.exists() and dst.stat().st_size > 0:
        print(f"[есть] {dst}")
        return
    print(f"[качаю] {url}\n   -> {dst}")
    tmp = dst.with_suffix(dst.suffix + ".part")
    with urllib.request.urlopen(url) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f, length=1 << 20)
    tmp.rename(dst)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--skeletons", action="store_true", help="скачать также 3D-скелеты (5.4 ГБ)")
    p.add_argument("--male", action="store_true", help="скачать коннектом самца MaleCNS (~570 МБ)")
    args = p.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    fetch(ANNOTATIONS_URL, "neuron_annotations.tsv")
    fetch(ZENODO_CONNECTIONS, "proofread_connections_783.feather")
    if args.skeletons:
        fetch(ZENODO_SKELETONS, "sk_lod1_783_healed_ds2.parquet")
    if args.male:
        RAW_MALE.mkdir(parents=True, exist_ok=True)
        for f in MALECNS_FILES:
            fetch(f"{MALECNS_BASE}/{f}", f.rsplit("/", 1)[1], RAW_MALE)
    print("Готово.")


if __name__ == "__main__":
    main()
