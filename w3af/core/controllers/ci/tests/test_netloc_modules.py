import unittest

from w3af.core.controllers.ci import moth, php_moth, sqlmap_testenv, w3af_moth, wavsep
from w3af.core.controllers.ci.tests.real_state import file_content


class TestMoth(unittest.TestCase):
    def test_falls_back_to_defaults_when_address_files_are_missing(self):
        with (
            file_content(moth.HTTP_ADDRESS_FILE, None),
            file_content(moth.HTTPS_ADDRESS_FILE, None),
        ):
            self.assertEqual(
                moth.whereis_moth(),
                {"http": moth.DEFAULT_MOTH, "https": moth.DEFAULT_MOTHS},
            )

    def test_reads_addresses_written_by_the_ci_runner(self):
        with (
            file_content(moth.HTTP_ADDRESS_FILE, "127.0.0.1:8083\n"),
            file_content(moth.HTTPS_ADDRESS_FILE, "127.0.0.1:8341\n"),
        ):
            self.assertEqual(
                moth.whereis_moth(),
                {"http": "127.0.0.1:8083", "https": "127.0.0.1:8341"},
            )

    def test_empty_address_file_uses_default(self):
        with (
            file_content(moth.HTTP_ADDRESS_FILE, "\n"),
            file_content(moth.HTTPS_ADDRESS_FILE, ""),
        ):
            self.assertEqual(moth.whereis_moth()["http"], moth.DEFAULT_MOTH)
            self.assertEqual(moth.whereis_moth()["https"], moth.DEFAULT_MOTHS)

    def test_urls_are_built_from_the_address_files(self):
        with (
            file_content(moth.HTTP_ADDRESS_FILE, "127.0.0.1:8083"),
            file_content(moth.HTTPS_ADDRESS_FILE, "127.0.0.1:8341"),
        ):
            self.assertEqual(
                moth.get_moth_http("/a?b=1"), "http://127.0.0.1:8083/a?b=1"
            )
            self.assertEqual(moth.get_moth_https("/x"), "https://127.0.0.1:8341/x")

    def test_default_path_is_root(self):
        with file_content(moth.HTTP_ADDRESS_FILE, None):
            self.assertEqual(moth.get_moth_http(), f"http://{moth.DEFAULT_MOTH}/")


class TestSingleFileNetlocModules(unittest.TestCase):
    CASES = (
        (php_moth, "HTTP_PHP_MOTH", "DEFAULT_PHP_MOTH", "get_php_moth_http"),
        (
            sqlmap_testenv,
            "HTTP_SQLMAP_TESTENV",
            "DEFAULT_SQLMAP_TESTENV",
            "get_sqlmap_testenv_http",
        ),
        (wavsep, "HTTP_WAVSEP", "DEFAULT_WAVSEP", "get_wavsep_http"),
    )

    def test_missing_file_uses_default_netloc(self):
        for module, file_attr, default_attr, getter in self.CASES:
            with (
                self.subTest(module=module.__name__),
                file_content(getattr(module, file_attr), None),
            ):
                expected = f"http://{getattr(module, default_attr)}/p"
                self.assertEqual(getattr(module, getter)("/p"), expected)

    def test_file_netloc_is_used_and_stripped(self):
        for module, file_attr, _, getter in self.CASES:
            with (
                self.subTest(module=module.__name__),
                file_content(getattr(module, file_attr), "10.0.0.5:9000\n"),
            ):
                self.assertEqual(getattr(module, getter)(), "http://10.0.0.5:9000/")


class TestW3afMoth(unittest.TestCase):
    def test_url_points_to_the_docker_moth_host(self):
        self.assertEqual(w3af_moth.get_w3af_moth_http("/x"), "http://moth:9008/x")
        self.assertEqual(w3af_moth.get_w3af_moth_http(), "http://moth:9008/")
