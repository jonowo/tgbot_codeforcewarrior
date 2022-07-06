import json
import os

with open(os.path.join(os.path.dirname(__file__), "..", "config.json")) as f:
    config = json.load(f)

config["FUNCTIONS_URL"] = config["FUNCTIONS_URL"].rstrip("/")
config["CF_UPDATE_URL"] = config["CF_UPDATE_URL"].rstrip("/")
