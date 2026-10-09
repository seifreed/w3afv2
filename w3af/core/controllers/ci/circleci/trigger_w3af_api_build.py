#!/usr/bin/env python

import json
import os
import tempfile
from pathlib import Path

import requests

DOCKER_TAG_FILE = os.path.join(tempfile.gettempdir(), "new-w3af-docker-tag.txt")
BUILD_TRIGGER_TIMEOUT = 30

if __name__ == "__main__":
    headers = {"Content-Type": "application/json"}

    url = (
        "https://circleci.com/api/v1/project/andresriancho/"
        "w3af-api-docker/tree/%s?circle-token=%s"
    )
    branch = os.environ.get("CIRCLE_BRANCH")
    token = os.environ.get("W3AF_API_DOCKER_TOKEN")

    latest_w3af_tag = Path(DOCKER_TAG_FILE).read_text()

    payload = {"build_parameters": {"W3AF_REGISTRY_TAG": latest_w3af_tag}}
    requests.post(
        url % (branch, token),
        headers=headers,
        data=json.dumps(payload),
        timeout=BUILD_TRIGGER_TIMEOUT,
    )
