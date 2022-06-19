import requests, flask, random, functools, logging, google.cloud.logging

google.cloud.logging.Client().setup_logging()

try:
  import googleclouddebugger
  googleclouddebugger.enable(
    breakpoint_enable_canary=False
  )
except ImportError:
  pass

problems = requests.get("https://codeforces.com/api/problemset.problems").json()["result"]["problems"]
available_tags = functools.reduce(lambda a, b: a | set(b["tags"]), problems, set())

newjoin_member = set()

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

def form_response(problem_entry):
    contest_id = 
    index = 
    return 

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
                self.command(command, splits[1])
            elif "new_chat_member" in message:
                new_chat_member = message["new_chat_member"]
                if new_chat_member["is_bot"] == False:
                    self.new_member_join(new_chat_member)

    def command(self, cmd, content):
        if cmd == "/help":
            self.response = """
command:
    /help - thats why you see me talking now
    /select - random question from codeforces
    /tags - show available tags

arguments:
    tags=data structures,dp - csv form of tags
    rating=1800-2000 - rating range

example usage:
    /select rating=1800-2000
    /select tags=data structures,dp|rating=1800-2000
    /select@codeforcewarrior_bot tags=data structures,dp|rating=1800-2000

if you are willing to contribute, please submit merge request for adding more function in:
    https://github.com/eepnt/tgbot_codeforcewarrior
            """
        elif cmd == "/tags":
            self.response = list(available_tags)
        elif cmd == "/select":
            tags = set()
            rating = None
            if len(splits) > 1:
                splits = splits[1].split('|')
            else:
                splits = []
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

    def new_member_join(self, user):
        self.response = "welcome {}".format(user["first_name"])

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
    app.run(host='127.0.0.1', port=8080, debug=True)

