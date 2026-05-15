import json
import re
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
import subprocess

OUT = Path("assets/live-data.json")
TRIP_DATA_JS = Path("assets/iceland-trip-data.js")
TRIP_YEAR = 2026

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
ROAD_STATUS_URL = "https://gagnaveita.vegagerdin.is/api/faerd2017_1"

TRIP_DATA_JS = Path("assets/iceland-trip-data.js")

# keywords 用于在 Vegagerðin 返回的路段名称里做模糊匹配。
ROAD_GROUPS = [
    {
        "destination": "Landmannalaugar",
        "route_options": [
            {
                "name": "F26 + F208 North",
                "segments": [
                    {"road": "26", "label": "Landvegur: Hringvegur - Laugaland", "official_name": "Landvegur : Hringvegur - Laugaland"},
                    {"road": "26", "label": "Landvegur: Laugaland - Bjallavegur", "official_name": "Landvegur: Laugaland - Bjallavegur"},
                    {"road": "26", "label": "Landvegur: Bjallavegur - Galtalækur", "official_name": "Landvegur : Bjallavegur - Galtalækur"},
                    {"road": "26", "label": "Landvegur: Galtalækur - Þjórsárdalsvegur", "official_name": "Landvegur : Galtalækur - Þjórsárdalsvegur"},
                    {"road": "26", "label": "Þjórsárdalsvegur - Vatnsfellsvirkjun", "official_name": "Þjórsárdalsvegur - Vatnsfellsvirkjun"},
                    {"road": "208", "label": "Sigalda - Landmannalaugar", "official_name": "Fjallabaksleið nyrðri: Sigalda - Landmannalaugar"},
                ],
            },
            {
                "name": "F26 + F225",
                "segments": [
                    {"road": "26", "label": "Landvegur: Hringvegur - Laugaland", "official_name": "Landvegur : Hringvegur - Laugaland"},
                    {"road": "26", "label": "Landvegur: Laugaland - Bjallavegur", "official_name": "Landvegur: Laugaland - Bjallavegur"},
                    {"road": "26", "label": "Landvegur: Bjallavegur - Galtalækur", "official_name": "Landvegur : Bjallavegur - Galtalækur"},
                    {"road": "26", "label": "Landvegur: Galtalækur - Þjórsárdalsvegur", "official_name": "Landvegur : Galtalækur - Þjórsárdalsvegur"},
                    {"road": "225", "label": "Landmannaleið vestan Heklu", "official_name": "Landmannaleið vestan Heklu"},
                    {"road": "225", "label": "Landmannaleið: Hekla - Landmannahellir", "official_name": "Landmannaleið: Hekla - Landmannahellir"},
                    {"road": "225", "label": "Landmannaleið: Landmannahellir - Fjallabak N", "official_name": "Landmannaleið: Landmannahellir - Fjallabak N"},
                ],
            },
            {
                "name": "F208 South",
                "segments": [
                    {"road": "208", "label": "Skaftártunguvegur austan Flögu", "official_name": "Skaftártunguvegur austan Flögu"},
                    {"road": "208", "label": "Skaftártunguvegur og Ljótarstaðavegur", "official_name": "Skaftártunguvegur og Ljótarstaðavegur"},
                    {"road": "208", "label": "Búland - Eldgjá", "official_name": "Fjallabaksleið nyrðri: Búland - Eldgjá"},
                    {"road": "208", "label": "Eldgjá - Landmannalaugavegur", "official_name": "Fjallabaksleið nyrðri: Eldgjá - Landmannalaugavegur"},
                ],
            },
        ],
    },

    {
        "destination": "Mælifell / 抹茶山",
        "route_options": [
            {
                "name": "F232 + F210",
                "segments": [
                    {"road": "232", "label": "Öldufellsleið", "official_name": "Öldufellsleið"},
                    {"road": "210", "label": "Snæbýli - Emstruleið", "official_name": "Fjallabaksleið syðri: Snæbýli - Emstruleið"},
                ],
            },
            {
                "name": "F210 West",
                "segments": [
                    {"road": "210", "label": "Snæbýli - Emstruleið", "official_name": "Fjallabaksleið syðri: Snæbýli - Emstruleið"},
                    {"road": "210", "label": "Emstruleið - Rangárvallavegur", "official_name": "Fjallabaksleið syðri: Emstruleið - Rangárvallavegur"},
                ],
            },
            {
                "name": "F261 + F210",
                "segments": [
                    {"road": "261", "label": "Emstruleið", "official_name": "Emstruleið"},
                    {"road": "210", "label": "Snæbýli - Emstruleið", "official_name": "Fjallabaksleið syðri: Snæbýli - Emstruleið"},
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
                    {"road": "249", "label": "að Seljalandsfossi", "official_name": "Þórsmerkurvegur að Seljalandsfossi"},
                    {"road": "249", "label": "Seljalandsfoss - Merkurvegur", "official_name": "Þórsmerkurvegur: Seljalandsfoss - Merkurvegur"},
                    {"road": "249", "label": "Merkurvegur - Stóra-Mörk", "official_name": "Þórsmerkurvegur: Merkurvegur - Stóra-Mörk"},
                    {"road": "249", "label": "Stóra-Mörk - Nauthúsagil", "official_name": "Þórsmerkurvegur: Stóra-Mörk - Nauthúsagil"},
                    {"road": "249", "label": "Nauthúsagil - Jökultungur", "official_name": "Þórsmerkurvegur: Nauthúsagil - Jökultungur"},
                    {"road": "249", "label": "Jökultungur - Básar", "official_name": "Þórsmerkurvegur: Jökultungur - Básar"},
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
                    {"road": "35", "label": "Múli - Gullfoss", "official_name": "Biskupstungnabraut: Múli - Gullfoss"},
                    {"road": "35", "label": "Gullfoss - Hagavatnsvegur", "official_name": "Kjalvegur: Gullfoss - Hagavatnsvegur"},
                    {"road": "35", "label": "Hagavatnsvegur - Bláfellsháls", "official_name": "Kjalvegur: Hagavatnsvegur - Bláfellsháls"},
                    {"road": "35", "label": "Bláfellsháls - Kerlingarfjallavegur", "official_name": "Kjalvegur: Bláfellsháls - Kerlingarfjallavegur"},
                    {"road": "347", "label": "Kerlingarfjallavegur", "official_name": "Kerlingarfjallavegur"},
                    {"road": "347", "label": "Ásgarður - Hveradalir", "official_name": "Ásgarður - Hveradalir"},
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
                    {"road": "214", "label": "Kerlingardalsvegur: Þakgil", "official_name": "Kerlingardalsvegur: Þakgil"},
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

    for day in build_weather_days_from_trip_data():
        day_item = {
            "id": day.get("id"),
            "date": day["date"],
            "tab": day.get("tab", ""),
            "title": day["title"],
            "isAlternative": day.get("isAlternative", False),
            "places": [],
        }

        for place in day["places"]:
            try:
                day_item["places"].append(fetch_place_weather(place, day["date"]))
            except Exception:
                # 如果目标日期还没有天气预报，就回退到当天实时/当日天气。
                try:
                    today = datetime.now(timezone.utc).date().isoformat()
                    fallback = fetch_place_weather(place, today)
                    fallback["target_date"] = day["date"]
                    fallback["fallback_date"] = today
                    fallback["is_fallback"] = True
                    fallback["fallback_note"] = f"目标日期 {day['date']} 暂无预报，当前显示 {today} 的天气。"
                    day_item["places"].append(fallback)
                except Exception as e2:
                    day_item["places"].append({
                        "id": place.get("id"),
                        "name": place["name"],
                        "date": day["date"],
                        "error": str(e2),
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

def canonical_road_name(s):
    """
    Normalize official Icelandic road-section names for robust exact matching.
    Handles spacing around ':' and '-' and small punctuation differences.
    """
    s = normalize_text(s)
    s = s.replace("：", ":")
    s = s.replace("–", "-").replace("—", "-")
    s = re.sub(r"\s*:\s*", ":", s)
    s = re.sub(r"\s*-\s*", "-", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()

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

def normalize_section_id(x):
    if x is None:
        return ""
    return str(x).replace(".0", "").strip()

def get_section_id(sec):
    return normalize_section_id(
        sec.get("IdButur")
        or sec.get("ButurID")
        or sec.get("Id")
        or sec.get("id")
    )

def match_sections(sections, section_ids=None, official_name=None, match_all=None, match_any=None):
    section_ids = {normalize_section_id(x) for x in (section_ids or [])}
    match_all = [normalize_text(x) for x in (match_all or [])]
    match_any = [normalize_text(x) for x in (match_any or [])]

    target_name = canonical_road_name(official_name) if official_name else None

    matched = []

    for sec in sections:
        sec_id = get_section_id(sec)

        if section_ids:
            if sec_id in section_ids:
                matched.append(sec)
            continue

        full_name = sec.get("FulltNafnButs") or ""
        short_name = sec.get("StuttNafnButs") or ""

        if target_name:
            full_norm = canonical_road_name(full_name)
            short_norm = canonical_road_name(short_name)

            # 优先 full name 精确匹配；short name 作为兜底。
            if target_name == full_norm or target_name == short_norm:
                matched.append(sec)
            continue

        text = section_text(sec)

        if match_all and not all(k in text for k in match_all):
            continue

        if match_any and not any(k in text for k in match_any):
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
                    section_ids=seg.get("section_ids"),
                    official_name=seg.get("official_name"),
                    match_all=seg.get("match_all"),
                    match_any=seg.get("match_any"),
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
                            "id": get_section_id(sec),
                            "name": sec.get("FulltNafnButs") or sec.get("StuttNafnButs"),
                            "short_name": sec.get("StuttNafnButs"),
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

def load_trip_data_from_js():
    """
    Read assets/iceland-trip-data.js and extract const spots / const days.

    This works with files like:
      const spots = {...}
      const days = [...]
    """
    js_path = TRIP_DATA_JS.resolve()

    node_code = f"""
const fs = require('fs');
const vm = require('vm');

const code = fs.readFileSync({json.dumps(str(js_path))}, 'utf8');

const sandbox = {{}};
vm.createContext(sandbox);

vm.runInContext(code + `
;globalThis.__tripData = {{
  spots: typeof spots !== 'undefined' ? spots : {{}},
  days: typeof days !== 'undefined' ? days : [],
  alternatives: typeof alternatives !== 'undefined' ? alternatives : []
}};
`, sandbox);

console.log(JSON.stringify(sandbox.__tripData));
"""

    result = subprocess.run(
        ["node", "-e", node_code],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    return json.loads(result.stdout)


def parse_trip_date(day):
    """
    Convert day.tab like '6/7' to '2026-06-07'.
    If the day already has a date field, use it directly.
    """
    if day.get("date"):
        return day["date"]

    tab = str(day.get("tab", "")).strip()
    m = re.search(r"(\d{1,2})\s*/\s*(\d{1,2})", tab)
    if not m:
        return datetime.now(timezone.utc).date().isoformat()

    month = int(m.group(1))
    date = int(m.group(2))
    return f"{TRIP_YEAR}-{month:02d}-{date:02d}"


def should_skip_weather_spot(spot_id, spot):
    """
    Exclude places that are not useful for tourist weather cards.
    You can adjust this list later.
    """
    sid = str(spot_id).upper()
    name = str(spot.get("name", "")).lower()

    skip_keywords = [
        "stay",
        "hotel",
        "住宿",
        "机场",
        "airport",
        "toilet",
        "厕所",
        "gas",
        "加油",
        "supermarket",
        "bónus",
        "bonus",
        "krónan",
        "kronan",
    ]

    if sid.startswith(("STAY", "HOTEL", "LODGE", "TOILET", "GAS", "FOOD")):
        return True

    return any(k in name for k in skip_keywords)


def build_weather_days_from_trip_data():
    trip = load_trip_data_from_js()
    spots = trip.get("spots", {})

    # 如果你的 4 个备选也在 days 里，这里会自动包含。
    # 如果你单独用了 alternatives 数组，这里也会拼进去。
    raw_days = []
    raw_days.extend(trip.get("days", []))
    raw_days.extend(trip.get("alternatives", []))

    weather_days = []

    for index, day in enumerate(raw_days, start=1):
        spot_ids = day.get("spots", [])
        places = []

        for spot_id in spot_ids:
            spot = spots.get(spot_id)
            if not spot:
                continue

            if should_skip_weather_spot(spot_id, spot):
                continue

            lat = spot.get("lat")
            lon = spot.get("lng", spot.get("lon"))

            if lat is None or lon is None:
                continue

            places.append({
                "id": spot_id,
                "name": spot.get("name", spot_id),
                "lat": lat,
                "lon": lon,
            })

        # 避免一天景点过多，天气区太长。你可以改成 6 或 8。
        places = places[:8]

        if not places:
            continue

        weather_days.append({
            "id": day.get("id", f"day-{index}"),
            "date": parse_trip_date(day),
            "tab": day.get("tab", ""),
            "title": day.get("title", f"Day {index}"),
            "isAlternative": bool(day.get("isAlternative", False) or day.get("alternative", False)),
            "places": places,
        })

    return weather_days

if __name__ == "__main__":
    main()