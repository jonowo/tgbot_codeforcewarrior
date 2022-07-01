# tgbot_codeforcewarrior

## Installation
Create `tgbot/.env` with the following format:
```
TOKEN=tg_bot_token_here
SECRET=secret_here
```

You can generate `SECRET` using
```bash
python -c "import secrets; print(secrets.token_hex(10))"
```

Using Windows cmd, create hard links and directory junctions:
```cmd
mklink /h .\cf_verification\.env .\tgbot\.env
mklink /h .\decline_join_request\.env .\tgbot\.env
mklink /h .\cf_update\.env .\tgbot\.env
mklink /j .\cf_verification\codeforces .\tgbot\codeforces
mklink /j .\cf_update\codeforces .\tgbot\codeforces
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
- Contest notification
- Help eep spend more money
