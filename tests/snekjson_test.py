import unittest
from datetime import datetime, timedelta
import json
from sneks import snekjson

class TestSnekJson(unittest.TestCase):

    def test_blob_constructor(self):
        kwargs = {
            "foo":"bar",
            "alpha":"beta",
            "true":False,
            "one":2,
            "some":None
        }
        b = snekjson.blob(**kwargs)
        for k in kwargs:
            self.assertEqual(getattr(b, k), kwargs[k])
            self.assertEqual(b[k], kwargs[k])
        b["snek"] = "json"
        self.assertEqual(b.snek, "json")

    def test_blob_update(self):
        b = snekjson.blob()
        b["snek"] = "json"
        self.assertEqual(b.snek, "json")
        del b["snek"]
        self.assertEqual(b.get("snek","oops"), "oops")

    def test_normal_cases(self):
        s = "Hi!  I'm a string!!1!"
        l = [1, True, None, s, {"wx":"yz"}]
        d = {"foo":"bar","baz":None,"a":3,"false":True,"list":l}
        for x in [s,l,d]:
            self.assertEqual(snekjson.dumps(x), json.dumps(x))
            xl = json.dumps(x)
            self.assertEqual(snekjson.loads(xl), json.loads(xl))

if __name__ == '__main__':
    unittest.main()
