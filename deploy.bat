start "Deploy cf_verification" cmd /C "gcloud functions deploy cf_verification --trigger-http --allow-unauthenticated --region asia-northeast1 --memory 256MB --runtime python39"
start "Deploy decline_join_request" cmd /C "gcloud functions deploy decline_join_request --trigger-http --allow-unauthenticated --region asia-northeast1 --memory 256MB --runtime python39"
gcloud app deploy
