import requests, json, flask, random, functools, logging, datetime
import google.cloud.logging
from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2
from google.cloud import firestore

google.cloud.logging.Client().setup_logging()

try:
  import googlecloudinfoger
  googlecloudinfoger.enable(
    breakpoint_enable_canary=False
  )
except ImportError:
  pass

# load firestore
db = firestore.Client(project='tgbot-340618')

# load tgbot credentials
tgbot_token = None
with open(".credentials", "r") as f:
    tgbot_token = f.read()
tg_chat_id = "-1001669733846"

def check_user_signon(request):
    try:
        data = request.get_json()
        logging.info(data)
        msg = {
            "data": data,
        }

        user_doc_ref = db.collection('cfbot_user').document(str(data["tg_user"]))
        user_doc = user_doc_ref.get()
        if not user_doc.exists:
            message = {
                "chat_id": tg_chat_id,
                "user_id": data["tg_user"],
            }
            url = "https://api.telegram.org/bot{}/banChatMember".format(tgbot_token)
            response = requests.get(url, params=message)
            logging.info({
                "action": "delete tg user",
                "request_url": url,
                "request_body": message,
                "response_code": response.status_code,
                "response_text": response.text,
            })
        return ""
    except Exception as e:
        import traceback
        logging.error(''.join(traceback.format_exception(type(e), e, e.__traceback__)))
        return ""

