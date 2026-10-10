import json
import runpy
import tempfile
import unittest
from pathlib import Path

from w3af.core.controllers.ci.circleci import trigger_w3af_api_build as trigger
from w3af.core.controllers.ci.tests.real_state import (
    environment_variable,
    file_content,
)
from w3af.core.controllers.tests.local_http_server import LocalHTTPServer, Reply


def circleci_server():
    return LocalHTTPServer(lambda method, path: Reply(200, "{}"))


class TestTriggerBuild(unittest.TestCase):
    def test_posts_the_docker_tag_to_the_project_endpoint(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tag_file = Path(tmp_dir) / "tag.txt"
            tag_file.write_text("registry-tag-42")

            with circleci_server() as server:
                response = trigger.trigger_build(
                    server.url("").rstrip("/"), "master", "secret", str(tag_file)
                )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                server.requested_paths,
                [trigger.TRIGGER_PATH % ("master", "secret")],
            )
            self.assertEqual(
                json.loads(response.request.body),
                {"build_parameters": {"W3AF_REGISTRY_TAG": "registry-tag-42"}},
            )
            self.assertEqual(
                response.request.headers["Content-Type"], "application/json"
            )

    def test_missing_tag_file_raises(self):
        with (
            tempfile.TemporaryDirectory() as tmp_dir,
            self.assertRaises(FileNotFoundError),
        ):
            trigger.trigger_build(
                "http://127.0.0.1:1", "master", "t", str(Path(tmp_dir) / "no")
            )

    def test_script_entry_point_reads_environment(self):
        with (
            circleci_server() as server,
            file_content(trigger.DOCKER_TAG_FILE, "tag-from-script"),
            environment_variable("CIRCLECI_URL", server.url("").rstrip("/")),
            environment_variable("CIRCLE_BRANCH", "develop"),
            environment_variable("W3AF_API_DOCKER_TOKEN", "tok"),
        ):
            runpy.run_path(trigger.__file__, run_name="__main__")

        self.assertEqual(
            server.requested_paths, [trigger.TRIGGER_PATH % ("develop", "tok")]
        )
