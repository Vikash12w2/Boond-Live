# Boond Live — AWS Implementation Backup

This directory preserves the AWS source code and configuration used by the Boond Live application.

## Directory Structure

- `handlers/` — Standalone AWS Lambda handlers.
- `layer/python/engine/` — Engine files from the deployed `boond-engine` Lambda layer.
- `sam-functions/api/boond/` — Application modules bundled with the SAM API Lambda function.
- `sam-functions/daily/boond/` — Application modules bundled with the SAM daily Lambda function.
- `sam-functions/daily/engine/` — Engine files bundled with the SAM daily function.
- `configuration/` — Exported AWS resource settings, Lambda configurations, API Gateway routes and integrations, scheduler settings, and IAM policy documents.

## AWS Environment

- **Region:** Asia Pacific (Sydney), `ap-southeast-2`
- **Amplify application:** `Boond-Live`
- **Amplify production branch:** `frontend-dashboard`
- **Primary DynamoDB table:** `boond`
- **Additional DynamoDB table:** `boond-Table-185DEERJ6MCUZ`
- **Lambda layer:** `boond-engine`, version 1
- **Daily processing function:** `boond-daily-engine`
- **Daily schedule:** `boond-daily-schedule`, enabled at 6:00 AM IST
- **Text-to-speech:** Amazon Polly
- **Audio storage:** Amazon S3
- **Weather data:** Retrieved through the weather Lambda handler

## API Gateway

### `boond-tts-api`

Base URL:

`https://xhp7rzeew0.execute-api.ap-southeast-2.amazonaws.com`

| Method | Route | Purpose |
|---|---|---|
| POST | `/fields` | Register a field |
| GET | `/fields/{token}` | Retrieve field information |
| PATCH | `/fields/{token}` | Update field information |
| DELETE | `/fields/{token}` | Delete field information |
| POST | `/fields/{token}/events` | Record a field event |
| POST | `/fields/{token}/push` | Save push-notification subscription data |
| GET | `/fields/{token}/weather` | Retrieve weather information |
| POST | `/tts` | Generate speech and return an audio URL |

### `boond`

A separate HTTP API connected to `boond-ApiFunction-vt5eMr3kMeg0`.

Its routes and integrations are documented in:

- `configuration/boond-routes.json`
- `configuration/boond-integrations.json`

## AWS Lambda Functions

The standalone handlers are stored in `handlers/`:

- `boond-field` — Field registration.
- `boond-get-field` — Retrieve field information.
- `boond-update-field` — Update field information.
- `boond-delete-field` — Delete field information.
- `boond-field-event` — Record field events.
- `boond-save-push` — Save push-notification subscription data.
- `boond-weather` — Retrieve weather information.
- `boond-tts` — Generate text-to-speech audio.
- `boond-daily-engine` — Run daily field processing.

The `sam-functions/` directory separately preserves the application modules and engine bundled with the two SAM Lambda functions.

## Data Storage

The primary `boond` DynamoDB table uses `pk` and `sk` string keys.

Field records use partition keys in the form `FIELD#<token>` and sort keys such as:

- `PROFILE`
- `STATE`
- `DAY#<date>`
- Event records

The application also uses Amazon S3 to store generated audio.

The configuration backup records resource settings and schemas; it does not contain exported live DynamoDB records or S3 audio objects.

## Daily Processing

Amazon EventBridge Scheduler invokes `boond-daily-engine` every day at 6:00 AM India time.

- **Schedule expression:** `cron(0 6 * * ? *)`
- **Timezone:** `Asia/Calcutta`
- **Target:** `boond-daily-engine`
- **Maximum retry attempts:** 3
- **Maximum event age:** 1 hour

The daily engine processes field data and records execution logs in Amazon CloudWatch.

The scheduler configuration is saved in `configuration/boond-daily-schedule.json`.

## Text-to-Speech and Audio

The `boond-tts` Lambda handler uses Amazon Polly to generate speech and Amazon S3 to store the resulting audio. The API returns an audio URL for the frontend to use.

## Amplify Frontend

The AWS Amplify application is named `Boond-Live`.

- **Application ID:** `d1f7juo4mqr40l`
- **Repository:** `https://github.com/Vikash12w2/Boond-Live`
- **Production branch:** `frontend-dashboard`

The exported Amplify app and branch settings are stored in `configuration/amplify-app.json` and `configuration/amplify-branches.json`.

## IAM and Resource Configuration

The `configuration/` directory contains exported metadata for:

- Lambda runtimes, handlers, execution roles, memory, timeouts, and layers.
- IAM attached policies, inline policies, and the scheduler role trust policy.
- API Gateway APIs, routes, and integrations.
- DynamoDB table schemas and TTL settings.
- S3 bucket settings.
- Amplify application and branch settings.
- EventBridge Scheduler configuration.

These files document the AWS environment. They are configuration records, not a complete automated deployment template.

## Purpose

This directory preserves the AWS Lambda source code, deployed engine files, SAM function modules, and AWS resource configuration for Boond Live. It serves as a reference for the current implementation and future maintenance.
