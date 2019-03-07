import boto3
from boto3.dynamodb.conditions import Key, Attr
import sneks.snekjson as json
from decimal import Decimal
from datetime import datetime, timedelta
import traceback

STRFTIME_STRING = "%Y%m%d %H:%M:%S.%f"

def make_json_safe(item):
    if isinstance(item, list):
        item = [make_json_safe(e) for e in item]
    if isinstance(item, dict):
        item = {k:make_json_safe(item[k]) for k in item}
    if isinstance(item, Decimal):
        item = float(item)
    if isinstance(item, datetime):
        item = item.strftime(STRFTIME_STRING)
    return item

def dumps(obj, *args, **kwargs):
    return json.dumps(make_json_safe(obj), *args, **kwargs)

def make_ddb_safe(item):
    if isinstance(item, list):
        item = [make_ddb_safe(e) for e in item]
    if isinstance(item, dict):
        item = {k:make_ddb_safe(item[k]) for k in item}
    if isinstance(item, float):
        item = Decimal(item)
    if isinstance(item, datetime):
        item = item.strftime(STRFTIME_STRING)
    if item is None:
        item = "null"
    if item == "":
        item = json.dumps("")
    return item

def deepload(s):
    while True:
        try:
            s = json.loads(s)
        except:
            break
    if isinstance(s, list):
        s = [deepload(x) for x in s]
    if isinstance(s, dict):
        s = {k:deepload(s[k]) for k in s}
    return s

def ddb_save(table, item, **kwargs):
    item = make_ddb_safe(item)
    try:
        table.put_item(Item=item, **kwargs)
    except:
        print("Error saving the following object:")
        print(dumps(item))
        traceback.print_exc()
        raise

def ddb_load(table, key, **kwargs):
    item = None
    try:
        item = table.get_item(Key=key, **kwargs)["Item"]
    except:
        traceback.print_exc()
    return item

def ddb_query(table, key, value, **kwargs):
    # Todo: turn into a generator that auto-paginates.
    return table.query(Select='ALL_ATTRIBUTES', KeyConditionExpression=Key(key).eq(value), **kwargs)["Items"]

def table_from_env(varname):
    return boto3.resource("dynamodb").Table(os.environ[varname])
