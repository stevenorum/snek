import http.cookies
import json
import os
import urllib.parse
import traceback
from functools import update_wrapper

def qsp(event):
    if not event:
        return None
    return event.get("queryStringParameters") if event.get("queryStringParameters") else {}

def base_path(event):
    if not event:
        return ""
    event_path = event.get("requestContext",{}).get("path","").rstrip("/")
    if event.get("pathParameters") and event["pathParameters"].get("proxy"):
        proxy = event["pathParameters"]["proxy"].rstrip("/")
        event_path = event_path[:-1*len(proxy)].rstrip("/")
    return event_path

def page_path(event):
    if event.get("pathParameters") and event["pathParameters"].get("proxy"):
        return "/" + event["pathParameters"]["proxy"].strip("/")
    else:
        return "/"

def domain(event, prefix="https://"):
    if not event:
        return None
    return (prefix if prefix else "") + event["headers"]["Host"]

def base_url(event, prefix="https://"):
    if not event:
        return None
    return domain(event, prefix=prefix) + base_path(event)

def static_path(event):
    if "STATIC_BUCKET" in os.environ and "STATIC_PATH" in os.environ:
        return "https://s3.amazonaws.com/{STATIC_BUCKET}/{STATIC_PATH}".format(**os.environ)
    if not event:
        return None
    return base_path(event)
