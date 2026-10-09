import os
import pprint
import sys

sys.path.append(os.getcwd())

from w3af.core.data.dc.headers import Headers
from w3af.core.data.parsers.doc.open_api import OpenAPI
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.http_response import HTTPResponse

spec_filename = sys.argv[1]

_, extension = os.path.splitext(spec_filename)

body = open(spec_filename).read()
headers = Headers(list({"Content-Type": f"application/{extension}"}.items()))
response = HTTPResponse(
    200,
    body,
    headers,
    URL(f"http://moth/swagger.{extension}"),
    URL(f"http://moth/swagger.{extension}"),
    _id=1,
)


parser = OpenAPI(response)
parser.parse()
api_calls = parser.get_api_calls()

for api_call in api_calls:
    method = api_call.get_method()
    headers = api_call.get_headers()
    data = api_call.get_data()

    uri = api_call.get_uri().url_string

    data = (method, uri, headers, data)

    pprint.pprint(data)
