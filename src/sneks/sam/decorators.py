import os
import traceback
import time
from sneks import snekjson as json
from functools import update_wrapper
from sneks.sam import ui_stuff, response_core
from sneks import snekjson
from sneks.sam.exceptions import HTTP404

returns_html = ui_stuff.loader_for

PAGE_CACHE = {}

def cache_page(seconds=60, keys=[]):
    def cachefunc(func):
        def newfunc(event, *args, **kwargs):
            global PAGE_CACHE
            keyvals = {k:kwargs.get(k) for k in kwargs if k in keys}
            keyvals["__funcname__"] = func.__name__
            key = snekjson.dumps(keyvals, separators=(',',':'), ignore_type_error=True, sort_keys=True)
            cached_page = PAGE_CACHE.get(key, {})
            if cached_page:
                if cached_page.get("expires",0) > time.time():
                    print("Using cached response with key '{}'".format(key))
                    return cached_page["response"]
                else:
                    print("Cached response expired for key '{}'".format(key))
            response = func(event, *args, **kwargs)
            PAGE_CACHE[key] = {"expires":time.time()+seconds, "response":response}
            return response
        update_wrapper(newfunc, func)
        return newfunc
    return cachefunc

def returns_json(func):
    def newfunc(event, *args, **kwargs):
        response = func(event, *args, **kwargs)
        if ui_stuff.is_response(response):
            return response
        return response_core.make_response(body=snekjson.dumps(response, separators=(',',':'), ignore_type_error=True), headers = {"Content-Type": "application/json"})
    update_wrapper(newfunc, func)
    return newfunc

def returns_text(func):
    def newfunc(event, *args, **kwargs):
        response = func(event, *args, **kwargs)
        if ui_stuff.is_response(response):
            return response
        return response_core.make_response(body=str(response), headers = {"Content-Type": "text/plain"})
    update_wrapper(newfunc, func)
    return newfunc

def log_function(func):
    def newfunc(*args, **kwargs):
        print("Entering function '{}'".format(func.__name__))
        try:
            return func(*args, **kwargs)
        finally:
            print("Exiting function '{}'".format(func.__name__))
    update_wrapper(newfunc, func)
    return newfunc

def register_path(chain_name, path_re, *args, **kwargs):
    def newfunc(func):
        response_core.register_path_matcher(chain_name, path_re, func, *args, **kwargs)
        return func
    return newfunc

def require_passphrase(passphrase):
    def cachefunc(func):
        def newfunc(event, *args, **kwargs):
            if not kwargs.get("passphrase") == passphrase:
                 HTTP404.throw()
            return func(event, *args, **kwargs)
        update_wrapper(newfunc, func)
        return newfunc
    return cachefunc

def add_ddb_capacity_args(func):
    def newfunc(event, *args, **kwargs):
        os.environ["DDB_READ_CAPACITY_USED"] = "0"
        os.environ["DDB_WRITE_CAPACITY_USED"] = "0"
        response = func(event, *args, **kwargs)
        if ui_stuff.is_response(response):
            return response
        elif isinstance(response, dict):
            response["_ddb_read_capacity_used"] = float(os.environ["DDB_READ_CAPACITY_USED"])
            response["_ddb_write_capacity_used"] = float(os.environ["DDB_WRITE_CAPACITY_USED"])
            response["_ddb_capacity_used"] = response["_ddb_read_capacity_used"] + response["_ddb_write_capacity_used"]
            response["_ddb_cost"] = response["_ddb_read_capacity_used"] * 0.25/1000000 + response["_ddb_write_capacity_used"] * 1.25/1000000
            print("RCUs: {}".format(os.environ["DDB_READ_CAPACITY_USED"]))
            print("WCUs: {}".format(os.environ["DDB_WRITE_CAPACITY_USED"]))
            os.environ["DDB_READ_CAPACITY_USED"] = "0"
            os.environ["DDB_WRITE_CAPACITY_USED"] = "0"
        return response
    update_wrapper(newfunc, func)
    return newfunc
