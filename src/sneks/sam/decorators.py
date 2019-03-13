import traceback
from sneks import snekjson as json
from functools import update_wrapper
from sneks.sam import ui_stuff, response_core

returns_html = ui_stuff.loader_for

def returns_json(func):
    def newfunc(event, *args, **kwargs):
        response = func(event, *args, **kwargs)
        if ui_stuff.is_response(response):
            return response
        return response_core.make_response(body=json.dumps(response, separators=(',',':')), headers = {"Content-Type": "application/json"})
    update_wrapper(newfunc, func)
    return newfunc

def register_path(chain_name, path_re, *args, **kwargs):
    def newfunc(func):
        response_core.register_path_matcher(chain_name, path_re, func, *args, **kwargs)
        return func
    return newfunc
