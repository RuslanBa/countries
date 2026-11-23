"""
Дополнительные данные для карты (только стандартная библиотека Python).

1) Население стран (World Bank SP.POP.TOTL, значения 2021+)  -> extra.csv
   Нужно, чтобы убрать из рейтинга микрогосударства (< 250 тыс. жителей).
2) Визовые режимы «паспорт -> страна» (Passport Index dataset, MIT,
   данные passportindex.org)                                    -> visa_tidy_iso3.csv
   Нужно для фактора «Лёгкость легализации».

Запуск:  python3 extra_data.py
Потом:   python3 build_data.py
"""
import csv
import json
import time
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (country-map prototype)", "Accept": "*/*"}


def get(url, tries=3):
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            last = e
            print(f"  повтор {i + 1}/{tries}: {e}")
            time.sleep(2 * (i + 1))
    raise last


# ---------- 1. население ----------
def population():
    print("World Bank: население…")
    best = {}
    page = 1
    while True:
        url = ("https://api.worldbank.org/v2/country/all/indicator/SP.POP.TOTL"
               f"?format=json&date=2021:2026&per_page=2000&page={page}")
        meta, rows = json.loads(get(url))
        for r in rows or []:
            iso3, val = r.get("countryiso3code"), r.get("value")
            if not iso3 or val is None:
                continue
            yr = int(r["date"])
            if iso3 not in best or yr > best[iso3][1]:
                best[iso3] = (val, yr)
        if page >= meta.get("pages", 1):
            break
        page += 1
    with open("extra.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["iso3", "population", "population_year"])
        for iso3, (v, y) in sorted(best.items()):
            w.writerow([iso3, int(v), y])
    print(f"  ok: {len(best)} стран -> extra.csv")


# ---------- 2. визы ----------
VISA_URLS = [
    # обновляется чаще (последнее обновление — 2026)
    "https://raw.githubusercontent.com/imorte/passport-index-data/main/passport-index-tidy-iso3.csv",
    "https://raw.githubusercontent.com/imorte/passport-index-data/master/passport-index-tidy-iso3.csv",
    # исходный датасет (до 2025)
    "https://raw.githubusercontent.com/ilyankou/passport-index-dataset/master/passport-index-tidy-iso3.csv",
]


def visas():
    print("Passport Index: визовые режимы…")
    for url in VISA_URLS:
        try:
            data = get(url, tries=2)
        except Exception as e:  # noqa: BLE001
            print(f"  не получилось: {url} ({e})")
            continue
        text = data.decode("utf-8")
        if "Passport" not in text.splitlines()[0]:
            print(f"  неожиданный формат: {url}")
            continue
        with open("visa_tidy_iso3.csv", "w", encoding="utf-8") as f:
            f.write(text)
        with open("visa_source.txt", "w", encoding="utf-8") as f:
            f.write(url + "\n" + time.strftime("%Y-%m-%d") + "\n")
        print(f"  ok: {len(text.splitlines()) - 1} пар -> visa_tidy_iso3.csv")
        return
    print("  ОШИБКА: визовые данные не скачались")


if __name__ == "__main__":
    population()
    visas()
