import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT = Path("assets/live-data.json")

PLACES = [
    {"name": "Reykjavík", "lat": 64.1466, "lon": -21.9426},
    {"name": "Landmannalaugar", "lat": 63.9926, "lon": -19.0609},
    {"name": "Mælifell / Fjallabak area", "lat": 63.7990, "lon": -18.9330},
    {"name": "Þórsmörk", "lat": 63.6806, "lon": -19.4828},
    {"name": "Vík", "lat": 63.4186, "lon": -19.0060},
    {"name": "Jökulsárlón", "lat": 64.0481, "lon": -16.1794},
    {"name": "Akureyri", "lat": 65.6885, "lon": -18.1262},
]

ROADS = [
    {
        "name": "F208 North / Landmannalaugar access",
        "status": "Check official source",
        "url": "https://umferdin.is/en",
        "note": "Check before driving to Landmannalaugar."
    },
    {
        "name": "F208 South",
        "status": "Check official source",
        "url": "https://umferdin.is/en",
        "note": "Often opens later than northern access."
    },
    {
        "name": "F210 / Mælifell area",
        "status": "Check official source",
        "url": "https://umferdin.is/en",
        "note": "Highland route; river crossings and closures possible."
    },
    {
        "name": "F249 / Þórsmörk",
        "status": "Check official source",
        "url": "https://umferdin.is/en",
        "note": "River crossings; usually not suitable for normal SUVs."
    },
    {
        "name": "F26 Sprengisandur",
        "status": "Check official source",
        "url": "https://umferdin.is/en",
        "note": "Long remote highland route; do not rely on historical opening dates."
    }
]

def fetch_json(url):
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))

def fetch_weather(place):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={place['lat']}&longitude={place['lon']}"
        "&current=temperature_2m,precipitation,wind_speed_10m,wind_gusts_10m"
        "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max"
        "&forecast_days=3"
        "&timezone=Atlantic%2FReykjavik"
    )
    data = fetch_json(url)
    current = data.get("current", {})
    daily = data.get("daily", {})

    return {
        "name": place["name"],
        "lat": place["lat"],
        "lon": place["lon"],
        "current": {
            "temperature": current.get("temperature_2m"),
            "precipitation": current.get("precipitation"),
            "wind_speed": current.get("wind_speed_10m"),
            "wind_gusts": current.get("wind_gusts_10m"),
            "time": current.get("time"),
        },
        "daily": daily,
    }

def main():
    weather = []
    for place in PLACES:
        try:
            weather.append(fetch_weather(place))
        except Exception as e:
            weather.append({
                "name": place["name"],
                "error": str(e),
            })

    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "weather_source": "Open-Meteo",
        "road_source": "Manual/official links; verify at road.is / trafficinfo.is",
        "weather": weather,
        "roads": ROADS,
        "warnings": [
            "Weather and highland road conditions change quickly in Iceland.",
            "Always verify road status on road.is / trafficinfo.is before driving.",
            "Do not drive closed highland roads even if maps or old reports suggest they may be passable."
        ]
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()