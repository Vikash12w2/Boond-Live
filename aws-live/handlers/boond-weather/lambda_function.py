
import boto3
import json
import urllib.request
import urllib.parse

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("boond")


def response(status_code, data):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(data)
    }


def lambda_handler(event, context):

    # Get field token from /fields/{token}/weather
    path_parameters = event.get("pathParameters") or {}
    field_token = path_parameters.get("token")

    if not field_token:
        return response(400, {"error": "Field token is required"})

    # Get registered field profile
    try:
        result = table.get_item(
            Key={
                "pk": f"FIELD#{field_token}",
                "sk": "PROFILE"
            }
        )
    except Exception as exc:
        print(f"Could not read field profile: {exc}")
        return response(500, {"error": "Could not read field profile"})

    field = result.get("Item")

    if not field:
        return response(404, {"error": "Field not found"})

    latitude = float(field["latitude"])
    longitude = float(field["longitude"])

    # Request weather data needed by the irrigation engine.
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": ",".join([
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "precipitation_probability_max",
            "et0_fao_evapotranspiration",
            "relative_humidity_2m_min",
            "wind_speed_10m_max"
        ]),
        "forecast_days": 16,
        "past_days": 3,
        "timezone": "Asia/Kolkata"
    }

    url = (
        "https://api.open-meteo.com/v1/forecast?"
        + urllib.parse.urlencode(params)
    )

    try:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "BoondLive/1.0"}
        )

        with urllib.request.urlopen(request, timeout=20) as response_obj:
            weather = json.loads(
                response_obj.read().decode("utf-8")
            )

        # Ensure the essential daily series are present.
        daily = weather.get("daily", {})
        required_series = [
            "time",
            "et0_fao_evapotranspiration",
            "precipitation_sum",
            "temperature_2m_max",
            "precipitation_probability_max"
        ]

        missing = [
            key for key in required_series
            if key not in daily
        ]

        if missing:
            print(f"Weather response missing fields: {missing}")
            return response(502, {
                "error": "Weather response is incomplete",
                "missing_fields": missing
            })

    except Exception as exc:
        print(f"Weather service error: {exc}")
        return response(502, {
            "error": "Weather service unavailable",
            "details": str(exc)
        })

    return response(200, {
        "field_token": field_token,
        "latitude": latitude,
        "longitude": longitude,
        "timezone": weather.get("timezone"),
        "weather": weather
    })
