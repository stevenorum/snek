#!/usr/bin/env python3

import base64
from botocore.exceptions import *
from boto3.dynamodb.conditions import Key, Attr, Or
from boto3.dynamodb.types import TypeSerializer
import boto3
import copy
from datetime import datetime
import decimal
import html
import inspect
import json
import logging
import os
import random
import traceback

VERSION_KEY = '__version__'

DATETIME_FORMAT = "datetime:%Y-%m-%dT%H:%M:%S.%fZ"

logger = logging.getLogger(__name__)
_TRACE_LEVEL = 1
def _TRACE(msg, *args, **kwargs):
    return logger.log(_TRACE_LEVEL, msg, *args, **kwargs)

def DECIMAL(*args, **kwargs):
    d = decimal.Decimal(*args, **kwargs)
    decimal.getcontext().clear_flags()
    return d

def _ensure_ddbsafe(d):
    if isinstance(d, dict):
        return {k:_ensure_ddbsafe(d[k]) for k in d}
    elif isinstance(d, list):
        return [_ensure_ddbsafe(e) for e in d]
    elif isinstance(d, decimal.Decimal):
        return float(d)
    elif isinstance(d, datetime):
        return d.strftime(DATETIME_FORMAT)
    elif isinstance(d, str) and "" == d:
        return None
    else:
        return d

def ensure_ddbsafe(d):
    return json.loads(json.dumps(_ensure_ddbsafe(d)), parse_float=decimal.Decimal)

def _fix_types(d):
    if isinstance(d, dict):
        return {k:_fix_types(d[k]) for k in d}
    elif isinstance(d, list):
        return [_fix_types(e) for e in d]
    elif isinstance(d, decimal.Decimal):
        return float(d)
    elif isinstance(d, str):
        if d.startswith("datetime:"):
            try:
                return datetime.strptime(d, DATETIME_FORMAT)
            except:
                pass
    return d

class BaseDynamoObject(dict):
    """
    Holder class for a bunch of class methods and stuff like that.
    """
    _SCHEMA_CACHE = None
    _TABLE_CACHE = None
    _CLASSNAME = None
    _REQUIRED_ATTRS = []
    _COMPOUND_ATTRS = {}
    _DEFAULT_ITEMS = []
    _META_ITEMS = []

    @classmethod
    def _from_dict(cls, d):
        if isinstance(d, cls):
            return d
        return cls(d)

    @classmethod
    def objectify(cls, d):
        return cls._from_dict(d)

    def dictify(self):
        return dict(self)

    @classmethod
    def _encode_nexttoken(cls, key):
        # TODO: replace the json step with something that'll work for any input
        # Convert to a string
        # This won't work for a lot of valid keys due to the json serialization step
        key = _fix_types(key)
        key = json.dumps(key)
        # base64 encode it to make it safer to handle
        key = base64.urlsafe_b64encode(key.encode("utf-8")).decode("utf-8")
        # strip the padding, as we can easily re-add it later
        key = key.replace("=","")
        return key

    @classmethod
    def _decode_nexttoken(cls, key):
        # TODO: replace the json step with something that'll work for any input
        # re-add the padding
        key = key + "=" * ((-1*len(key))%16)
        # convert if back from base64-encoded bytes to the underlying string
        key = base64.urlsafe_b64decode(key.encode("utf-8")).decode("utf-8")
        # load the string back into a dict
        # This won't work for a lot of valid keys due to the json serialization step
        key = json.loads(key)
        key = ensure_ddbsafe(key)
        return key

    @classmethod
    def _parse_items(cls, response):
        items = []
        for item in response.get("Items",[]):
            items.append(cls(dict(_fix_types(item))))
        return items

    @classmethod
    def _preprocess_search_params(cls, **kwargs):
        params = dict(kwargs)
        if params.get("ShufflePages", None):
            del params["ShufflePages"]
        if params.get("PageSize", None):
            if not params.get("Limit", None):
                params["Limit"] = params["PageSize"]
            del params["PageSize"]
        if params.get("MaxResults", None):
            if params["MaxResults"] > 0 and not params.get("Limit", None):
                # This is an arbitrary padding factor in case the user is using some sort of server-side filtering.
                # Limit sets the number of items evaluated, so the number returned may be smaller.
                # TODO: Either properly document this, or make it less janktastic.
                params["Limit"] = 5*params["MaxResults"]
            del params["MaxResults"]
        if params.get("NextToken", None) and not params.get("ExclusiveStartKey", None):
            params["ExclusiveStartKey"] = cls._decode_nexttoken(params["NextToken"])
        if "NextToken" in params:
            del params["NextToken"]
        if not params.get("KeyConditionExpression", None):
            hashname, rangename = cls._HASH_AND_RANGE_KEYS(index_name = params.get("IndexName", None))
            if params.get(hashname) and not params.get("HashKey", None):
                params["HashKey"] = params[hashname]
                del params[hashname]
            if params.get(rangename) and not params.get("RangeKey", None):
                params["RangeKey"] = params[rangename]
                del params[rangename]
            if params.get("HashKey", None) and not params.get("KeyConditionExpression", None):
                hkc = Key(hashname).eq(params["HashKey"])
                if params.get("RangeKey", None):
                    rk = params["RangeKey"]
                    if isinstance(rk,(list, tuple)):
                        rkc = getattr(Key(rangename),rk[0])(*rk[1:])
                    else:
                        rkc = Key(rangename).eq(rk_arg)
                    kce = hkc & rkc
                else:
                    kce = hkc
                params["KeyConditionExpression"] = kce
        if "HashKey" in params:
            del params["HashKey"]
        if "RangeKey" in params:
            del params["RangeKey"]
        return params

    @classmethod
    def _postprocess_search_results(cls, results):
        response = {
            "Items":cls._parse_items(results),
            "Count":results.get("Count",0),
            "ScannedCount":results.get("ScannedCount",0),
            "NextToken":None,
            "RawResponse":results
        }
        if results.get("LastEvaluatedKey", None):
            response["NextToken"] = cls._encode_nexttoken(results["LastEvaluatedKey"])
        return response

    @classmethod
    def _scanquery(cls, func_name, **kwargs):
        # Almost certainly a better way to have these share this code,
        # but it'd take literally **minutes** to figure it out and ain't nobody got time for that.
        if func_name not in ["scan","query"]:
            logger.error("Nice try, kiddo.")
            raise RuntimeError("Invalid search operation '{}' specified.".format(func_name))
        params = cls._preprocess_search_params(**kwargs)
        results = getattr(cls.TABLE(),func_name)(**params)
        if results.get("ConsumedCapacity"):
            print(json.dumps(results.get("ConsumedCapacity")))
        return cls._postprocess_search_results(results)

    @staticmethod
    def _autopaginate_search(func, **kwargs):
        # Almost certainly a better way to have these share this code,
        # but it'd take literally **minutes** to figure it out and ain't nobody got time for that.
        max_results = kwargs.get("MaxResults", -1)
        item_count = 0
        finished = False
        shuffle_pages = kwargs.get("ShufflePages", False)
        response = func(**kwargs)
        while response and not finished:
            items = response.get("Items")
            if shuffle_pages:
                random.shuffle(items)
            for item in items:
                if finished:
                    break
                item_count += 1
                if max_results > 0 and item_count >= max_results:
                    finished = True
                yield item
            if response.get("NextToken") and not finished:
                response = func(NextToken=response.get("NextToken"), **kwargs)
            else:
                response = None

    @classmethod
    def scan(cls, **kwargs):
        return cls._scanquery("scan", **kwargs)

    @classmethod
    def query(cls, **kwargs):
        return cls._scanquery("query", **kwargs)

    @classmethod
    def scan_all(cls, **kwargs):
        return cls._autopaginate_search(cls.scan, **kwargs)

    @classmethod
    def query_all(cls, **kwargs):
        return cls._autopaginate_search(cls.query, **kwargs)

    @classmethod
    def count(cls, **kwargs):
        kwargs["Select"] = "COUNT"
        params = cls._preprocess_search_params(**kwargs)
        results = cls.TABLE().query(**params)
        return cls._postprocess_search_results(results)

    @classmethod
    def count_all(cls, **kwargs):
        response = cls.count(**kwargs)
        item_count = 0
        scanned_count = 0
        while response:
            item_count += response.get("Count",0)
            scanned_count += response.get("ScannedCount",0)
            if response.get("NextToken"):
                response = cls.count(NextToken=response.get("NextToken"), **kwargs)
            else:
                response = None
        return {
            "Count": item_count,
            "ScannedCount": scanned_count
        }

    @classmethod
    def load(cls, **kwargs):
        obj = cls.TABLE().get_item(Key=kwargs).get("Item", {})
        if obj:
            obj = _fix_types(obj)
            return cls(obj)
        return None

    @classmethod
    def SCHEMA(cls, use_cache=True):
        if cls._SCHEMA_CACHE and use_cache:
            return cls._SCHEMA_CACHE
        schema = cls._SCHEMA()
        cls._SCHEMA_CACHE = schema
        return schema

    @classmethod
    def _SCHEMA(cls, use_cache=True):
        raise NotImplementedError("Each subclass must implement this on their own.")

    @classmethod
    def TABLE_NAME(cls, use_cache=True):
        schema = cls.SCHEMA(use_cache=use_cache)
        return schema.get('TableName')

    @classmethod
    def CLASS_NAME(cls):
        return cls._CLASSNAME if cls._CLASSNAME else "{module}.{name}".format(module=cls.__module__, name=cls.__name__)

    @classmethod
    def TABLE(cls):
        if not cls._TABLE_CACHE:
            cls._TABLE_CACHE = boto3.resource('dynamodb').Table(cls.TABLE_NAME())
        return cls._TABLE_CACHE

    @classmethod
    def create_table(cls):
        boto3.client("dynamodb").create_table(**cls._SCHEMA())

    @classmethod
    def _get_required_attributes(cls):
        attrs = []
        hashkn, rangekn = cls._HASH_AND_RANGE_KEYS()
        if hashkn:
            attrs.append(hashkn)
        if rangekn:
            attrs.append(rangekn)
        attrs.extend(cls._REQUIRED_ATTRS)
        return attrs

    @classmethod
    def _HASH_AND_RANGE_KEYS(cls, index_name=None):
        schema = cls._SCHEMA()
        key_schema = schema['KeySchema']
        if index_name:
            gsis = schema.get("GlobalSecondaryIndexes", [])
            matches = [gsi for gsi in gsis if gsi["IndexName"] == index_name]
            if len(matches) == 0:
                raise RuntimeError("No index with the name '{index_name}' found!".format(index_name=index_name))
            key_schema = matches[0]["KeySchema"]
        hash = [h['AttributeName'] for h in key_schema if h['KeyType']=='HASH'][0]
        ranges = [r['AttributeName'] for r in key_schema if r['KeyType']=='RANGE']
        range = ranges[0] if ranges else None
        return hash, range

    @classmethod
    def _get_class_relation_map(cls, obj):
        return {'class':cls.CLASS_NAME(), 'key':obj._get_key_dict()}

    @classmethod
    def _add_compound_attr(cls, attrname, attrfunc, save=False):
        cls._COMPOUND_ATTRS[attrname] = {"func":attrfunc,"save":save}

    @classmethod
    def _remove_compound_attr(cls, attrname):
        if attrname in cls._COMPOUND_ATTRS:
            del cls._COMPOUND_ATTRS[attrname]

class DynamoObject(BaseDynamoObject):
    '''
    Base class for all DynamoDB-storable objects.  Cannot itself be instantiated.

    The only thing that a subclass is required to implement is the classmethod SCHEMA, and it must return a dict that can be passed to client.create_table(**schema) and succeed.

    Constructor args:

    :param kwargs: Keys for an object, and any attributes to attach to that object.
    :rtype: DynamoObject
    '''
    def __init__(self, mapping={}, **kwargs):
        super().__init__(mapping, **kwargs)

    def __getitem__(self, key):
        if key in self._META_ITEMS:
            return self._META_ITEMS[key](self)
        try:
            return dict.__getitem__(self, key)
        except:
            if key in self._DEFAULT_ITEMS:
                _default = self._DEFAULT_ITEMS[key]
                return _default() if callable(_default) else _default
            raise

    def __setitem__(self, key, val):
        if key in self._META_ITEMS:
            # May want to make this an error at some point, but for now just make it a no-op for testing.
            # raise RuntimeError("Setting an explicit value for a meta-item ('{}') is not allowed.".format(key))
            return
        dict.__setitem__(self, key, val)

    def _my_hash_and_range(self):
        hash_keyname, range_keyname = self.__class__._HASH_AND_RANGE_KEYS()
        hash_key = self[hash_keyname]
        range_key = self[range_keyname] if range_keyname else None
        return hash_key, range_key

    def _get_key_dict(self, dictionary=None):
        hash_keyname, range_keyname = self.__class__._HASH_AND_RANGE_KEYS()
        keys = {}
        dictionary = dictionary if dictionary else self
        for k in (hash_keyname, range_keyname):
            if k and k in dictionary.keys():
                # I'm explicitly bypassing the getter here in the off chance either hash or range is a foreign key
                keys[k] = dictionary[k]
        return keys

    def save(self, force=False, save_if_missing=True, save_if_existing=True):
        _TRACE("DynamoObject.save reached")
        if not save_if_missing and not save_if_existing:
            raise RuntimeError("At least one of save_if_missing and save_if_existing must be true.")

        old_version = DECIMAL(self.get(VERSION_KEY, -1))
        create_condition = Attr(VERSION_KEY).not_exists()
        if force:
            update_condition = Attr(VERSION_KEY).exists()
        else:
            update_condition = Attr(VERSION_KEY).eq(old_version)
        CE = None
        if force and save_if_missing and save_if_existing:
            pass
        elif save_if_missing and save_if_existing:
            CE = Or(create_condition, update_condition)
        elif save_if_existing:
            CE = update_condition
        else:
            # If we're here, we know that create_condition=True
            CE = create_condition
        try:
            self[VERSION_KEY] = old_version + 1
            if CE:
                self._store(CE)
            else:
                self._store()
            return self
        except ClientError as e:
            self[VERSION_KEY] = old_version
            raise e

    def modify(self, force=False):
        return self.save(force=force, save_if_existing=True, save_if_missing=False)

    def create(self, force=False):
        return self.save(force=force, save_if_existing=False, save_if_missing=True)

    def _store(self, CE=None):
        _TRACE("DynamoObject._store reached")
        dict_to_save = copy.deepcopy(self)
        required = self._get_required_attributes()
        missing = [r for r in required if not dict_to_save.get(r, None)]
        if missing:
            raise RuntimeError('The following attributes are missing and must be added before saving: '+', '.join(missing))
        dict_to_save = ensure_ddbsafe(dict_to_save)
        if CE:
            self.__class__.TABLE().put_item(Item=dict_to_save, ConditionExpression=CE)
        else:
            self.__class__.TABLE().put_item(Item=dict_to_save)
        _TRACE("DynamoObject._store returning")
        return self

    def delete(self, CE=None):
        if CE:
            return self.__class__.TABLE().delete_item(Key=self._get_key_dict(), ConditionExpression=CE)
        else:
            return self.__class__.TABLE().delete_item(Key=self._get_key_dict())

    # def load(self):
    #     new_me = self.__class__.TABLE().get_item(Key=self._get_key_dict()).get("Item", {})
    #     return self.__class__.__init__(new_me)

    def reload(self):
        '''
        Reloads the item's attributes from DynamoDB, replacing whatever's currently in the object.
        '''
        new_me = self.load()
        for k in list(self.keys()):
            if k not in new_me:
                del self[k]
        self.update(new_me)
        return self

class CFObject(DynamoObject):
    '''
    Base class for objects that are based on tables created in a CloudFormation stack.
    '''

    _CF_STACK_NAME = None
    _CF_LOGICAL_NAME = None
    _CF_CLIENT = boto3.client('cloudformation')
    _CF_TEMPLATE = None
    _CF_RESOURCES = {}

    @classmethod
    def _set_cf_info(cls, cf_stack_name=None, cf_logical_name=None):
        if cf_stack_name:
            cls._CF_STACK_NAME = cf_stack_name
        if cf_logical_name:
            cls._LOGICAL_NAME = cf_logical_name

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @classmethod
    def _get_stack_name(cls, stack_name=None):
        stack_name = stack_name if stack_name else cls._CF_STACK_NAME
        if not stack_name:
            if os.environ.get("STACK_NAME"):
                return os.environ["STACK_NAME"]
            raise RuntimeError("Stack name not set!")
        return stack_name

    @classmethod
    def _get_stack_and_logical_names(cls, stack_name=None, logical_name=None):
        stack_name = stack_name if stack_name else cls._CF_STACK_NAME
        logical_name = logical_name if logical_name else cls._CF_LOGICAL_NAME
        if not stack_name or not logical_name:
            raise RuntimeError("Stack name or logical name (or both) not set!")
        return stack_name, logical_name

    @classmethod
    def _describe_stack_resource(cls, stack_name=None, logical_name=None):
        stack_name, logical_name = cls._get_stack_and_logical_names(stack_name=stack_name, logical_name=logical_name)
        if logical_name not in cls._CF_RESOURCES:
            logging.warn("Cache miss loading _CF_RESOURCE for class {}".format(cls))
            response = cls._CF_CLIENT.describe_stack_resource(StackName=stack_name, LogicalResourceId=logical_name)
            if not response or "StackResourceDetail" not in response:
                raise RuntimeError("Resource does not exist!")
            cls._CF_RESOURCES[logical_name] = response["StackResourceDetail"]
        else:
            logging.info("Cache hit loading _CF_RESOURCE for class {}".format(cls))
        return cls._CF_RESOURCES[logical_name]

    @classmethod
    def _get_physical_resource_id(cls, stack_name=None, logical_name=None):
        return cls._describe_stack_resource(stack_name=stack_name, logical_name=logical_name)["PhysicalResourceId"]

    @classmethod
    def _get_template(cls, stack_name=None):
        stack_name = cls._get_stack_name(stack_name=stack_name)
        if not getattr(cls, "_CF_TEMPLATE"):
            logging.warn("Cache miss loading _CF_TEMPLATE for class {}".format(cls))
            try:
                template = cls._CF_CLIENT.get_template(StackName=stack_name)["TemplateBody"]
                setattr(cls, "_CF_TEMPLATE", template)
            except ValidationError:
                raise RuntimeError("Unable to retrieve template for stack {}, likely due to it not existing.".format(stack_name))
        else:
            logging.info("Cache hit loading _CF_TEMPLATE for class {}".format(cls))
        return cls._CF_TEMPLATE

    @classmethod
    def _clear_cf_cache(cls):
        setattr(cls, "_CF_TEMPLATE", None)
        setattr(cls, "_CF_RESOURCES", {})

    @classmethod
    def _SCHEMA(cls):
        stack_name, logical_name = cls._get_stack_and_logical_names()
        template = cls._get_template(stack_name=stack_name)
        resources = template["Resources"]
        if logical_name not in resources:
            raise RuntimeError("Stack doesn't contain a table with the given logical name!")
        resource = resources[logical_name]
        table_type = "AWS::DynamoDB::Table"
        if not table_type == resource["Type"]:
            raise RuntimeError("Logical resource {} in stack {} is of type '{}', not type '{}'".format(logical_name, stack_name, resource["Type"], table_type))
        properties = dict(resource["Properties"])
        properties["TableName"] = cls._get_physical_resource_id()
        return properties

    @classmethod
    def _get_class_relation_map(cls, obj):
        stack_name, logical_name = obj._get_stack_and_logical_names()
        return {'class':cls.CLASS_NAME(), '_cf_stack_name':stack_name, '_cf_logical_name':logical_name}

    @classmethod
    def lazysubclass(cls, stack_name=None, logical_name=None):
        '''
        Returns a class that inherits from this one, with the given default stack and logical names.
        If you just want to have a new object type with no fancy features added, this makes it a one-liner.

        :rtype: Class that inherits from cls
        '''
        class LazyObject(cls):
            _CF_STACK_NAME = cls._get_stack_name(stack_name)
            _CF_LOGICAL_NAME = logical_name if logical_name else cls._CF_LOGICAL_NAME
            _CLASSNAME = cls.CLASS_NAME()
        return LazyObject

class DataField(object):
    def __init__(self, key, **kwargs):
        self.key = key
        self.pretty = kwargs.get("pretty",key.replace("_"," ").title())
        self.hidden = kwargs.get("hidden",False)
        self.immutable = kwargs.get("immutable",False)
        self.data_type = kwargs.get("data_type","text")
        self.data_width = kwargs.get("data_width",50)
        self.data_height = kwargs.get("data_height",1)
        self.default = kwargs.get("default","")
        self.to_str = kwargs.get("to_str",lambda x:x)
        self.value_generator = kwargs.get("value_generator",None)
        self.validator = kwargs.get("validator",lambda x: True)
        pass

    def extract_value(self, d):
        return d.get(self.key, self.default)

    def form_format(self, d, immutable=False):
        value = self.extract_value(d)
        if self.hidden:
            value = html.escape(self.to_str(value) if value else "")
            response = '<input type="hidden" name="{key}" id="{key}_field" value="{value}"{immutable}>'
        else:
            response = '<label for="{key}">{pretty}: </label>\n'
            if self.data_type == "textarea":
                value = html.escape(self.to_str(value) if value else "")
                response += '<br><textarea name="{key}" id="{key}_field" rows="{data_height}" cols="{data_width}"{immutable}>{value}</textarea>'
            elif self.data_type == "datetime":
                if isinstance(value, datetime):
                    value = value.strftime("%Y-%m-%dT%H:%M")
                response += '<input type="datetime-local" name="{key}" id="{key}_field" value="{value}"{immutable}>'
            elif self.data_type == "int":
                value = int(value) if value else 0
                response += '<input type="number" name="{key}" id="{key}_field" value="{value}"{immutable}>'
            elif self.data_type == "boolean":
                value = "checked" if value else ""
                response += '<input type="checkbox" name="{key}" id="{key}_field" {value}'
                if immutable or self.immutable:
                    response += ' onclick="return false;"'
                response += '>'
            else:
                value = html.escape(self.to_str(value) if value else "")
                response += '<input type="text" name="{key}" id="{key}_field" value="{value}"{immutable}>'
            response += "<br>\n"
        return response.format(
            key=self.key,
            pretty=self.pretty,
            data_height=self.data_height,
            data_width=self.data_width,
            immutable=" readonly" if (immutable or self.immutable) else "",
            value=value
        )

class StructuredObject(DynamoObject):
    _HIDDEN_KEYS = [VERSION_KEY]
    _DATA_FIELDS = []

    @classmethod
    def skema(cls):
        return {x.key:x for x in cls._DATA_FIELDS}

    @classmethod
    def skema_keys(cls):
        return [k.key for k in cls._DATA_FIELDS]

    def all_keys(self):
        sk = self.skema_keys()
        return sk + [x for x in self if x not in sk]

    @classmethod
    def skeme(cls, k):
        return cls.skema().get(k, DataField(k))

    @classmethod
    def from_body(cls, body):
        raw_obj = json.loads(body)
        obj = {k:skeme(k).preprocessor(raw_obj[k]) for k in raw_obj}
        return cls(obj)

    def save(self, *args, **kwargs):
        for k in self.all_keys():
            skeme = self.skeme(k)
            if skeme.value_generator and not self.get(k):
                self[k] = skeme.value_generator()
            v = self.get(k)
            if not skeme.validator(v):
                raise RuntimeError('Invalid value provided for key "{}"!'.format(k))
        return super().save(*args, **kwargs)

    def data_form(self, immutable=False):
        keys = self.skema_keys()
        blocks = []
        for k in keys:
            v = self.skeme(k).form_format(self, immutable=immutable)
            if v:
                blocks.append(v)
        return '''<form>\n{}\n</form>'''.format("\n".join(blocks))
