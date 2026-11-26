"""
Собирает данные для карты: data/countries.json (+ data/visa.json).

Входные файлы (в текущей папке):
  countries.csv        — результат countries_data.py (Всемирный банк)       обязательно
  pisa_2025.csv        — PISA 2025 (OECD)                                    обязательно
  iso_codes.csv        — коды стран ISO 3166 (лежит рядом)                    обязательно
  visa_tidy_iso3.csv   — визовые режимы (extra_data.py)                      желательно
  manpower_neo.csv     — ManpowerGroup Net Employment Outlook (вручную)      по желанию

Запуск:  python3 build_data.py
"""
import csv
import json
import os
import time

MIN_YEAR = 2021
MANPOWER_MIN_COUNTRIES = 35       # опрос Manpower используем, только если внесены почти все ~42 страны

# Показатель: (направление: +1 больше = лучше, -1 меньше = лучше), источник
IND = {
    "homicides_100k": (-1, "wb"), "political_stability_0_100": (1, "wgi"),
    "price_level_vs_usa": (-1, "wb"),
    "pisa": (1, "pisa"), "tertiary_enrollment": (1, "wb"),
    "life_expectancy": (1, "wb"), "uhc_index": (1, "who"), "infant_mortality": (-1, "wb"),
    "gdp_pc_ppp": (1, "wb"), "gdp_growth": (1, "wb"), "inflation": (-1, "wb"),
    "unemployment": (-1, "ilo"), "vulnerable_employment": (-1, "ilo"), "manpower_neo": (1, "manpower"),
    "rule_of_law_0_100": (1, "wgi"), "control_corruption_0_100": (1, "wgi"),
}
# Фактор = взвешенное среднее процентилей его показателей; нет показателя = 0.
FACTORS = {
    "safety":    [("homicides_100k", .5), ("political_stability_0_100", .5)],
    "cost":      [("price_level_vs_usa", 1.0)],
    "education": [("pisa", .7), ("tertiary_enrollment", .3)],
    "health":    [("life_expectancy", .4), ("uhc_index", .3), ("infant_mortality", .3)],
    "economy":   [("gdp_pc_ppp", .5), ("gdp_growth", .2), ("inflation", .3)],
    "labor":     [("unemployment", .55), ("vulnerable_employment", .35), ("manpower_neo", .10)],
    "laws":      [("rule_of_law_0_100", .5), ("control_corruption_0_100", .5)],
}
# Показатели, которых нет у многих стран не из-за слабости, а потому что опрос там не проводят
OPTIONAL = set()  # было {"manpower_neo"}; решили: нет опроса = 0, как у всех показателей
# Ручные значения из национальных первоисточников (нет во Всемирном банке)
MANUAL = {
    ("ARG", "inflation"): (31.5, 2025, "indec"),  # INDEC, дек 2025 к дек 2024
}
# Не показываем отдельно: Нормандские острова — часть Великобритании (у ВБ это сумма Джерси и Гернси)
SKIP = {"CHI"}
# Спорные территории — на карте серые, в рейтинг не берём
DISPUTED = {"XKX", "ESH"}
# Страны, которых нет во Всемирном банке, но есть в других источниках
EXTRA_COUNTRIES = {"TWN": "Taiwan"}


def read_csv(name):
    with open(name, encoding="utf-8") as f:
        return list(csv.DictReader(f))


iso = read_csv("iso_codes.csv")
a3_to_a2 = {r["alpha3"]: r["alpha2"] for r in iso if r["alpha2"]}
num_to_a3 = {r["numeric"]: r["alpha3"] for r in iso if r["numeric"]}

rows = read_csv("countries.csv")
pisa = {r["iso3"]: r for r in read_csv("pisa_2025.csv")}

def excluded(iso3):
    return iso3 in SKIP or iso3 in DISPUTED


countries = {}
dropped = []
for r in rows:
    if excluded(r["iso3"]):
        dropped.append(r["iso3"])
        continue
    c = {"iso3": r["iso3"], "iso2": a3_to_a2.get(r["iso3"]), "name": r["name"], "v": {}, "src": {}}
    for k in IND:
        if k in ("pisa", "manpower_neo"):
            continue
        val, yr = r.get(k), r.get(k + "_year")
        if val and yr and int(yr) >= MIN_YEAR:
            c["v"][k] = [round(float(val), 2), int(yr)]
    p = pisa.get(r["iso3"])
    if p and p["pisa_math"] and "только часть" not in p["note"]:
        vals = [float(p[x]) for x in ("pisa_math", "pisa_reading", "pisa_science") if p[x]]
        c["v"]["pisa"] = [round(sum(vals) / len(vals)), 2025]
        c["pisa3"] = [int(p["pisa_math"] or 0), int(p["pisa_reading"] or 0), int(p["pisa_science"] or 0)]
    countries[r["iso3"]] = c

for iso3, name in EXTRA_COUNTRIES.items():
    if iso3 not in countries:
        c = {"iso3": iso3, "iso2": a3_to_a2.get(iso3), "name": name, "v": {}, "src": {}}
        p = pisa.get(iso3)
        if p and p["pisa_math"] and "только часть" not in p["note"]:
            vals = [float(p[x]) for x in ("pisa_math", "pisa_reading", "pisa_science") if p[x]]
            c["v"]["pisa"] = [round(sum(vals) / len(vals)), 2025]
            c["pisa3"] = [int(p["pisa_math"] or 0), int(p["pisa_reading"] or 0), int(p["pisa_science"] or 0)]
        countries[iso3] = c

for (iso3, key), (val, yr, src) in MANUAL.items():
    if iso3 in countries:
        countries[iso3]["v"][key] = [val, yr]
        countries[iso3]["src"][key] = src

# ManpowerGroup Employment Outlook Survey (вводится вручную из отчёта)
manpower_q = None
if os.path.exists("manpower_neo.csv"):
    mp = [r for r in read_csv("manpower_neo.csv") if r.get("neo", "").strip()]
    if len(mp) >= MANPOWER_MIN_COUNTRIES:
        for r in mp:
            if r["iso3"] in countries:
                countries[r["iso3"]]["v"]["manpower_neo"] = [float(r["neo"]), int(r["year"])]
                manpower_q = r.get("quarter")
        print("Manpower:", len(mp), "стран, используем")
    else:
        print(f"Manpower: заполнено {len(mp)} стран из ~42 — пока не используем")
if manpower_q is None:
    FACTORS["labor"] = [x for x in FACTORS["labor"] if x[0] != "manpower_neo"]
    del IND["manpower_neo"]


def percentiles(key):
    better = IND[key][0]
    items = [(i, c["v"][key][0]) for i, c in countries.items() if key in c["v"]]
    vals = sorted(v for _, v in items)
    n = len(vals)
    out = {}
    for i, v in items:
        below = sum(1 for x in vals if x < v)
        equal = sum(1 for x in vals if x == v)
        p = (below + 0.5 * equal) / n * 100
        out[i] = p if better > 0 else 100 - p
    return out


P = {k: percentiles(k) for k in IND}
for i, c in countries.items():
    c["f"], c["p"] = {}, {}
    for k in IND:
        if i in P[k]:
            c["p"][k] = round(P[k][i])
    for f, parts in FACTORS.items():
        # нет показателя = 0 (пропуски обычно скрывают слабые результаты);
        # исключение — OPTIONAL: опросы, которые проводятся не во всех странах
        parts = [(k, w) for k, w in parts if k not in OPTIONAL or i in P[k]]
        total = sum(w for _, w in parts)
        have = [(P[k][i], w) for k, w in parts if i in P[k]]
        if have:
            c["f"][f] = round(sum(s * w for s, w in have) / total)
    if not c["src"]:
        del c["src"]

os.makedirs("data", exist_ok=True)
out = {
    "generated": time.strftime("%Y-%m-%d"),
    "min_year": MIN_YEAR,
    "factors": {f: [[k, w] for k, w in p] for f, p in FACTORS.items()},
    "indicators": {k: {"better": IND[k][0], "src": IND[k][1]} for k in IND},
    "manpower_quarter": manpower_q,
    "num_to_iso3": num_to_a3,
    "iso2": a3_to_a2,
    "countries": sorted(countries.values(), key=lambda c: c["iso3"]),
}
with open("data/countries.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
print("стран в рейтинге:", len(countries), "| исключено:", len(dropped))
print("покрытие факторов:", {f: sum(1 for c in countries.values() if f in c["f"]) for f in FACTORS})

# ---------- визы -> data/visa.json ----------
# Коды: 0 въезд запрещён, 1 нужна виза, 2 e-visa, 3 eTA, 4 виза по прилёту,
#       5 без визы < 30 дн, 6 без визы 30–89 дн, 7 без визы 90+ дн, 8 своя страна
if os.path.exists("visa_tidy_iso3.csv"):
    def code(req):
        req = (req or "").strip().lower()
        if req == "-1":
            return 8
        if req.isdigit():
            d = int(req)
            return 7 if d >= 90 else 6 if d >= 30 else 5
        return {"visa free": 7, "visa on arrival": 4, "eta": 3, "e-visa": 2,
                "visa required": 1, "no admission": 0}.get(req)

    pairs = {}
    with open("visa_tidy_iso3.csv", encoding="utf-8") as f:
        rd = csv.reader(f)
        next(rd)
        for row in rd:
            if len(row) >= 3:
                pairs[(row[0], row[1])] = code(row[2])
    # Территории, где действуют иммиграционные правила метрополии, — копируем её режим
    VISA_PARENT = {"PRI": "USA", "GUM": "USA", "VIR": "USA", "MNP": "USA", "IMN": "GBR"}
    for (p_, d_), v_ in list(pairs.items()):
        for terr, par in VISA_PARENT.items():
            if d_ == par:
                pairs[(p_, terr)] = v_
    dests = sorted({d for _, d in pairs})
    passports = sorted({p for p, _ in pairs})
    src_info = open("visa_source.txt", encoding="utf-8").read().split("\n") if os.path.exists("visa_source.txt") else ["", ""]
    visa = {"dest": dests, "date": src_info[1] if len(src_info) > 1 else "", "url": src_info[0],
            "p": {p: "".join(str(pairs.get((p, d))) if pairs.get((p, d)) is not None else "-" for d in dests)
                  for p in passports}}
    with open("data/visa.json", "w", encoding="utf-8") as f:
        json.dump(visa, f, separators=(",", ":"))
    print("визы:", len(passports), "паспортов x", len(dests), "стран -> data/visa.json")
else:
    print("visa_tidy_iso3.csv нет — фактор «Лёгкость легализации» будет без данных (запусти extra_data.py)")
