# tgbot_codeforcewarrior

## Installation
Create `tgbot/config.json` with the following format:
```json
{
  "TOKEN": "",
  "SECRET": "",
  "CLIST_API_KEY": "",
  "FUNCTIONS_URL": "https://xxxxxxxxxxx.cloudfunctions.net",
  "CF_UPDATE_URL": "",
  "CHAT_ID": -100000000000
}
```

- TOKEN: Telegram bot token
- SECRET: Generate using `python -c "import secrets; print(secrets.token_hex(10))"`
- CLIST_API_KEY: Create a clist.by account and obtain it [here](https://clist.by/api/v2/doc/)
- FUNCTIONS_URL: URL of the functions deployed on GCP
- CF_UPDATE_URL: URL of where `cf_update` is deployed
- CHAT_ID: Telegram group ID

Set up webhook for Telegram bot.

## Deployment
### tgbot
```bash
gcloud app deploy
```

### cf_verification
```bash
gcloud functions deploy cf_verification --trigger-http --allow-unauthenticated --region asia-northeast1 --memory 256MB --runtime python39
```

### decline_join_request
```bash
gcloud functions deploy decline_join_request --trigger-http --allow-unauthenticated --region asia-northeast1 --memory 256MB --runtime python39
```

### cf_update
Deploy on any *nix web server. (gunicorn does not work on Windows)

```bash
pip install -r requirements.txt
gunicorn tgbot.cf_update:create_app --bind localhost:3000 --worker-class aiohttp.GunicornWebWorker
```
