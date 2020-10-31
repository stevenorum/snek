import http.cookies
import json
import os
import urllib.parse
import string
import traceback
from functools import update_wrapper
from sneks.sam import events

def listify(obj):
    if obj == None:
        return []
    if isinstance(obj, (list,tuple)):
        return obj
    return [obj]

def unlistify(obj):
    if obj == None:
        return None
    if isinstance(obj, (list,tuple)):
        if len(obj) == 0:
            return None
        elif len(obj) == 1:
            return obj[0]
    return obj

def listify_dict(d):
    keys = list(d.keys())
    new_d = dict()
    for k in keys:
        new_d[k] = listify(d[k])
    return new_d

def unlistify_dict(d):
    keys = list(d.keys())
    new_d = dict()
    for k in keys:
        new_d[k] = unlistify(d[k])
    return new_d

def dict_append(d, k, v):
    # d = listify_dict(d)
    d[k] = listify(d.get(k,[]))
    d[k].extend(listify(v))
    return d

def update_lists(d1, d2):
    # d1 = listify_dict(d1)
    # d2 = listify_dict(d2)
    for k in d2:
        d1[k] = listify(d1.get(k,[]))
        d1 = dict_append(d1, k, d2[k])
    return d1

def parse_body(body):
    if body.startswith("{"):
        try:
            return json.loads(body)
        except:
            traceback.print_exc()
    else:
        try:
            return urllib.parse.parse_qs(body)
        except:
            traceback.print_exc()
    return {}

def add_event_params(event, *args, **kwargs):
    params = {}
    event["queryStringParameters"] = event.get("queryStringParameters") if event.get("queryStringParameters") else {}
    params.update(event["queryStringParameters"])
    if event["httpMethod"] == "POST" and event.get("body"):
        body = event["body"]
        update_lists(params, parse_body(body))
    cookie_dict = {}
    try:
        cookies = http.cookies.SimpleCookie()
        cookies.load(event["headers"].get("Cookie",""))
        for k in cookies:
            morsel = cookies[k]
            cookie_dict[morsel.key] = morsel.value
    except:
        traceback.print_exc()
    params = listify_dict(params)
    params = {"kwargs":params}
    params["single_kwargs"] = unlistify_dict(params["kwargs"])
    params["cookies"] = cookie_dict
    params["path"] = {}
    params["path"]["raw"] = event["path"]
    params["path"]["base"] = events.base_path(event)
    params["path"]["page"] = events.page_path(event)
    params["path"]["full"] = "https://" + event["headers"]["Host"] + params["path"]["raw"]
    params["path"]["full_base"] = "https://" + event["headers"]["Host"] + params["path"]["base"]
    if "STATIC_BUCKET" in os.environ and "STATIC_PATH" in os.environ:
        params["path"]["static_base"] = "https://s3.amazonaws.com/{STATIC_BUCKET}/{STATIC_PATH}".format(**os.environ)
    else:
        params["path"]["static_base"] = params["path"]["base"]
    params["http"] = {}
    params["http"]["Referer"] = event.get("headers",{}).get("Referer","")
    params["http"]["Referer"] = params["http"]["Referer"] if params["http"]["Referer"] else params["path"]["full_base"]
    params["http"]["User-Agent"] = event.get("headers",{}).get("User-Agent")
    params["http"]["Method"] = event["httpMethod"]
    params["redirect"] = params["single_kwargs"].get("redirect", params["http"]["Referer"])
    params["redirect"] = params["redirect"] if params["redirect"] else params["path"]["full_base"]
    params["objects"] = {}
    event["params"] = params
    return event

def event_params_decorator(func):
    def newfunc(event, *args, **kwargs):
        event = add_event_params(event)
        return func(event, *args, **kwargs)
    update_wrapper(newfunc, func)
    return newfunc

def bitmask_string_case(s, n):
    # This function lets you get a bunch of different casing variations on a string.
    # This is necessary because API Gateway uses a dict to store the headers, so to set multiple cookies at once,
    # each one needs to use a different casing of "Set-Cookie" to avoid overwriting each other.
    s = s.lower()
    length = len([c for c in s if c in string.ascii_lowercase])
    mask = "{0:b}".format(n)
    if len(mask) > length:
        raise RuntimeError("Binary representation of mask {} is longer than string to be masked '{}'".format(n, s))
    else:
        mask = "0"*(length-len(mask)) + mask
    offset = 0
    new_s = ""
    for i in range(len(s)):
        c = s[i]
        if c not in string.ascii_lowercase:
            new_s += c
            offset += 1
        else:
            m = mask[i-offset]
            print(m)
            new_s += s[i].upper() if m=="1" else s[i].lower()
    return new_s

def get_cookie_headers(cookies):
    headers = {}
    if len(cookies) > 512:
        raise RuntimeError("Can only set up to 512 cookies in a single request due to API Gateway being janky.")
    for i in range(len(cookies)):
        headers[bitmask_string_case("set-cookie", i)] = cookies[i]
    return headers
