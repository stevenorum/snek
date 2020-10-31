from base64 import b64encode
import boto3
from bs4 import BeautifulSoup
import copy
import json
import re
import traceback
from urllib.parse import urlencode, urlparse, parse_qs

from sneks.sam import events

TEXT_MIME_TYPES = [
    "text/plain",
    "text/css",
    "text/html",
    "application/javascript",
    "image/svg+xml",
    "application/json",
    "text/xml",
    "application/xml",
    "application/xhtml+xml",
]

def make_response(body, code=200, headers={}, base64=None, prettify_html=True):
    _headers = {"Content-Type": "text/html"}
    if isinstance(body, (list,dict)):
        body = json.dumps(body, separators=(',',':'))
        _headers = {"Content-Type": "application/json"}
    if None == base64 and isinstance(body, (bytes,bytearray)):
        ct = headers.get("Content-Type","")
        if "text" in ct or "json" in ct or "xml" in ct:
            body = body.decode("utf-8")
            base64 = False
        else:
            body = str(b64encode(body))
            base64 = True
    _headers.update(headers)
    if prettify_html and _headers.get("Content-Type") == "text/html":
        body = BeautifulSoup(body, features="html.parser").prettify()
    return {
        "body": body,
        "statusCode": code,
        "headers": _headers,
        "isBase64Encoded": base64
    }

def redirect(target_url, temporary=True, headers={}, qs={}):
    print("Redirecting to {} with additional qs {}".format(target_url, qs))
    if qs:
        parsed = urlparse(target_url)
        eqs = parse_qs(parsed.query)
        newqs = set()
        for k in eqs:
            for e in eqs[k]:
                newqs.add(urlencode({k:e}))
        for k in qs:
            newqs.add(urlencode({k:qs[k]}))
        full_qs = "&".join(list(newqs))
        target_url = parsed.netloc + parsed.path
        if parsed.scheme:
            target_url = parsed.scheme + "://" + target_url
        if parsed.params:
            target_url += ";" + parsed.params
        if full_qs:
            target_url += "?" + full_qs
        if parsed.fragment:
            target_url += "#" + parsed.fragment
    _headers = {"Location": target_url}
    _headers.update(headers)
    print("Redirect headers: {}".format(_headers))
    return make_response(
        body = "",
        code = 303 if temporary else 301,
        headers = _headers
    )

def get_bucket_function(bucket_name, bucket_prefix="", bucket_is_public=False):
    client = boto3.client('s3')
    def function(event, *args, **kwargs):
        path = events.page_path(event)
        if bucket_prefix:
            path = bucket_prefix.rstrip("/") + "/" + path.lstrip("/")
        if not path.lower().endswith("html"):
            obj = client.head_object(Bucket=bucket_name, Key=path)
            if obj.get("ContentType","") not in TEXT_MIME_TYPES:
                if bucket_is_public:
                    url = "https://s3.amazonaws.com/{bucket_name}/{path}".format(bucket_name=bucket_name, path=path)
                else:
                    # have to generate a presigned URL instead of the usual public one
                    url = client.generate_presigned_url(ClientMethod="get_object",Params={"Bucket":bucket_name, "Key":path}, ExpiresIn=3600)
                return redirect(url)
        obj = client.get_object(Bucket=bucket_name, Key=path)
        body = obj["Body"].read()
        ctype = obj.get("ContentType", "text/html")
        return make_response(body, code=200, headers={"Content-Type":ctype}, prettify_html=True)
    return function

def get_bucket_matcher(bucket_name, bucket_prefix=""):
    client = boto3.client('s3')
    def function(event, *args, **kwargs):
        path = events.page_path(event)
        if bucket_prefix:
            path = bucket_prefix.rstrip("/") + "/" + path.lstrip("/")
        try:
            obj = client.head_object(Bucket=bucket_name, Key=path)
            return True, {}
        except:
            traceback.print_exc()
            return False, {}
    return function

class EventMatcher(object):
    def __init__(self, response_function, default_kwargs={}, matcher_function=None, preprocessor_functions=[]):
        self.response_function = response_function
        self.kwargs = default_kwargs
        preprocessor_functions = preprocessor_functions if isinstance(preprocessor_functions, (list, tuple)) else [preprocessor_functions]
        self.preprocessor_functions = preprocessor_functions if preprocessor_functions else getattr(self, "preprocessor_functions", [])
        self.matcher_function = matcher_function if matcher_function else getattr(self, "matcher_function", lambda *args, **kwargs: (False,None))

    def match_event(self, event):
        resp = self.matcher_function(event)
        if len(resp) != 2 or not resp[0]:
            return None, None
        kwargs = copy.deepcopy(self.kwargs)
        kwargs.update(resp[1])
        kwargs["event"] = event if "event" not in kwargs else kwargs.get("event")
        for processor_func in self.preprocessor_functions:
            kwargs = processor_func(kwargs)
        return (self.response_function, kwargs)

    def handle_event(self, event):
        match = self.match_event(event)
        if match and match[0]:
            function = match[0]
            kwargs = match[1]
            return function(**kwargs)
        return None

class PathMatcher(EventMatcher):
    def __init__(self, regex, function, default_kwargs={}, preprocessor_functions=[]):
        super().__init__(function, default_kwargs, preprocessor_functions=preprocessor_functions)
        self.matcher = re.compile(regex)

    def matcher_function(self, event):
        path = events.page_path(event)
        response = self.matcher.match(path)
        if response:
            return (True, response.groupdict())
        return False, None

class ListMatcher(EventMatcher):
    def __init__(self, matchers):
        self.matchers = matchers

    def match_event(self, event):
        for matcher in self.matchers:
            resp = matcher.match_event(event)
            if resp[0]:
                return resp
        return None, None

class ResponseException(Exception):
    def __init__(self, response):
        self.response = response

class ApiException(ResponseException):
    def __init__(self, data={}, code=500):
        self.response = make_response(body=data, code=code)

MATCHERS = {}

def register_path_matcher(chain_name, *args, **kwargs):
    global MATCHERS
    MATCHERS[chain_name] = MATCHERS.get(chain_name, [])
    MATCHERS[chain_name].append((args, kwargs))

def get_matchers(chain_name, **kwargs):
    global MATCHERS
    matchers = []
    for link in MATCHERS.get(chain_name, []):
        _args = link[0]
        _kwargs = copy.deepcopy(kwargs)
        _kwargs.update(link[1])
        matchers.append(PathMatcher(*_args, **_kwargs))
    return matchers

def get_matchers_debug_blob():
    global MATCHERS
    mkeys = list(MATCHERS.keys())
    blobs = {}
    for chain_name in mkeys:
        blob = []
        for link in MATCHERS.get(chain_name, []):
            blob.append([str(link[0]), str(link[1])])
        blobs[chain_name] = blob
    return blobs
