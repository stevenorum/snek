import traceback
from sneks import snekjson as json
from functools import update_wrapper
from sneks.sam import ui_stuff, response_core
from sneks import snekjson

returns_html = ui_stuff.loader_for

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

def register_path(chain_name, path_re, *args, **kwargs):
    def newfunc(func):
        response_core.register_path_matcher(chain_name, path_re, func, *args, **kwargs)
        return func
    return newfunc
