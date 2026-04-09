"""Weather lookup skill - returns current weather for a city."""


def weather_lookup(city: str) -> str:
    """Look up current weather conditions for a city.

    In a real deployment this would call a weather API.
    For the demo it returns a plausible placeholder.
    """
    return f"Weather in {city}: 18°C, partly cloudy, humidity 62%"
