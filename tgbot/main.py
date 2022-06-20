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

# load cloud task config
task_client = tasks_v2.CloudTasksClient()
task_parent = task_client.queue_path("tgbot-340618", "asia-northeast1", "cfbot-userdeletion")

# load question set
problems = requests.get("https://codeforces.com/api/problemset.problems").json()["result"]["problems"]
available_tags = functools.reduce(lambda a, b: a | set(b["tags"]), problems, set())

app = flask.Flask(__name__)

def select(tags, rating):
    logging.info({
        "tags": list(tags),
        "rating": rating,
    })
    filtered_problems = problems
    if len(tags) > 0:
        filtered_problems = filter(
            lambda problem: tags.issubset(set(problem["tags"])), 
            filtered_problems
        )
    if rating is not None:
        filtered_problems = filter(
            lambda problem: "rating" in problem.keys() and int(rating[0]) <= problem["rating"] and problem["rating"] <= int(rating[1]), 
            filtered_problems
        )
    filtered_problems = list(filtered_problems)
    if len(filtered_problems) > 0:
        return random.choice(filtered_problems)
    else:
        return None

class tgmsg_digester():
    def __init__(self, data):
        self.data = data
        self.response = None
        if "message" in data:
            message = data["message"]
            if "text" in message:
                text = message["text"]
                splits = text.split(' ', 1)
                command = splits[0].replace("@codeforcewarrior_bot", "")
                if len(splits) == 1:
                    splits.append("")
                user = data["message"]["from"]
                if user["is_bot"]:
                    user = None
                self.command(command, splits[1], user=user)
            elif "new_chat_member" in message:
                new_chat_member = message["new_chat_member"]
                if new_chat_member["is_bot"] == False:
                    self.new_member_join(new_chat_member)

    def command(self, cmd, content, user=None):
        if cmd == "/help":
            self.response = "command: \n" + \
                "    /help - thats why you see me talking now \n" + \
                "    /select - random question from codeforces \n" + \
                "    /tags - show available tags \n" + \
                " \n" + \
                "arguments: \n" + \
                "    tags=data structures,dp - csv form of tags \n" + \
                "    rating=1800-2000 - rating range \n" + \
                " \n" + \
                "example usage: \n" + \
                "    /select rating=1800-2000 \n" + \
                "    /select tags=data structures,dp|rating=1800-2000 \n" + \
                "    /select@codeforcewarrior_bot tags=data structures,dp|rating=1800-2000 \n" + \
                " \n" + \
                "if you are willing to contribute, please submit merge request for adding more function in: \n" + \
                "    https://github.com/eepnt/tgbot_codeforcewarrior"
        elif cmd == "/tags":
            self.response = list(available_tags)
        elif cmd == "/select":
            tags = set()
            rating = None
            splits = content.split('|')
            while len(splits) > 0:
                entry = splits.pop(0)
                mini_splits = entry.split('=')
                if mini_splits[0] == "tags":
                    micro_splits = mini_splits[1].split(',')
                    while len(micro_splits) > 0:
                        micro_entry = micro_splits.pop()
                        if micro_entry != "":
                            tags.add(micro_entry)
                elif mini_splits[0] == "rating":
                    micro_splits = mini_splits[1].split('-')
                    rating = micro_splits
            problem = select(tags, rating)
            if problem is None:
                self.response = "no problem match search criteria {} {}".format(tags, rating)
            else:
                self.response = "{}\n".format(problem["name"]) + \
                    "tags: {}\n".format(problem["tags"]) + \
                    "rating: {}\n".format(problem["rating"] if "rating" in problem.keys() else "not rated") + \
                    "https://codeforces.com/problemset/problem/{}/{}".format(problem["contestId"], problem["index"])
        elif cmd == "/sign_on":
            if user is None:
                logging.error("unexpected response")
                return
                
            if content == "":
                self.response = "please enter codeforce username"
            else:
                response = requests.get("https://codeforces.com/api/user.info?handles={}".format(content))
                logging.info({
                    "response_code": response.status_code,
                    "response_text": response.text,
                })
                response = response.json()
                if response["status"] == "OK":
                    """
                    if response["result"][0]["lastOnlineTimeSeconds"] < int(time.time()) - 300:
                        self.response = "i suspect this is not your account? please get online before signon"
                        return
                    """
                    user_doc = db.collection('cfbot_user').document(str(user["id"]))
                    user_doc.set({
                        "tg_user": user,
                        "cf_user": response,
                    })
                    self.response = "{} successfully signed on as codeforce user {}".format(user["first_name"], response["result"][0]["handle"])
                else:
                    self.response = "codeforce user \"{}\" cannot be found or invalid".format(content)

    def new_member_join(self, user):
        if not user["is_bot"]:
            timestamp = timestamp_pb2.Timestamp()
            timestamp.FromDatetime(
                datetime.datetime.now(tz=datetime.timezone.utc) + datetime.timedelta(seconds=300)
            )
            task_client.create_task(parent=task_parent, task={
                'http_request': {
                    "url": "https://asia-northeast1-tgbot-340618.cloudfunctions.net/check_user_signon",
                    # 'http_method': tasks_v2.HttpMethod.POST,
                    'headers': {
                        "Content-type": "application/json"
                    },
                    'body': json.dumps({
                        'tg_user': user['id'],
                    }).encode('utf-8'),
                },
                'schedule_time': timestamp,
            })
            self.response = "Welcome {} \n".format(user["first_name"]) + \
                "進入本群需持有codeforce account \n" + \
                "請儘快申請帳號: https://codeforces.com/register \n" + \
                "並於此群輸入 `/sign_on {{codeforce handle (username)}}`"

    def response_output(self):
        if self.response is not None:
            return {
                "method": "sendMessage",
                "chat_id": self.data["message"]["chat"]["id"],
                'text': self.response
            }
        else:
            return None

@app.route('/', methods=["POST"])
def hello():
    try:
        data = flask.request.get_json()
        logging.info(data)
        response = tgmsg_digester(data).response_output()
        logging.info(response)
        if response != None:
            return flask.jsonify(response)
        else:
            return ""
    except Exception as e:
        import traceback
        logging.error(''.join(traceback.format_exception(type(e), e, e.__traceback__)))
        return ""

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, info=True)

