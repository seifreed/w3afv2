#!/usr/bin/env python

import json
import os
import tempfile
from pathlib import Path

import requests

DOCKER_TAG_FILE = os.path.join(tempfile.gettempdir(), "new-w3af-docker-tag.txt")
BUILD_TRIGGER_TIMEOUT = 30
DEFAULT_CIRCLECI_URL = "https://circleci.com"
TRIGGER_PATH = "/api/v1/project/andresriancho/w3af-api-docker/tree/%s?circle-token=%s"


def trigger_build(circleci_url, branch, token, docker_tag_file):
    latest_w3af_tag = Path(docker_tag_file).read_text()
    payload = {"build_parameters": {"W3AF_REGISTRY_TAG": latest_w3af_tag}}

    return requests.post(
        circleci_url + TRIGGER_PATH % (branch, token),
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload),
        timeout=BUILD_TRIGGER_TIMEOUT,
    )


if __name__ == "__main__":
    trigger_build(
        os.environ.get("CIRCLECI_URL", DEFAULT_CIRCLECI_URL),
        os.environ.get("CIRCLE_BRANCH"),
        os.environ.get("W3AF_API_DOCKER_TOKEN"),
        DOCKER_TAG_FILE,
    )
