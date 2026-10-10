
import boto3
import json
import uuid
from botocore.config import Config

# Amazon Polly client
polly = boto3.client("polly")

# S3 client configured for presigned URLs
s3 = boto3.client(
    "s3",
    region_name="ap-southeast-2",
    config=Config(signature_version="s3v4")
)

BUCKET = "boond-audio-vikash-2026"


def lambda_handler(event, context):

    # Handle API Gateway requests and direct Lambda tests
    try:
        if "body" in event:
            body = event["body"]

            if isinstance(body, str):
                body = json.loads(body)

            if body is None:
                body = {}
        else:
            body = event

    except (json.JSONDecodeError, TypeError):
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "error": "Invalid JSON body"
            })
        }

    # Read text and language
    text = body.get("text")
    language = body.get("language", "hi")

    if not isinstance(text, str) or not text.strip():
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "error": "text is required"
            })
        }

    if language not in ("hi", "en"):
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "error": "language must be 'hi' or 'en'"
            })
        }

    # Generate speech using Amazon Polly
    try:
        response = polly.synthesize_speech(
            Text=text,
            TextType="text",
            OutputFormat="mp3",
            VoiceId="Aditi",
            LanguageCode="en-IN" if language == "en" else "hi-IN"
        )

        audio_bytes = response["AudioStream"].read()
        response["AudioStream"].close()

    except Exception:
        print("Polly speech generation failed")
        return {
            "statusCode": 502,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "error": "Could not generate audio"
            })
        }

    # Save the generated MP3 to S3
    key = f"test/{uuid.uuid4()}.mp3"

    try:
        s3.put_object(
            Bucket=BUCKET,
            Key=key,
            Body=audio_bytes,
            ContentType="audio/mpeg"
        )

        # Generate a temporary URL for the private audio file
        audio_url = s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": BUCKET,
                "Key": key
            },
            ExpiresIn=3600
        )

    except Exception:
        print("S3 upload or presigned URL generation failed")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "error": "Could not save or retrieve generated audio"
            })
        }

    # Return the audio URL to the frontend
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps({
            "message": "Audio generated successfully",
            "audio_url": audio_url,
            "language": language
        })
    }
