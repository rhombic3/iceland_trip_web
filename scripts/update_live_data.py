import json
import re
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

OUT = Path("assets/live-data.json")

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
ROAD_STATUS_URL = "https://gagnaveita.vegagerdin.is/api/faerd2017_1"

# 这里按你的 6/7-6/17 行程配置。坐标可以之后继续微调。
# 注意：Open-Meteo 只有未来最多 16 天预报；离旅行太远时，目标日期可能没有数据。
DAY_PLACES = [
    {
        "date": "2026-06-07",
        "title": "Day 1 · Reykjavík & Golden Circle",
        "places": [
            {"name": "Reykjavík", "lat": 64.1466, "lon": -21.9426},
            {"name": "Þingvellir", "lat": 64.2559, "lon": -21.1295},
            {"name": "Brúarfoss", "lat": 64.2635, "lon": -20.5156},
            {"name": "Geysir", "lat": 64.3138, "lon": -20.3007},
            {"name": "Gullfoss", "lat": 64.3271, "lon": -20.1199},
        ],
    },
    {
        "date": "2026-06-08",
        "title": "Day 2 · South Coast",
        "places": [
            {"name": "Seljalandsfoss", "lat": 63.6156, "lon": -19.9886},
            {"name": "Skógafoss", "lat": 63.5321, "lon": -19.5114},
            {"name": "Reynisfjara", "lat": 63.4044, "lon": -19.0443},
            {"name": "Vík", "lat": 63.4186, "lon": -19.0060},
        ],
    },
    {
        "date": "2026-06-09",
        "title": "Day 3 · Skaftafell & Glacier Lagoon",
        "places": [
            {"name": "Fjaðrárgljúfur", "lat": 63.7712, "lon": -18.1719},
            {"name": "Skaftafell", "lat": 64.0150, "lon": -16.9669},
            {"name": "Jökulsárlón", "lat": 64.0481, "lon": -16.1794},
            {"name": "Diamond Beach", "lat": 64.0430, "lon": -16.1777},
        ],
    },
    {
        "date": "2026-06-10",
        "title": "Day 4 · East Iceland",
        "places": [
            {"name": "Höfn", "lat": 64.2497, "lon": -15.2020},
            {"name": "Stokksnes", "lat": 64.2445, "lon": -14.9720},
            {"name": "Djúpivogur", "lat": 64.6575, "lon": -14.2853},
            {"name": "Egilsstaðir", "lat": 65.2669, "lon": -14.3948},
        ],
    },
    {
        "date": "2026-06-11",
        "title": "Day 5 · North / Mývatn area",
        "places": [
            {"name": "Stuðlagil Canyon", "lat": 65.1637, "lon": -15.3077},
            {"name": "Dettifoss", "lat": 65.8147, "lon": -16.3846},
            {"name": "Mývatn", "lat": 65.6039, "lon": -16.9961},
            {"name": "Akureyri", "lat": 65.6885, "lon": -18.1262},
        ],
    },
    {
        "date": "2026-06-12",
        "title": "Day 6 · North to West",
        "places": [
            {"name": "Goðafoss", "lat": 65.6828, "lon": -17.5502},
            {"name": "Akureyri", "lat": 65.6885, "lon": -18.1262},
            {"name": "Hvítserkur", "lat": 65.6068, "lon": -20.6353},
            {"name": "Snæfellsnes", "lat": 64.8333, "lon": -23.0000},
        ],
    },
    {
        "date": "2026-06-13",
        "title": "Day 7 · Landmannalaugar",
        "places": [
            {"name": "Háifoss", "lat": 64.2070, "lon": -19.6869},
            {"name": "Sigöldugljúfur", "lat": 64.1578, "lon": -19.1390},
            {"name": "Landmannalaugar", "lat": 63.9926, "lon": -19.0609},
        ],
    },
    {
        "date": "2026-06-14",
        "title": "Day 8 · Þórsmörk",
        "places": [
            {"name": "Þórsmörk", "lat": 63.6806, "lon": -19.4828},
            {"name": "Stakkholtsgjá", "lat": 63.6864, "lon": -19.5130},
        ],
    },
    {
        "date": "2026-06-15",
        "title": "Day 9 · Kerlingarfjöll",
        "places": [
            {"name": "Kerlingarfjöll", "lat": 64.6423, "lon": -19.2887},
            {"name": "Hveradalir", "lat": 64.6529, "lon": -19.2824},
        ],
    },
    {
        "date": "2026-06-16",
        "title": "Day 10 · Þakgil / Vík area",
        "places": [
            {"name": "Þakgil", "lat": 63.5302, "lon": -18.8892},
            {"name": "Vík", "lat": 63.4186, "lon": -19.0060},
        ],
    },
    {
        "date": "2026-06-17",
        "title": "Day 11 · Mælifell / return",
        "places": [
            {"name": "Mælifell", "lat": 63.7990, "lon": -18.9330},
            {"name": "Vík", "lat": 63.4186, "lon": -19.0060},
            {"name": "Keflavík Airport", "lat": 63.9850, "lon": -22.6056},
        ],
    },
]

# 这里按你想看的“地点 -> 公路”分组。
# keywords 用于在 Vegagerðin 返回的路段名称里做模糊匹配。
ROAD_GROUPS = [
    {
        "destination": "Mælifell / 抹茶山",
        "routes": [
            {
                "road": "F232",
                "label": "Vík → F232 → F210",
                "keywords": ["F232", "Öldufellsleið", "Oldufellsleid"],
            },
            {
                "road": "F210",
                "label": "F210 Fjallabaksleið syðri",
                "keywords": ["F210", "Fjallabaksleið syðri", "Fjallabaksleid sydri", "Mælifell", "Maelifell"],
            },
            {
                "road": "F233",
                "label": "F233/F210 alternative",
                "keywords": ["F233", "Álftavatnskrókur", "Alftavatnskrokur"],
            },
        ],
    },
    {
        "destination": "Þórsmörk",
        "routes": [
            {
                "road": "F249",
                "label": "F249 Þórsmerkurvegur",
                "keywords": ["F249", "Þórsmerkurvegur", "Thorsmerkurvegur", "Þórsmörk", "Thorsmork"],
            },
        ],
    },
    {
        "destination": "Landmannalaugar",
        "routes": [
            {
                "road": "F26 + F208 North",
                "label": "F26 small part + F208 north access",
                "keywords": ["F26", "Sprengisandur", "F208", "Fjallabaksleið nyrðri", "Landmannalaugar"],
            },
            {
                "road": "F208 South",
                "label": "F208 south",
                "keywords": ["F208", "Fjallabaksleið syðri", "Eldgjá", "Skaftártunga"],
            },
            {
                "road": "F225",
                "label": "F225 Landmannaleið",
                "keywords": ["F225", "Landmannaleið", "Landmannaleid"],
            },
        ],
    },
    {
        "destination": "Kerlingarfjöll",
        "routes": [
            {
                "road": "35",
                "label": "Road 35 / Kjölur",
                "keywords": ["35", "Kjalvegur", "Kjölur", "Kjalvegur"],
            },
            {
                "road": "F347",
                "label": "F347 Kerlingarfjallavegur",
                "keywords": ["F347", "Kerlingarfjallavegur", "Kerlingarfjöll", "Kerlingarfjoll"],
            },
        ],
    },
    {
        "destination": "Þakgil",
        "routes": [
            {
                "road": "214",
                "label": "Road 214 to Þakgil",
                "keywords": ["214", "Þakgil", "Thakgil"],
            },
        ],
    },
]

STATUS_MAP = {
    "GREIDFAERT": ("Open", True, "✅"),
    "FAERT_FJALLABILUM": ("Mountain vehicles only", True, "⚠️"),
    "LOKAD": ("Closed", False, "⛔"),
    "ALLUR_AKSTUR_BANN": ("Driving prohibited", False, "⛔"),
    "OFAERT_ANNAD": ("Impassable", False, "⛔"),
    "OFAERT_VEDUR": ("Impassable due to weather", False, "⛔"),
    "OTHEKKT": ("Unknown", None, "❔"),
    "EKKI_I_THJONUSTU": ("Not in service", None, "❔"),
    "HALKA": ("Icy", True, "⚠️"),
    "HALKUBLETTIR": ("Spots of ice", True, "⚠️"),
    "SNJOTHEKJA": ("Snow cover", True, "⚠️"),
    "THUNGFAERT": ("Difficult driving", True, "⚠️"),
    "THAEFINGUR": ("Difficult driving", True, "⚠️"),
    "KRAP": ("Slush", True, "⚠️"),
    "FLUGHALT": ("Extremely slippery", True, "⚠️"),
}

WEATHER_CODE = {
    0: ("晴", "☀️"),
    1: ("大致晴朗", "🌤️"),
    2: ("局部多云", "⛅"),
    3: ("多云", "☁️"),
    45: ("雾", "🌫️"),
    48: ("雾凇", "🌫️"),
    51: ("小毛毛雨", "🌦️"),
    53: ("毛毛雨", "🌦️"),
    55: ("较强毛毛雨", "🌧️"),
    61: ("小雨", "🌧️"),
    63: ("中雨", "🌧️"),
    65: ("大雨", "🌧️"),
    71: ("小雪", "🌨️"),
    73: ("中雪", "🌨️"),
    75: ("大雪", "🌨️"),
    80: ("阵雨", "🌦️"),
    81: ("较强阵雨", "🌧️"),
    82: ("强阵雨", "⛈️"),
    95: ("雷暴", "⛈️"),
    96: ("雷暴伴冰雹", "⛈️"),
    99: ("强雷暴伴冰雹", "⛈️"),
}


def fetch_json(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "iceland-trip-web/1.0 (+https://github.com/rhombic3/iceland_trip_web)"
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        text = r.read().decode("utf-8")
        return json.loads(text)


def build_weather_url(place, start_date, end_date):
    params = {
        "latitude": place["lat"],
        "longitude": place["lon"],
        "daily": ",".join([
            "weather_code",
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "precipitation_probability_max",
            "wind_speed_10m_max",
            "wind_gusts_10m_max",
        ]),
        "timezone": "Atlantic/Reykjavik",
        "start_date": start_date,
        "end_date": end_date,
    }
    return OPEN_METEO_URL + "?" + urllib.parse.urlencode(params)


def first_value(daily, key):
    values = daily.get(key) or []
    return values[0] if values else None


def fetch_place_weather(place, date):
    url = build_weather_url(place, date, date)
    data = fetch_json(url)
    daily = data.get("daily", {})

    code = first_value(daily, "weather_code")
    summary, icon = WEATHER_CODE.get(code, ("未知", "❔"))

    return {
        "name": place["name"],
        "lat": place["lat"],
        "lon": place["lon"],
        "date": date,
        "summary": summary,
        "icon": icon,
        "weather_code": code,
        "temperature_min": first_value(daily, "temperature_2m_min"),
        "temperature_max": first_value(daily, "temperature_2m_max"),
        "precipitation_sum": first_value(daily, "precipitation_sum"),
        "precipitation_probability_max": first_value(daily, "precipitation_probability_max"),
        "wind_speed_max": first_value(daily, "wind_speed_10m_max"),
        "wind_gusts_max": first_value(daily, "wind_gusts_10m_max"),
        "source_url": url,
    }


def fetch_daily_weather():
    results = []
    for day in DAY_PLACES:
        day_item = {
            "date": day["date"],
            "title": day["title"],
            "places": [],
        }

        for place in day["places"]:
            try:
                day_item["places"].append(fetch_place_weather(place, day["date"]))
            except Exception as e:
                day_item["places"].append({
                    "name": place["name"],
                    "date": day["date"],
                    "error": str(e),
                    "summary": "暂无预报",
                    "icon": "❔",
                })

        results.append(day_item)

    return results


def normalize_text(s):
    if s is None:
        return ""
    s = str(s)
    s = s.replace("ð", "d").replace("Ð", "D")
    s = s.replace("þ", "th").replace("Þ", "Th")
    s = s.replace("æ", "ae").replace("Æ", "Ae")
    s = s.replace("ö", "o").replace("Ö", "O")
    s = s.replace("á", "a").replace("Á", "A")
    s = s.replace("í", "i").replace("Í", "I")
    s = s.replace("ó", "o").replace("Ó", "O")
    s = s.replace("ú", "u").replace("Ú", "U")
    s = s.lower()
    s = re.sub(r"\s+", " ", s)
    return s


def fetch_road_sections():
    data = fetch_json(ROAD_STATUS_URL)

    # Vegagerðin 接口通常直接返回 list；为了稳妥兼容 dict 包一层的情况。
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ["features", "items", "data", "results"]:
            value = data.get(key)
            if isinstance(value, list):
                if key == "features":
                    return [f.get("properties", f) for f in value]
                return value

    return []


def section_text(section):
    parts = [
        section.get("StuttNafnButs"),
        section.get("FulltNafnButs"),
        section.get("Aths"),
        section.get("AthsEn"),
    ]
    return normalize_text(" ".join(str(p) for p in parts if p))


def match_sections(sections, keywords):
    norm_keywords = [normalize_text(k) for k in keywords]
    matched = []
    for sec in sections:
        text = section_text(sec)
        if any(k in text for k in norm_keywords):
            matched.append(sec)
    return matched


def route_status_from_sections(sections):
    if not sections:
        return {
            "status": "Unknown",
            "open": None,
            "icon": "❔",
            "detail": "No matching official road section found.",
        }

    raw_values = []
    labels = []

    for sec in sections:
        raw = sec.get("AstandYfirbord") or sec.get("Astand") or ""
        extra = sec.get("AstandVidbotaruppl") or ""
        raw_values.extend([raw, extra])

        label = sec.get("AstandLysingEn") or sec.get("AstandLysing") or raw
        if label:
            labels.append(label)

    raw_values = [str(v).strip().upper() for v in raw_values if v]

    # 优先级：禁止/关闭 > 山地车可通行 > 开放 > 其他警告 > unknown
    closed_codes = {"LOKAD", "ALLUR_AKSTUR_BANN", "OFAERT_ANNAD", "OFAERT_VEDUR"}
    if any(v in closed_codes for v in raw_values):
        return {
            "status": "Closed",
            "open": False,
            "icon": "⛔",
            "detail": " / ".join(sorted(set(labels))) or "Closed",
        }

    if "FAERT_FJALLABILUM" in raw_values:
        return {
            "status": "Mountain vehicles only",
            "open": True,
            "icon": "⚠️",
            "detail": " / ".join(sorted(set(labels))) or "Passable for mountain vehicles",
        }

    if "GREIDFAERT" in raw_values:
        return {
            "status": "Open",
            "open": True,
            "icon": "✅",
            "detail": " / ".join(sorted(set(labels))) or "Clear / passable",
        }

    if raw_values:
        first = raw_values[0]
        status, open_value, icon = STATUS_MAP.get(first, ("Check condition", None, "⚠️"))
        return {
            "status": status,
            "open": open_value,
            "icon": icon,
            "detail": " / ".join(sorted(set(labels))) or first,
        }

    return {
        "status": "Unknown",
        "open": None,
        "icon": "❔",
        "detail": "No condition value found.",
    }


def fetch_road_groups():
    try:
        sections = fetch_road_sections()
    except Exception as e:
        return [
            {
                "destination": group["destination"],
                "routes": [
                    {
                        "road": route["road"],
                        "label": route["label"],
                        "status": "Fetch failed",
                        "open": None,
                        "icon": "❔",
                        "detail": str(e),
                        "official_url": "https://umferdin.is/en",
                    }
                    for route in group["routes"]
                ],
            }
            for group in ROAD_GROUPS
        ]

    output = []
    for group in ROAD_GROUPS:
        group_item = {
            "destination": group["destination"],
            "routes": [],
        }

        for route in group["routes"]:
            matched = match_sections(sections, route["keywords"])
            status = route_status_from_sections(matched)

            group_item["routes"].append({
                "road": route["road"],
                "label": route["label"],
                "status": status["status"],
                "open": status["open"],
                "icon": status["icon"],
                "detail": status["detail"],
                "matched_count": len(matched),
                "matched_sections": [
                    {
                        "name": sec.get("FulltNafnButs") or sec.get("StuttNafnButs"),
                        "condition": sec.get("AstandYfirbord") or sec.get("Astand"),
                        "condition_en": sec.get("AstandLysingEn") or sec.get("AstandLysing"),
                        "registered_at": sec.get("DagsSkrad"),
                    }
                    for sec in matched[:6]
                ],
                "official_url": "https://umferdin.is/en",
            })

        output.append(group_item)

    return output


def main():
    payload = {
        "updated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "weather_source": "Open-Meteo Forecast API",
        "road_source": "Vegagerðin / umferdin.is faerd2017_1",
        "daily_weather": fetch_daily_weather(),
        "road_groups": fetch_road_groups(),
        "official_links": {
            "traffic": "https://umferdin.is/en",
            "mountain_roads": "https://www.vegagerdin.is/ferdaupplysingar/fjallvegir",
            "weather": "https://en.vedur.is",
            "safetravel": "https://safetravel.is",
        },
        "warnings": [
            "Weather and highland road conditions change quickly in Iceland.",
            "Always verify road status on road.is / umferdin.is before driving.",
            "If a road is marked closed or all driving is prohibited, do not drive it.",
            "This page is a convenience dashboard, not a substitute for official road signs or safety advice.",
        ],
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()