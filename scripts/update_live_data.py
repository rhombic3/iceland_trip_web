import json
import re
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

OUT = Path("assets/live-data.json")

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
ROAD_STATUS_URL = "https://gagnaveita.vegagerdin.is/api/faerd2017_1"

TRIP_DATA_JS = Path("assets/iceland-trip-data.js")

def load_weather_days_from_trip_data():
    text = TRIP_DATA_JS.read_text(encoding="utf-8")

    # 适用于文件里有 weatherStops: [...] 的情况。
    # 这个解析方式比完整解析 JS 简单，但要求 weatherStops 里只放普通对象，不要放函数。
    day_blocks = re.findall(
        r"\{[^{}]*?(?:id|date)\s*:\s*['\"][^'\"]+['\"][\s\S]*?weatherStops\s*:\s*(\[[\s\S]*?\])[\s\S]*?\}",
        text
    )

    # 更稳的方式：直接从所有 day 对象中提取 date/title/weatherStops
    day_pattern = re.compile(
        r"\{(?P<body>[\s\S]*?weatherStops\s*:\s*\[[\s\S]*?\][\s\S]*?)\}",
        re.MULTILINE
    )

    days = []
    for m in day_pattern.finditer(text):
        body = m.group("body")

        date_match = re.search(r"date\s*:\s*['\"]([^'\"]+)['\"]", body)
        title_match = re.search(r"title\s*:\s*['\"]([^'\"]+)['\"]", body)
        id_match = re.search(r"id\s*:\s*['\"]([^'\"]+)['\"]", body)
        alt_match = re.search(r"isAlternative\s*:\s*true", body)

        stops_match = re.search(r"weatherStops\s*:\s*(\[[\s\S]*?\])", body)
        if not date_match or not stops_match:
            continue

        raw_stops = stops_match.group(1)

        # 把 JS object 写法转成 JSON-like。
        # 要求 weatherStops 中字段写成 name/lat/lon，字符串用双引号或单引号都可以。
        json_like = raw_stops
        json_like = re.sub(r"(\w+)\s*:", r'"\1":', json_like)
        json_like = json_like.replace("'", '"')
        json_like = re.sub(r",\s*]", "]", json_like)
        json_like = re.sub(r",\s*}", "}", json_like)

        try:
            stops = json.loads(json_like)
        except Exception as e:
            raise ValueError(f"Failed to parse weatherStops for {date_match.group(1)}: {e}")

        days.append({
            "id": id_match.group(1) if id_match else date_match.group(1),
            "date": date_match.group(1),
            "title": title_match.group(1) if title_match else date_match.group(1),
            "isAlternative": bool(alt_match),
            "places": stops,
        })

    return days
# 这里按你想看的“地点 -> 公路”分组。
# keywords 用于在 Vegagerðin 返回的路段名称里做模糊匹配。
ROAD_GROUPS = [
    {
        "destination": "Landmannalaugar",
        "route_options": [
            {
                "name": "F26 + F208 North",
                "segments": [
                    {
                        "road": "F26",
                        "label": "Hringvegur → Vatnsfellsvirkjun",
                        "must_include": ["F26"],
                        "any_include": ["Hringvegur", "Vatnsfellsvirkjun", "Þjóðvegur", "Thjodvegur"],
                    },
                    {
                        "road": "F208",
                        "label": "Vatnsfellsvirkjun → Landmannalaugar",
                        "must_include": ["F208"],
                        "any_include": ["Vatnsfellsvirkjun", "Landmannalaugar", "Fjallabaksleið nyrðri", "Fjallabaksleid nyrdri"],
                    },
                ],
            },
            {
                "name": "F225 Landmannaleið",
                "segments": [
                    {
                        "road": "F225",
                        "label": "Landmannaleið",
                        "must_include": ["F225"],
                        "any_include": ["Landmannaleið", "Landmannaleid"],
                    },
                ],
            },
            {
                "name": "F208 South",
                "segments": [
                    {
                        "road": "F208",
                        "label": "F208 South / Eldgjá side",
                        "must_include": ["F208"],
                        "any_include": ["Eldgjá", "Eldgja", "Skaftártunga", "Fjallabaksleið syðri", "Fjallabaksleid sydri"],
                    },
                ],
            },
        ],
    },
    {
        "destination": "Mælifell / 抹茶山",
        "route_options": [
            {
                "name": "Vík → F232 → F210",
                "segments": [
                    {
                        "road": "F232",
                        "label": "F232 Öldufellsleið",
                        "must_include": ["F232"],
                        "any_include": ["Öldufellsleið", "Oldufellsleid"],
                    },
                    {
                        "road": "F210",
                        "label": "F210 near Mælifell",
                        "must_include": ["F210"],
                        "any_include": ["Mælifell", "Maelifell", "Fjallabaksleið syðri", "Fjallabaksleid sydri"],
                    },
                ],
            },
            {
                "name": "F210 direct",
                "segments": [
                    {
                        "road": "F210",
                        "label": "F210 Fjallabaksleið syðri",
                        "must_include": ["F210"],
                        "any_include": ["Fjallabaksleið syðri", "Fjallabaksleid sydri", "Mælifell", "Maelifell"],
                    },
                ],
            },
            {
                "name": "F233 / F210 alternative",
                "segments": [
                    {
                        "road": "F233",
                        "label": "F233 Álftavatnskrókur",
                        "must_include": ["F233"],
                        "any_include": ["Álftavatnskrókur", "Alftavatnskrokur"],
                    },
                    {
                        "road": "F210",
                        "label": "F210 connection",
                        "must_include": ["F210"],
                        "any_include": ["Fjallabaksleið syðri", "Fjallabaksleid sydri", "Mælifell", "Maelifell"],
                    },
                ],
            },
        ],
    },
    {
        "destination": "Þórsmörk",
        "route_options": [
            {
                "name": "F249",
                "segments": [
                    {
                        "road": "F249",
                        "label": "F249 Þórsmerkurvegur",
                        "must_include": ["F249"],
                        "any_include": ["Þórsmerkurvegur", "Thorsmerkurvegur", "Þórsmörk", "Thorsmork"],
                    },
                ],
            },
        ],
    },
    {
        "destination": "Kerlingarfjöll",
        "route_options": [
            {
                "name": "35 + F347",
                "segments": [
                    {
                        "road": "35",
                        "label": "Road 35 / Kjölur",
                        "must_include": ["35"],
                        "any_include": ["Kjalvegur", "Kjölur", "Kjolur"],
                    },
                    {
                        "road": "F347",
                        "label": "F347 Kerlingarfjallavegur",
                        "must_include": ["F347"],
                        "any_include": ["Kerlingarfjallavegur", "Kerlingarfjöll", "Kerlingarfjoll"],
                    },
                ],
            },
        ],
    },
    {
        "destination": "Þakgil",
        "route_options": [
            {
                "name": "Road 214",
                "segments": [
                    {
                        "road": "214",
                        "label": "Road 214 to Þakgil",
                        "must_include": ["214"],
                        "any_include": ["Þakgil", "Thakgil"],
                    },
                ],
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
    for day in load_weather_days_from_trip_data():
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


def match_sections(sections, must_include=None, any_include=None):
    must_include = [normalize_text(x) for x in (must_include or [])]
    any_include = [normalize_text(x) for x in (any_include or [])]

    matched = []
    for sec in sections:
        text = section_text(sec)

        if must_include and not all(k in text for k in must_include):
            continue

        if any_include and not any(k in text for k in any_include):
            continue

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
        return []

    output = []

    for group in ROAD_GROUPS:
        group_item = {
            "destination": group["destination"],
            "route_options": [],
        }

        for option in group["route_options"]:
            option_item = {
                "name": option["name"],
                "segments": [],
            }

            for seg in option["segments"]:
                matched = match_sections(
                    sections,
                    must_include=seg.get("must_include"),
                    any_include=seg.get("any_include"),
                )
                status = route_status_from_sections(matched)

                option_item["segments"].append({
                    "road": seg["road"],
                    "label": seg["label"],
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

            # 路线整体状态：只要有一段 closed，就路线 closed；全部 open 才 open。
            segment_opens = [s["open"] for s in option_item["segments"]]
            if any(v is False for v in segment_opens):
                option_item["overall_status"] = "Closed / Partly closed"
                option_item["overall_open"] = False
                option_item["overall_icon"] = "⛔"
            elif segment_opens and all(v is True for v in segment_opens):
                option_item["overall_status"] = "Open"
                option_item["overall_open"] = True
                option_item["overall_icon"] = "✅"
            else:
                option_item["overall_status"] = "Unknown / Check official"
                option_item["overall_open"] = None
                option_item["overall_icon"] = "❔"

            group_item["route_options"].append(option_item)

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