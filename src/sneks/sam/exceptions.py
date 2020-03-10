from sneks.sam.response_core import make_response, ResponseException

class HTTPException(ResponseException):
    CODE = 500
    BODY = None
    HEADERS = {}

    @classmethod
    def throw(cls, body=None, code=None, headers=None):
        body = body if body else cls.BODY
        code = code if code else cls.CODE
        headers = headers if headers else cls.HEADERS
        response = make_response(body=body, code=code, headers=headers)
        raise ResponseException(response)

class HTTPRedirect(HTTPException):
    CODE = 307
    BODY = ""

    @classmethod
    def throw(cls, target_url, body="", headers={}):
        _headers = {"Location": target_url}
        body = body if body else cls.BODY
        _headers.update(headers)
        response = make_response(body=body, code=cls.CODE, headers=_headers)
        raise ResponseException(response)

class HTTPTemporaryRedirect(HTTPRedirect):
    pass

class HTTPPermanentRedirect(HTTPRedirect):
    CODE = 308

class HTTP400(HTTPException):
    CODE = 400
    BODY = "No can do, buddy."

class HTTP401(HTTPException):
    CODE = 401
    BODY = "No ticket."

class HTTP403(HTTPException):
    CODE = 403
    BODY = "I can't let you do that, Dave."

class HTTP404(HTTPException):
    CODE = 404
    BODY = "I have absolutely no idea what you're talking about."

class HTTP418(HTTPException):
    CODE = 418
    BODY = "I'm a little teapot, short and stout."

class HTTP451(HTTPException):
    CODE = 451
    BODY = "The man says that you can't handle the truth."

class HTTP500(HTTPException):
    CODE = 500
    BODY = "Oops.  We done messed up."

class HTTP501(HTTPException):
    CODE = 501
    BODY = "A day may come when I implement this functionality, but it is not this day."
