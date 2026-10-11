import json

import boto3

import urllib.request

import urllib.parse

from datetime import date, datetime, timedelta

from decimal import Decimal

from zoneinfo import ZoneInfo

from botocore.exceptions import ClientError

from boto3.dynamodb.conditions import Key, Attr

from engine.field_runner import advance_field, MissingWeather

from engine.messages import render

# ==================================================

# CONFIGURATION

# ==================================================

TABLE_NAME = "boond"

TIMEZONE = ZoneInfo("Asia/Kolkata")

dynamodb = boto3.resource("dynamodb")

table = dynamodb.Table(TABLE_NAME)

# ==================================================

# GENERAL HELPERS

# ==================================================

def today_local():

    return datetime.now(TIMEZONE).date()

def json_default(value):

    if isinstance(value, Decimal):

        return float(value)

    if isinstance(value, (date, datetime)):

        return value.isoformat()

    raise TypeError(f"Cannot serialize {type(value).__name__}")

def json_response(status_code, body):

    return {

        "statusCode": status_code,

        "headers": {"Content-Type": "application/json"},

        "body": json.dumps(body, default=json_default)

    }

def to_float(value):

    if isinstance(value, Decimal):

        return float(value)

    if isinstance(value, dict):

        return {

            key: to_float(item)

            for key, item in value.items()

        }

    if isinstance(value, list):

        return [to_float(item) for item in value]

    if isinstance(value, tuple):

        return [to_float(item) for item in value]

    return value

def to_dynamodb(value):

    if isinstance(value, float):

        return Decimal(str(value))

    if isinstance(value, dict):

        return {

            key: to_dynamodb(item)

            for key, item in value.items()

        }

    if isinstance(value, list):

        return [to_dynamodb(item) for item in value]

    if isinstance(value, tuple):

        return [to_dynamodb(item) for item in value]

    return value

def get_json(url):

    request = urllib.request.Request(

        url,

        headers={"User-Agent": "BoondLive/1.0"}

    )

    with urllib.request.urlopen(request, timeout=20) as response:

        return json.loads(response.read().decode("utf-8"))

# ==================================================

# WEATHER RETRIEVAL

# ==================================================

def fetch_weather(latitude, longitude, endpoint, start_date, end_date):

    params = {

        "latitude": latitude,

        "longitude": longitude,

        "start_date": start_date.isoformat(),

        "end_date": end_date.isoformat(),

        "daily": (

            "temperature_2m_max,"

            "precipitation_sum,"

            "precipitation_probability_max,"

            "et0_fao_evapotranspiration"

        ),

        "timezone": "Asia/Kolkata"

    }

    url = endpoint + "?" + urllib.parse.urlencode(params)

    data = get_json(url)

    daily = data.get("daily", {})

    dates = daily.get("time", [])

    rows = []

    for index, day in enumerate(dates):

        def value(name, default=0):

            values = daily.get(name, [])

            if index >= len(values) or values[index] is None:

                return default

            return values[index]

        rows.append({

            "date": day,

            "et0_mm": value("et0_fao_evapotranspiration"),

            "rain_mm": value("precipitation_sum"),

            "tmax_c": value("temperature_2m_max"),

            "rain_prob": value("precipitation_probability_max", None)

        })

    return rows

def weather_rows(latitude, longitude, today, first_needed_date):

    """

    Fetch historical weather through yesterday and forecast weather

    beginning today.

    Return weather as dictionaries containing parallel arrays.

    """

    observed_rows = []

    forecast_rows = []

    yesterday = today - timedelta(days=1)

    # Older historical data: Open-Meteo archive.

    archive_end = min(yesterday, today - timedelta(days=4))

    if first_needed_date <= archive_end:

        observed_rows.extend(

            fetch_weather(

                latitude,

                longitude,

                "https://archive-api.open-meteo.com/v1/archive",

                first_needed_date,

                archive_end

            )

        )

    # Recent historical data: forecast API past days.

    recent_start = max(

        first_needed_date,

        today - timedelta(days=3)

    )

    if recent_start <= yesterday:

        observed_rows.extend(

            fetch_weather(

                latitude,

                longitude,

                "https://api.open-meteo.com/v1/forecast",

                recent_start,

                yesterday

            )

        )

    # Today's forecast and the following 15 days.

    forecast_rows.extend(

        fetch_weather(

            latitude,

            longitude,

            "https://api.open-meteo.com/v1/forecast",

            today,

            today + timedelta(days=15)

        )

    )

    # Deduplicate and sort weather rows.

    observed_by_date = {

        row["date"]: row for row in observed_rows

    }

    forecast_by_date = {

        row["date"]: row for row in forecast_rows

    }

    observed_rows = [

        observed_by_date[key]

        for key in sorted(observed_by_date)

    ]

    forecast_rows = [

        forecast_by_date[key]

        for key in sorted(forecast_by_date)

    ]

    # Convert rows into the engine's parallel-array format.

    def to_engine_format(rows, include_rain_probability):

        result = {

            "date": [row["date"] for row in rows],

            "et0_mm": [row["et0_mm"] for row in rows],

            "rain_mm": [row["rain_mm"] for row in rows],

            "tmax_c": [row["tmax_c"] for row in rows]

        }

        if include_rain_probability:

            result["rain_prob"] = [

                row["rain_prob"] for row in rows

            ]

        return result

    observed = to_engine_format(

        observed_rows,

        include_rain_probability=False

    )

    forecast = to_engine_format(

        forecast_rows,

        include_rain_probability=True

    )

    return observed, forecast

# ==================================================

# DYNAMODB HELPERS

# ==================================================

def get_state(field_pk):

    response = table.get_item(

        Key={

            "pk": field_pk,

            "sk": "STATE"

        },

        ConsistentRead=True

    )

    return response.get("Item")

def get_events(field_pk, last_processed_date, today):

    """

    Fetch all events for a field, including paginated results.

    """

    items = []

    response = table.query(

        KeyConditionExpression=(

            Key("pk").eq(field_pk)

            & Key("sk").begins_with("EVENT#")

        )

    )

    items.extend(response.get("Items", []))

    while "LastEvaluatedKey" in response:

        response = table.query(

            KeyConditionExpression=(

                Key("pk").eq(field_pk)

                & Key("sk").begins_with("EVENT#")

            ),

            ExclusiveStartKey=response["LastEvaluatedKey"]

        )

        items.extend(response.get("Items", []))

    events = []

    for item in items:

        event_date = item.get("date")

        if not event_date:

            continue

        if last_processed_date < event_date <= today.isoformat():

            events.append({

                "date": event_date,

                "type": item.get("type"),

                "level": item.get("level", "normal"),

                "mm_assumed": to_float(item.get("mm_assumed", 0))

            })

    return sorted(events, key=lambda event: event["date"])

def get_all_profiles():

    """

    Retrieve all PROFILE items, following DynamoDB pagination.

    """

    profiles = []

    response = table.scan(

        FilterExpression=Attr("sk").eq("PROFILE")

    )

    profiles.extend(response.get("Items", []))

    while "LastEvaluatedKey" in response:

        response = table.scan(

            FilterExpression=Attr("sk").eq("PROFILE"),

            ExclusiveStartKey=response["LastEvaluatedKey"]

        )

        profiles.extend(response.get("Items", []))

    return profiles

# ==================================================

# ADVICE RENDERING

# ==================================================

def render_advice(advice, field):

    language = field.get("language", "hi")

    language = "hi" if language == "hi" else "en"

    # The current engine may return this before sowing.

    if advice.get("reason_code") == "NOT_SOWN_YET":

        if language == "hi":

            return (

                "बुवाई की तारीख अभी नहीं आई है। "

                "बुवाई के बाद सिंचाई की सलाह उपलब्ध होगी।"

            )

        return (

            "The sowing date has not arrived yet. "

            "Irrigation advice will be available after sowing."

        )

    return render(advice, language)

# ==================================================

# PROCESS ONE FIELD

# ==================================================

def process_field(profile_item, today):

    field_pk = profile_item["pk"]

    field_token = field_pk.removeprefix("FIELD#")

    state_item = get_state(field_pk)

    # Never invent missing state.

    if not state_item:

        return {

            "field_token": field_token,

            "status": "skipped",

            "reason": "STATE record not found"

        }

    field = to_float(profile_item)

    state = to_float(state_item)

    last_processed = state.get("last_processed_date")

    if not last_processed:

        return {

            "field_token": field_token,

            "status": "skipped",

            "reason": "last_processed_date missing from STATE"

        }

    last_processed_date = date.fromisoformat(last_processed)

    # The engine catches up through yesterday and generates today's advice.

    # Skip if today's advice already matches the current profile. If the

    # sowing date changed after the advice was generated, recalculate it.

    today_key = f"DAY#{today.isoformat()}"

    today_item_response = table.get_item(

        Key={"pk": field_pk, "sk": today_key},

        ConsistentRead=True

    )

    today_item = today_item_response.get("Item", {})

    today_advice = today_item.get("advice", {})

    today_advice_sowing_date = today_advice.get("sowing_date")

    current_sowing_date = field.get("sowing_date")



    if last_processed_date >= today:

        return {

            "field_token": field_token,

            "status": "skipped",

            "reason": "Already processed through today"

        }



    if (last_processed_date >= today - timedelta(days=1)

            and today_item

            and today_advice_sowing_date == current_sowing_date):

        return {

            "field_token": field_token,

            "status": "skipped",

            "reason": "Today's advice already matches the current profile"

        }

    latitude = field.get("latitude")

    longitude = field.get("longitude")

    if latitude is None or longitude is None:

        return {

            "field_token": field_token,

            "status": "error",

            "reason": "Latitude or longitude missing from PROFILE"

        }

    first_needed_date = last_processed_date + timedelta(days=1)

    observed, forecast = weather_rows(

        latitude,

        longitude,

        today,

        first_needed_date

    )

    events = get_events(

        field_pk,

        last_processed,

        today

    )

    # Preserve profile data while providing state to the engine.

    engine_field = dict(field)

    engine_field.update(state)

    try:

        result = advance_field(

            engine_field,

            state,

            observed,

            forecast,

            events,

            today.isoformat()

        )

    except MissingWeather as exc:

        return {

            "field_token": field_token,

            "status": "skipped",

            "reason": f"Weather data unavailable: {str(exc)}"

        }

    # Validate the expected result structure.

    if not isinstance(result, dict):

        raise TypeError(

            "advance_field must return a dictionary; "

            f"received {type(result).__name__}"

        )

    new_state = result["state"]

    advice = result["advice"]

    if not isinstance(advice, dict):

        raise TypeError(

            "Expected result['advice'] to be a dictionary; "

            f"received {type(advice).__name__}"

        )

    advice_text = render_advice(advice, field)

    advice_date = advice.get("date", today.isoformat())

    day_item = {

        "pk": field_pk,

        "sk": f"DAY#{advice_date}",

        "date": advice_date,

        "advice": to_dynamodb(to_float(advice)),

        "advice_text": advice_text,

        "language": field.get("language", "hi"),

        "created_at": datetime.now(TIMEZONE).isoformat()

    }

    # Create today's record if absent. If it already exists, replace it only

    # when it was generated using a different sowing date (stale profile data).

    day_created = False

    day_record_updated = False

    try:

        table.put_item(

            Item=day_item,

            ConditionExpression=(

                "attribute_not_exists(pk) "

                "AND attribute_not_exists(sk)"

            )

        )

        day_created = True

    except ClientError as exc:

        error_code = exc.response.get("Error", {}).get("Code")

        if error_code != "ConditionalCheckFailedException":

            raise

        existing_response = table.get_item(

            Key={"pk": field_pk, "sk": f"DAY#{advice_date}"},

            ConsistentRead=True

        )

        existing_item = existing_response.get("Item", {})

        existing_advice = existing_item.get("advice", {})

        existing_sowing_date = existing_advice.get("sowing_date")

        current_sowing_date = field.get("sowing_date")

        if (current_sowing_date is not None

                and existing_sowing_date != current_sowing_date):

            table.put_item(Item=day_item)

            day_record_updated = True

    # Update the saved state.

    new_state_item = {

        "pk": field_pk,

        "sk": "STATE"

    }

    new_state_item.update(to_float(new_state))

    new_state_item["version"] = int(state.get("version", 0)) + 1

    table.put_item(

        Item=to_dynamodb(new_state_item)

    )

    return {

        "field_token": field_token,

        "status": "processed",

        "date": advice_date,

        "reason_code": advice.get("reason_code"),

        "day_record_created": day_created,

        "day_record_updated": day_record_updated,

        "advice_text": advice_text

    }

# ==================================================

# LAMBDA ENTRY POINT

# ==================================================

def lambda_handler(event, context):

    today = today_local()

    results = []

    processed = 0

    skipped = 0

    errors = 0

    try:

        profiles = get_all_profiles()

        for profile in profiles:

            try:

                result = process_field(profile, today)

                results.append(result)

                if result["status"] == "processed":

                    processed += 1

                elif result["status"] == "skipped":

                    skipped += 1

                else:

                    errors += 1

            except Exception as exc:

                field_pk = profile.get("pk", "")

                field_token = field_pk.removeprefix("FIELD#")

                print(

                    f"Daily processing failed for {field_pk}: "

                    f"{type(exc).__name__}: {str(exc)}"

                )

                results.append({

                    "field_token": field_token,

                    "status": "error",

                    "reason": f"{type(exc).__name__}: {str(exc)}"

                })

                errors += 1

        # Log the complete processing summary for CloudWatch diagnostics.
        print(json.dumps({
            "date": today.isoformat(),
            "fields_found": len(profiles),
            "fields_processed": processed,
            "fields_skipped": skipped,
            "fields_with_errors": errors,
            "results": results
        }, default=json_default))

        return json_response(200, {
            "date": today.isoformat(),

            "fields_found": len(profiles),

            "fields_processed": processed,

            "fields_skipped": skipped,

            "fields_with_errors": errors,

            "results": results

        })

    except Exception as exc:

        print(

            f"Daily engine failed: "

            f"{type(exc).__name__}: {str(exc)}"

        )

        return json_response(500, {

            "error": "Daily engine failed",

            "details": f"{type(exc).__name__}: {str(exc)}"

        })
