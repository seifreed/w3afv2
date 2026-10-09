#!/usr/bin/env python

import json
import os
from pathlib import Path

import requests

if __name__ == "__main__":
    headers = {"Content-Type": "application/json"}

    url = (
        "https://circleci.com/api/v1/project/andresriancho/"
        "w3af-api-docker/tree/%s?circle-token=%s"
    )
    branch = os.environ.get("CIRCLE_BRANCH")
    token = os.environ.get("W3AF_API_DOCKER_TOKEN")

    latest_w3af_tag = Path("/tmp/new-w3af-docker-tag.txt").read_text()

    data = {"build_parameters": {"W3AF_REGISTRY_TAG": latest_w3af_tag}}
    data = json.dumps(data)
    requests.post(url % (branch, token), headers=headers, data=data)
