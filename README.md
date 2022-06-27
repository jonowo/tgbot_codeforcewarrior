# tgbot_codeforcewarrior

## Installation
Write more later

Windows:
```cmd
mklink /J .\cf_verification\codeforces .\tgbot\codeforces
mklink /J .\cf_update\codeforces .\tgbot\codeforces
```
or equivalent on other OS.

### cf_update
Create an AWS IAM user.
```bash
pip install awscli
aws configure
```

## Roadmap
- Submission update notification
- clist.by integration (contest notification)
- Delta prediction
- Help eep spend more money
