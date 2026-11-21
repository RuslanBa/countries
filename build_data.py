"""
Собирает data/countries.json для карты из:
  countries.csv   — результат countries_data.py (Всемирный банк)
  pisa_2025.csv   — PISA 2025 (OECD)
Запуск:  python3 build_data.py countries.csv pisa_2025.csv
"""
import csv
import json
import sys

COUNTRIES_CSV = sys.argv[1] if len(sys.argv) > 1 else "countries.csv"
PISA_CSV = sys.argv[2] if len(sys.argv) > 2 else "pisa_2025.csv"
ISO_JSON = sys.argv[3] if len(sys.argv) > 3 else "/usr/share/iso-codes/json/iso_3166-1.json"
MIN_YEAR = 2021

# Показатель: (направление: +1 больше = лучше, -1 меньше = лучше), источник
IND = {
    "homicides_100k": (-1, "wb"), "political_stability_0_100": (1, "wgi"),
    "price_level_vs_usa": (-1, "wb"),
    "pisa": (1, "pisa"), "tertiary_enrollment": (1, "wb"),
    "life_expectancy": (1, "wb"), "uhc_index": (1, "who"), "infant_mortality": (-1, "wb"),
    "gdp_pc_ppp": (1, "wb"), "gdp_growth": (1, "wb"), "inflation": (-1, "wb"),
    "unemployment": (-1, "ilo"), "vulnerable_employment": (-1, "ilo"),
    "rule_of_law_0_100": (1, "wgi"), "control_corruption_0_100": (1, "wgi"),
}
# Фактор = взвешенное среднее процентилей его показателей.
FACTORS = {
    "safety":    [("homicides_100k", .5), ("political_stability_0_100", .5)],
    "cost":      [("price_level_vs_usa", 1.0)],
    "education": [("pisa", .7), ("tertiary_enrollment", .3)],
    "health":    [("life_expectancy", .4), ("uhc_index", .3), ("infant_mortality", .3)],
    "economy":   [("gdp_pc_ppp", .5), ("gdp_growth", .2), ("inflation", .3)],
    "jobs":      [("unemployment", .6), ("vulnerable_employment", .4)],
    "laws":      [("rule_of_law_0_100", .5), ("control_corruption_0_100", .5)],
}
# Ручные значения из национальных первоисточников (нет во Всемирном банке)
MANUAL = {
    ("ARG", "inflation"): (31.5, 2025, "indec"),  # INDEC, дек 2025 к дек 2024
}

iso = json.load(open(ISO_JSON, encoding="utf-8"))["3166-1"]
a3_to_a2 = {c["alpha_3"]: c["alpha_2"] for c in iso}
a3_to_a2["XKX"] = "XK"
num_to_a3 = {c["numeric"]: c["alpha_3"] for c in iso}

rows = list(csv.DictReader(open(COUNTRIES_CSV, encoding="utf-8")))
pisa = {r["iso3"]: r for r in csv.DictReader(open(PISA_CSV, encoding="utf-8"))}

countries = {}
for r in rows:
    c = {"iso3": r["iso3"], "iso2": a3_to_a2.get(r["iso3"]), "name": r["name"], "v": {}, "src": {}}
    for k in IND:
        if k == "pisa":
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

for (iso3, key), (val, yr, src) in MANUAL.items():
    if iso3 in countries:
        countries[iso3]["v"][key] = [val, yr]
        countries[iso3]["src"][key] = src


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
    c["f"] = {}
    for f, parts in FACTORS.items():
        total = sum(w for _, w in parts)
        have = [(P[k][i], w) for k, w in parts if i in P[k]]
        hw = sum(w for _, w in have)
        if hw >= 0.5 * total:
            c["f"][f] = round(sum(s * w for s, w in have) / hw)
            if hw < total:
                c.setdefault("partial", []).append(f)
    if not c["src"]:
        del c["src"]

out = {
    "generated": "2026-11-21",
    "min_year": MIN_YEAR,
    "factors": {f: [[k, w] for k, w in p] for f, p in FACTORS.items()},
    "indicators": {k: {"better": IND[k][0], "src": IND[k][1]} for k in IND},
    "num_to_iso3": num_to_a3,
    "countries": sorted(countries.values(), key=lambda c: c["iso3"]),
}
with open("data/countries.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
print("countries:", len(countries))
print("factor coverage:", {f: sum(1 for c in countries.values() if f in c["f"]) for f in FACTORS})
