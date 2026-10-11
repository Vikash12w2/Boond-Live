# Deploying the Boond backend

Region: **ap-south-1 (Mumbai)**. Stack name: `boond`. Every step below creates or changes
resources in your AWS account, so run them only when you mean to.

## 0. Tools (once, in your user account, no sudo)

```bash
# AWS CLI v2
curl -sSo /tmp/awscliv2.zip https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip
unzip -q /tmp/awscliv2.zip -d /tmp && /tmp/aws/install -i ~/.local/aws-cli -b ~/.local/bin
# AWS SAM CLI, in the backend virtualenv
backend/.venv/bin/pip install aws-sam-cli
aws --version && backend/.venv/bin/sam --version
```

## 1. Check which account you are about to use

```bash
aws sts get-caller-identity          # account ID and user/role: confirm this is the hackathon account
aws configure get region             # set to ap-south-1, or pass --region ap-south-1 below
```

## 2. Web Push keys (once)

```bash
cd backend && .venv/bin/python -m boond.vapid && cd ..
```
Store the private key in SSM (it never goes in the repo), keep the public key for step 4:
```bash
aws ssm put-parameter --region ap-south-1 --name /boond/vapid_private_key --type SecureString --value '<VAPID_PRIVATE_KEY>'
```

## 3. Bedrock model (optional: without it the engine's template text is used)

```bash
aws bedrock list-inference-profiles --region ap-south-1 \
  --query "inferenceProfileSummaries[?contains(inferenceProfileId, 'haiku') || contains(inferenceProfileId, 'nova')].inferenceProfileId"
```
Pick one (Claude Haiku via a `global.` profile, or Amazon Nova Lite via `apac.`). The first call to an
Anthropic model may ask you to submit a short use-case form in the Bedrock console. Test it:
```bash
aws bedrock-runtime converse --region ap-south-1 --model-id '<PROFILE_ID>' \
  --messages '[{"role":"user","content":[{"text":"Say OK"}]}]'
```

## 4. Build and deploy

`infra/package.sh` already builds the Lambda code for python3.13 (Linux wheels), so there is no
`sam build` step: `sam build` would look for a local `python3.13` binary, and this machine has 3.14.
`sam deploy` zips and uploads `.build/lambda` itself.
```bash
infra/package.sh
backend/.venv/bin/sam deploy --template-file infra/template.yaml --guided --region ap-south-1 --stack-name boond \
  --parameter-overrides VapidPublicKey='<VAPID_PUBLIC_KEY>' VapidContact='mailto:<a real email>' \
                        BedrockModelId='<PROFILE_ID or empty>' AllowedOrigin='*'
```
`VapidContact` must be a valid email address (`mailto:name@domain.tld`); push services reject others.
`--guided` saves your answers to `samconfig.toml`; later deploys are `infra/package.sh && sam deploy --template-file infra/template.yaml`.
The `ApiUrl` output is the dashboard's `VITE_API_BASE`.

## 5. Smoke test

```bash
API=<ApiUrl output>
curl -s "$API/config"
TOKEN=$(curl -s -X POST "$API/fields" -H 'content-type: application/json' \
  -d '{"language":"hi","latitude":30.9,"longitude":75.85,"crop":"wheat","sowing_date":"2026-11-05","soil":"loam","area_acres":1.5,"pump_type":"electric","lift_m":30,"consent":true}' \
  | python3 -c 'import json,sys;print(json.load(sys.stdin)["field_token"])')
curl -s "$API/fields/$TOKEN" | python3 -m json.tool | head -40
aws lambda invoke --region ap-south-1 --function-name <DailyFunctionName output> /tmp/daily.json && cat /tmp/daily.json
curl -s -X DELETE "$API/fields/$TOKEN" -o /dev/null -w '%{http_code}\n'   # 204
```
Check the logs in CloudWatch (`/aws/lambda/boond-ApiFunction-*`, `/aws/lambda/boond-DailyFunction-*`)
and the schedule `boond-daily` in EventBridge Scheduler (06:00, Asia/Kolkata).

## 6. Frontend

In Amplify Hosting set the environment variable `VITE_API_BASE` to the `ApiUrl` output and redeploy.
Then redeploy the stack with `AllowedOrigin='https://<your amplify domain>'` to restrict CORS.

## 7. Billing alarm (billing metrics live in us-east-1)

Enable "Receive Billing Alerts" in Billing preferences, then:
```bash
aws sns create-topic --region us-east-1 --name boond-billing
aws sns subscribe --region us-east-1 --topic-arn <topic arn> --protocol email --notification-endpoint <your email>
aws cloudwatch put-metric-alarm --region us-east-1 --alarm-name boond-billing-5usd \
  --namespace AWS/Billing --metric-name EstimatedCharges --dimensions Name=Currency,Value=USD \
  --statistic Maximum --period 21600 --evaluation-periods 1 --threshold 5 \
  --comparison-operator GreaterThanThreshold --alarm-actions <topic arn>
```

## Teardown

```bash
aws s3 rm s3://<BucketName output> --recursive
backend/.venv/bin/sam delete --region ap-south-1 --stack-name boond
aws ssm delete-parameter --region ap-south-1 --name /boond/vapid_private_key
```
