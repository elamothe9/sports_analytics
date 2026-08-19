import requests

from services.cache import ttl_cache

# Venue coordinates for Open-Meteo lookups
VENUE_COORDINATES = {
    "American Family Field":       {"lat": 43.0280, "lon": -87.9712},
    "Angel Stadium of Anaheim":    {"lat": 33.8003, "lon": -117.8827},
    "Busch Stadium":               {"lat": 38.6226, "lon": -90.1928},
    "Chase Field":                 {"lat": 33.4453, "lon": -112.0667},
    "Citi Field":                  {"lat": 40.7571, "lon": -73.8458},
    "Citizens Bank Park":          {"lat": 39.9061, "lon": -75.1665},
    "Comerica Park":               {"lat": 42.3390, "lon": -83.0485},
    "Coors Field":                 {"lat": 39.7559, "lon": -104.9942},
    "Daikin Park":                 {"lat": 29.7572, "lon": -95.3555},
    "Dodger Stadium":              {"lat": 34.0739, "lon": -118.2400},
    "Ewing M. Kauffman Stadium":   {"lat": 39.0517, "lon": -94.4803},
    "Fenway Park":                 {"lat": 42.3467, "lon": -71.0972},
    "Globe Life Field":            {"lat": 32.7473, "lon": -97.0822},
    "Great American Ball Park":    {"lat": 39.0979, "lon": -84.5082},
    "Nationals Park":              {"lat": 38.8730, "lon": -77.0074},
    "Oracle Park":                 {"lat": 37.7786, "lon": -122.3893},
    "Oriole Park at Camden Yards": {"lat": 39.2838, "lon": -76.6218},
    "PETCO Park":                  {"lat": 32.7076, "lon": -117.1570},
    "PNC Park":                    {"lat": 40.4469, "lon": -80.0057},
    "Progressive Field":           {"lat": 41.4962, "lon": -81.6852},
    "Rate Field":                  {"lat": 41.8300, "lon": -87.6338},
    "Rogers Centre":               {"lat": 43.6414, "lon": -79.3894},
    "Sutter Health Park":          {"lat": 38.5802, "lon": -121.5005},
    "T-Mobile Park":               {"lat": 47.5914, "lon": -122.3325},
    "Target Field":                {"lat": 44.9817, "lon": -93.2781},
    "Tropicana Field":             {"lat": 27.7682, "lon": -82.6534},
    "Truist Park":                 {"lat": 33.8908, "lon": -84.4678},
    "Wrigley Field":               {"lat": 41.9484, "lon": -87.6553},
    "Yankee Stadium":              {"lat": 40.8296, "lon": -73.9262},
    "loanDepot Park":              {"lat": 25.7781, "lon": -80.2197},
}

# Indoor stadiums — weather doesn't apply
INDOOR_VENUES = {
    "Chase Field",       # retractable roof
    "Daikin Park",       # retractable roof
    "Globe Life Field",  # retractable roof
    "Rogers Centre",     # retractable roof
    "Tropicana Field",   # fixed dome
    "loanDepot Park",    # retractable roof
}


@ttl_cache(seconds=10 * 60)
def get_weather_for_venue(venue: str) -> dict:
    """
    Fetch current weather at a venue using Open-Meteo.
    Returns neutral weather for indoor stadiums.
    """
    if venue in INDOOR_VENUES:
        return {
            "temp_f": 72,
            "wind_speed": 0,
            "wind_direction": "calm",
            "indoor": True,
        }

    coords = VENUE_COORDINATES.get(venue)
    if not coords:
        return {
            "temp_f": 72,
            "wind_speed": 0,
            "wind_direction": "calm",
            "indoor": False,
        }

    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": coords["lat"],
            "longitude": coords["lon"],
            "current": "temperature_2m,wind_speed_10m,wind_direction_10m",
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "forecast_days": 1,
        }
        res = requests.get(url, params=params, timeout=5)
        res.raise_for_status()
        current = res.json()["current"]

        wind_deg = current.get("wind_direction_10m", 0)
        wind_dir = degrees_to_direction(wind_deg)

        return {
            "temp_f": round(current["temperature_2m"], 1),
            "wind_speed": round(current["wind_speed_10m"], 1),
            "wind_direction": wind_dir,
            "indoor": False,
        }
    except Exception:
        return {
            "temp_f": 72,
            "wind_speed": 0,
            "wind_direction": "calm",
            "indoor": False,
        }


def degrees_to_direction(degrees: float) -> str:
    """
    Convert wind degrees to a simplified baseball direction.
    This is a rough approximation — stadium orientation varies.
    Directions 'out' mean blowing toward the outfield.
    """
    # Normalize to 0-360
    degrees = degrees % 360

    if 315 <= degrees or degrees < 45:
        return "out to cf"
    elif 45 <= degrees < 135:
        return "out to rf"
    elif 135 <= degrees < 225:
        return "in from cf"
    else:
        return "out to lf"
