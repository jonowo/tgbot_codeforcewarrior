import json
import logging
import math
import random
import traceback
from datetime import datetime, timedelta
from typing import Any, Optional

import flask

from clist import ClistAPI
from codeforces import CodeforcesAPI, CodeforcesError, Problem
from common import config, db, get_handle, make_tg_api_request, schedule_task, session

app = flask.Flask(__name__)
cf_client = CodeforcesAPI()
clist_client = ClistAPI(config["CLIST_API_KEY"])


def select(tags: set[str], rating: Optional[list[int]]) -> Optional[Problem]:
    filtered_problems = cf_client.get_problems()
    if "*special" not in tags:
        filtered_problems = [p for p in filtered_problems if "*special" not in p.tags]
    if tags:
        filtered_problems = [p for p in filtered_problems if tags <= set(p.tags)]  # Subset
    if rating:
        filtered_problems = [
            p for p in filtered_problems
            if p.rating and rating[0] <= p.rating <= rating[1]
        ]

    if filtered_problems := list(filtered_problems):
        return random.choice(filtered_problems)


class TGMessageDigester:
    def __init__(self, data):
        self.data = data
        self.response: Optional[dict[str, Any]] = None  # response objects for other endpoints
        self.text_response: Optional[str] = None  # reply text in the same chat
        self.disable_web_page_preview = False

        try:
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
                    self.command(command, splits[1].strip(), user=user)
                elif "new_chat_member" in message:
                    new_chat_member = message["new_chat_member"]
                    if new_chat_member["is_bot"] == False:
                        self.new_member_join(new_chat_member)
            elif "chat_join_request" in data:
                self.chat_join_request(data["chat_join_request"])
        except CodeforcesError as e:
            if str(e) == "Codeforces is temporarily unavailable.":
                self.text_response = "Codeforces is temporarily unavailable."
            else:
                raise e from None

    def command(self, cmd, content, user=None):
        if cmd == "/help":
            self.text_response = (
                "Commands:\n"
                "    /help - Hi\n"
                "    /sign_on - Confirm your identity as a codeforces user\n"
                "    /stalk - Show codeforces profile\n"
                "    /select - Random codeforces problem\n"
                "        Parameters:\n"
                "            tags: csv form of tags\n"
                "            rating: rating range\n"
                "        Example usage:\n"
                "            /select rating=1800-2000\n"
                "            /select tags=math,dp\n"
                "            /select tags=fft|rating=2400\n"
                "    /tags - Show available tags\n"
                "    /contests - Show upcoming contests\n"
                "    /delta - Check predicted/official rating changes\n\n"
                "If you are willing to contribute, please submit a PR "
                "<a href='https://github.com/eepnt/tgbot_codeforcewarrior'>here</a>."
            )
            self.disable_web_page_preview = True
        elif cmd in ("/group_admin", "/group_girlgod"):
            self.response = {
                "method": "sendSticker",
                "chat_id": self.data["message"]["chat"]["id"],
                "sticker": "CAACAgUAAxkBAAEJajlisHTO24Hg08vl_4yyrtoqifSYTgACGQcAArcy0VcwPcCmXDt1AygE"
            }
        elif cmd == "/tags":
            self.text_response = "Tags: " + ", ".join(cf_client.get_available_tags())
        elif cmd == "/select":
            tags = set()
            rating = None
            r_suggested = False
            try:
                splits = [s.strip() for s in content.split('|') if s and not s.isspace()]
                for entry in splits:
                    mini_splits = entry.split('=', maxsplit=1)
                    assert len(mini_splits) == 2
                    if mini_splits[0] == "tags":
                        micro_splits = mini_splits[1].split(',')
                        micro_splits = [s.strip() for s in micro_splits if s and not s.isspace()]
                        tags |= set(micro_splits)
                    elif mini_splits[0] == "rating":
                        rating = [int(r) for r in mini_splits[1].split('-', maxsplit=1)]
                        if len(rating) == 1:
                            rating *= 2  # [r] -> [r, r]
                    else:
                        raise ValueError
            except (ValueError, AssertionError):
                self.text_response = "Your query is invalid"
            else:
                if not rating and (handle := get_handle(user["id"])):
                    r_suggested = True
                    cf_user = cf_client.get_user(handle)
                    if cf_user.rating:
                        r_min = max(math.ceil(cf_user.rating / 100) * 100, 800)
                    else:
                        r_min = 800
                    rating = [r_min, r_min + 200]

                problem = select(tags, rating)
                if not problem and r_suggested:
                    problem = select(tags, rating := None)

                if problem:
                    self.text_response = str(problem)
                else:
                    self.text_response = f"no problem match search criteria {tags} {rating}"
        elif cmd in ("/sign_on", "/signon", "/sign_in", "/signin"):
            if user is None:
                logging.error("unexpected response")
                return

            if content == "":
                self.text_response = (
                    "請申請帳號: https://codeforces.com/register\n"
                    "並在此輸入 <code>/sign_on your_codeforces_username</code>"
                )
            elif content == "tourist":
                self.text_response = "咪扮"
            else:
                try:
                    cf_user = cf_client.get_user(content)
                except CodeforcesError as e:
                    if str(e) == "Not found":
                        self.text_response = "This codeforces user cannot be found"
                    else:
                        raise e from None
                else:
                    # Check for cf handle collision
                    query = db.collection("cfbot_handle").where("handle", "==", cf_user.handle)
                    for doc in query.stream():
                        if doc.id == str(user["id"]):
                            self.text_response = "你已登記此 handle"
                        else:
                            self.text_response = (
                                "已有成員已登記此 handle\n"
                                "如果你確實持有這 codeforces 帳號，請聯絡 @jowonowo"
                            )
                        return

                    problem = select(set(), rating=[3000, 3500])
                    doc_ref = db.collection("cfbot_verification").document(str(user["id"]))
                    doc_ref.set({
                        "handle": cf_user.handle,
                        "problem_id": problem.id,
                        "chat_id": self.data["message"]["chat"]["id"],
                        "message_id": self.data["message"]["message_id"],
                        "count": 0
                    })

                    schedule_task("cf_verification", user["id"], datetime.utcnow() + timedelta(seconds=30))

                    self.text_response = (
                        f"請在十分鐘內到 {problem.linked_name} 提交任何程式作身份驗證\n"
                        "你可以忽略題目要求並提交錯誤的程式\n"
                        "我在提交後半分鐘內會確認你的身份"
                    )
        elif cmd == "/stalk":
            if "reply_to_message" in self.data["message"]:
                user_id = self.data["message"]["reply_to_message"]["from"]["id"]
            else:
                user_id = user["id"]
            if handle := get_handle(user_id):
                cf_user = cf_client.get_user(handle)
                self.text_response = str(cf_user)
            else:
                self.text_response = "Not yet use /sign_on"
        elif cmd == "/contests":
            contests = clist_client.get_upcoming_contests()
            self.text_response = "\n\n".join([str(c) for c in contests])
            self.disable_web_page_preview = True
        elif cmd == "/delta":
            chat_id = self.data["message"]["chat"]["id"]
            if chat_id == config["CHAT_ID"] or get_handle(user["id"]):
                session.post(
                    f"{config['CF_UPDATE_URL']}/delta",
                    json={"chat_id": chat_id},
                    headers={"X-Auth-Token": config["SECRET"]},
                    timeout=5
                )
            else:
                self.text_response = "Please use this command inside the group."

    def new_member_join(self, user):
        if not user["is_bot"]:
            self.text_response = "妳好"

    def chat_join_request(self, chat_join_request):
        user_id = chat_join_request["from"]["id"]
        if get_handle(user_id):
            self.response = {
                "method": "approveChatJoinRequest",
                "chat_id": config["CHAT_ID"],
                "user_id": user_id
            }
        else:
            self.response = {
                "method": "sendMessage",
                "chat_id": user_id,
                "text": (
                    "妳好，進入本群需持有 codeforces 帳號\n"
                    "請申請帳號: https://codeforces.com/register\n"
                    "並在此輸入 <code>/sign_on your_codeforces_username</code>"
                ),
                "parse_mode": "HTML"
            }
            schedule_task("decline_join_request", user_id, datetime.utcnow() + timedelta(seconds=30 * 60))

    def response_output(self):
        if self.text_response and "message" in self.data:
            return {
                "method": "sendMessage",
                "chat_id": self.data["message"]["chat"]["id"],
                'text': self.text_response,
                "parse_mode": "HTML",
                "disable_web_page_preview": str(self.disable_web_page_preview).lower()
            }
        return self.response


@app.route('/', methods=["POST"])
def hello():
    try:
        data = flask.request.get_json()
        logging.info(data)
        response = TGMessageDigester(data).response_output()
        logging.info(response)
        if response:
            return flask.jsonify(response)
    except Exception as e:
        logging.error(''.join(traceback.format_exception(type(e), e, e.__traceback__)))
    return ""


@app.before_first_request
def startup():
    resp = make_tg_api_request("setMyCommands", params={
        "commands": json.dumps([
            {"command": "help", "description": "See help message"},
            {"command": "sign_on", "description": "Verify your codeforces handle"},
            {"command": "stalk", "description": "Show codeforces profile"},
            {"command": "select", "description": "Get a problem"},
            {"command": "tags", "description": "List problem tags"},
            {"command": "contests", "description": "See upcoming contests"},
            {"command": "delta", "description": "Check rating changes"}
        ])
    })
    resp.raise_for_status()
    logging.info(f"setMyCommands: {resp.text}")
