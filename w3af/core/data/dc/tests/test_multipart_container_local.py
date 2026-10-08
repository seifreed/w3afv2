import unittest

from w3af.core.data.dc.headers import Headers
from w3af.core.data.dc.multipart_container import MultipartContainer


class TestMultipartContainerLocal(unittest.TestCase):
    def test_reads_text_fields_and_file_parts(self):
        body = (
            '--xyz\r\nContent-Disposition: form-data; name="text"\r\n\r\n'
            "hello\r\n"
            '--xyz\r\nContent-Disposition: form-data; name="upload"; '
            'filename="a.txt"\r\nContent-Type: text/plain\r\n\r\n'
            "file data\r\n--xyz--\r\n"
        )
        headers = Headers([("Content-Type", "multipart/form-data; boundary=xyz")])

        container = MultipartContainer.from_postdata(headers, body)

        self.assertEqual(container["text"], ["hello"])
        self.assertEqual(container["upload"][0], "file data")
        self.assertEqual(container.get_file_name("upload"), "a.txt")

    def test_rejects_non_multipart_body(self):
        headers = Headers([("Content-Type", "multipart/form-data; boundary=xyz")])

        with self.assertRaisesRegex(ValueError, "Failed to create"):
            MultipartContainer.from_postdata(headers, "not multipart")
