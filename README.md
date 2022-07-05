# tgbot_codeforcewarrior

## Installation
Create `tgbot/config.json` with the following format:
```json
{
  "TOKEN": "",
  "SECRET": "",
  "CLIST_API_KEY": "",
  "PROJECT_ID": "",
  "FUNCTIONS_URL": "https://xxxxxxxxxxx.cloudfunctions.net",
  "CF_UPDATE_URL": "",
  "CHAT_ID": -100000000000
}
```

- TOKEN: Telegram bot token
- SECRET: Generate using `python -c "import secrets; print(secrets.token_hex(10))"`
- CLIST_API_KEY: Create a clist.by account and obtain it [here](https://clist.by/api/v2/doc/)
- PROJECT_ID: Project ID on Google Cloud Platform (GCP)
- FUNCTIONS_URL: URL of the functions deployed on GCP
- CF_UPDATE_URL: URL of where `cf_update` is deployed
- CHAT_ID: Telegram group ID

Using Windows cmd, create hard links and directory junctions:
```cmd
mklink /h .\cf_update\config.json .\gcp\config.json
mklink /j .\cf_update\codeforces .\gcp\codeforces
mklink /j .\cf_update\clist .\gcp\clist
```

or equivalent on other OS.

Set up webhook for Telegram bot.

## Deployment
### tgbot
```bash
cd gcp
gcloud app deploy
```

### cf_verification
```bash
cd gcp
gcloud functions deploy cf_verification --trigger-http --allow-unauthenticated --region asia-northeast1 --memory 256MB --runtime python39
```

### decline_join_request
```bash
cd gcp
gcloud functions deploy decline_join_request --trigger-http --allow-unauthenticated --region asia-northeast1 --memory 256MB --runtime python39
```

### cf_update
Deploy on any web server.

```bash
cd cf_update
pip install -r requirements.txt
python main.py
```
