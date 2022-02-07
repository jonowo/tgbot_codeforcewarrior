import requests, json, flask, random, functools

try:
  import googleclouddebugger
  googleclouddebugger.enable(
    breakpoint_enable_canary=False
  )
except ImportError:
  pass

problems = requests.get("https://codeforces.com/api/problemset.problems").json()["result"]["problems"]
available_tags = functools.reduce(lambda a, b: a | set(b["tags"]), problems, set())

app = flask.Flask(__name__)

def select(tags, rating):
    print(json.dumps({
        "tags": list(tags),
        "rating": rating,
    }))
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
    contest_id = problem_entry["contestId"]
    index = problem_entry["index"]
    return "{}\n".format(problem_entry["name"]) + \
    "tags: {}\n".format(problem_entry["tags"]) + \
    "rating: {}\n".format(problem_entry["rating"] if "rating" in problem_entry.keys() else "not rated") + \
    "https://codeforces.com/problemset/problem/{}/{}".format(contest_id, index)

def command_match(cmd, input):
    return input == cmd or input == cmd + "@codeforcewarrior_bot"

@app.route('/', methods=["POST"])
def hello():
    try:
        data = flask.request.get_json()
        print(json.dumps(data))
        text = data["message"]["text"]
        splits = text.split(' ', 1)
        problem = None
        if command_match("/help", splits[0]):
            response = """
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

            """
        elif command_match("/tags", splits[0]):
            response = list(available_tags)
        elif command_match("/select", splits[0]):
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
                response = "no problem match search criteria {} {}".format(tags, rating)
            else:
                response = form_response(problem)
        else:
            return ""
        response = {
            "method": "sendMessage",
            "chat_id": data["message"]["chat"]["id"],
            'text': response
        }
        print(json.dumps({
            "selected_problem": problem,
            "response": response,
        }))
        return flask.jsonify(response)
    except Exception as e:
        import sys, traceback
        print(''.join(traceback.format_exception(type(e), e, e.__traceback__)), file=sys.stderr)
        return ""

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)

