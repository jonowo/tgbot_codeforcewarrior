# tgbot_codeforcewarrior

## Installation
Write more later

Windows:
```cmd
mklink /J .\cf_verification\codeforces .\tgbot\codeforces
mklink /J .\cf_update\codeforces .\tgbot\codeforces
```
or equivalent on other OS.

### tgbot
```cmd
gcloud app deploy
```

### cf_verification
```cmd
gcloud functions deploy cf_verification --trigger-http --allow-unauthenticated --region asia-northeast1 --memory 256MB --runtime python39
```

### decline_join_request
```cmd
gcloud functions deploy decline_join_request --trigger-http --allow-unauthenticated --region asia-northeast1 --memory 128MB --runtime python39
```

### cf_update
Deploy on an AWS EC2 instance with an Elastic IP and nginx configured.
<br>
Create a DynamoDB table `cf-status` with string `handle` as partition key.
<br>
Create an AWS IAM user and grant DynamoDB edit rights.

```bash
pip install awscli
aws configure
pip install -r requirements.txt
python main.py
```

## Roadmap
- clist.by integration (non-cf contest notification)
- Help eep spend more money
