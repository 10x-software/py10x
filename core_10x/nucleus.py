import pickle
from datetime import datetime, date, time

import numpy

from core_10x.py_class import PyClass


class Nucleus:
    #===============================================================================================================================
    #   Nucleus Tags
    #===============================================================================================================================
    TYPE_TAG        = '_type'
    CLASS_TAG       = '_cls'
    REVISION_TAG    = '_rev'
    OBJECT_TAG      = '_obj'
    COLLECTION_TAG  = '_coll'
    ID_TAG          = '_id'

    #===============================================================================================================================
    #   Nucleus Records
    #===============================================================================================================================

    NX_RECORD       = '_nx'
    TYPE_RECORD     = '_dt'
    PICKLE_RECORD   = '_pkl'

    @staticmethod
    def deserialize_record(record: dict):
        record_type = record.get(Nucleus.TYPE_TAG, record)
        if record_type is record:  #-- record type is missing, so it's not a Nucleus record
            return None

        cls_name = record.get(Nucleus.CLASS_TAG, record)
        if cls_name is record:  #-- CLASS_TAG is missing - corrupted record
            raise TypeError(f'Nucleus record is currupted - CLASS_TAG is missing\n{record}')

        data_type = PyClass.find(cls_name)
        if data_type is None:
            raise TypeError(f'Unknown class {cls_name}')

        serialized_data = record.get(Nucleus.OBJECT_TAG, record)
        if serialized_data is record:    #-- serialized object is missing
            raise TypeError(f'Nucleus record is corrupted - missing OBJECT_TAG\n{record}')

        deserializer = Nucleus.s_record_map.get(record_type)
        if deserializer is None:
            raise TypeError(f'Unknown record type {record_type}')

        return deserializer(data_type, serialized_data)

    def deserialize_nx_record(data_type: type, serialized_data):
        if not issubclass(data_type, Nucleus):
            raise TypeError(f'NX_RECORD - data_type = {data_type} is not a subclass of Nucleus')

        return data_type.deserialize(serialized_data)

    def deserialize_type_record(data_type: type, serialized_data):
        deserializer = Nucleus.s_deserialization_map.get(data_type)
        if deserializer is None:
            raise TypeError(f'{data_type} - deserializer is missing')

        return deserializer(serialized_data)

    def deserialize_pickle_record(data_type: type, serialized_data):
        try:
            res = pickle.loads(serialized_data)
            if type(res) is not data_type:
                raise TypeError(f'PICKLE_RECORD - {data_type} is expected, unpickled {type(res)}')
            return res

        except Exception as ex:
            raise TypeError(f'PICKLE_RECORD - unpickling failed\n{str(ex)}')

    s_record_map = {
        NX_RECORD:      deserialize_nx_record,
        TYPE_RECORD:    deserialize_type_record,
        PICKLE_RECORD:  deserialize_pickle_record,
    }

    #===============================================================================================================================
    #   Serialize/deserialize Any value
    #===============================================================================================================================
    @staticmethod
    def serialize_any(value, embed, top_level = False):
        cls = type(value)

        #-- 1. Check if there's a built-in serializer
        serializer = Nucleus.s_serialization_map.get(cls)
        if serializer:
            serialized = serializer(value, embed)
            serialized_type = type(serialized)
            if serialized_type is not cls:     #-- different type, e.g., date serialized as str
                serialized = {
                    Nucleus.TYPE_TAG:   Nucleus.TYPE_RECORD,
                    Nucleus.CLASS_TAG:  PyClass.name(cls),
                    Nucleus.OBJECT_TAG: serialized
                }

            return serialized

        #-- 2. Check if it is Nucleus
        if issubclass(cls, Nucleus):
            serialized = value.serialize(embed)
            return {
                Nucleus.TYPE_TAG:   Nucleus.NX_RECORD,
                Nucleus.CLASS_TAG:  PyClass.name(cls),
                Nucleus.OBJECT_TAG: serialized
            }

        #-- 3. Last resort - let's try to pickle it
        return {
            Nucleus.TYPE_TAG:   Nucleus.PICKLE_RECORD,
            Nucleus.CLASS_TAG:  PyClass.name(cls),      #-- redundant; used to check this type after unpickling
            Nucleus.OBJECT_TAG: pickle.dumps(value)
        }

    @staticmethod
    def deserialize_any(value, expected_class: type = None):
        if expected_class is None:
            expected_class = type(value)

        deserializer = Nucleus.s_deserialization_map.get(expected_class)
        assert deserializer, f'May not deserialize {expected_class}'

        return deserializer(value)

    #===============================================================================================================================
    #   Serialize/deserialize containers and primitive types
    #===============================================================================================================================
    def serialize_list(value: list, embed: bool) -> list:
        return [ Nucleus.serialize_any(item, embed) for item in value ]

    def deserialize_list(value: list) -> list:
        return [ Nucleus.deserialize_any(v) for v in value ]

    def deserialize_tuple(value: list) -> tuple:
        return tuple( Nucleus.deserialize_any(v) for v in value )

    def serialize_dict(value: dict, embed: bool) -> dict:
        return { key: Nucleus.serialize_any(v, embed) for key, v in value.items() }

    def deserialize_dict(value: dict):
        res = Nucleus.deserialize_record(value)
        if res is not None:
            return res

        #-- this must be just a dict of values
        return { key: Nucleus.deserialize_any(v) for key, v in value.items() }

    def serialize_as_is(value, embed: bool):
        return value

    def deserialize_as_is(value):
        return value

    def serialize_complex(value: complex, embed: bool):
        return str(value)

    def deserialize_complex(value: str) -> complex:
        return complex(value)

    def serialize_date(value: date, embed: bool) -> str:
        return str(value)

    def deserialize_date(value: str) -> date:
        return date.fromisoformat(value)

    def serialize_type(value: type, embed: bool) -> str:
        return PyClass.name(value)

    def deserialize_type(cls_name: str) -> type:
        return PyClass.find(cls_name)

    s_serialization_map = {
        type:       serialize_type,
        bool:       serialize_as_is,
        int:        serialize_as_is,
        float:      serialize_as_is,
        complex:    serialize_complex,
        str:        serialize_as_is,
        bytes:      serialize_as_is,
        type(None): serialize_as_is,

        datetime:   serialize_as_is,
        date:       serialize_date,

        list:       serialize_list,
        tuple:      serialize_list,
        dict:       serialize_dict,

        #-- known external classes

        numpy.number: serialize_as_is,

    }

    s_deserialization_map = {
        type:       deserialize_type,
        bool:       deserialize_as_is,
        int:        deserialize_as_is,
        float:      deserialize_as_is,
        complex:    deserialize_complex,
        str:        deserialize_as_is,
        bytes:      deserialize_as_is,
        type(None): deserialize_as_is,

        datetime:   deserialize_as_is,
        date:       deserialize_date,

        list:       deserialize_list,
        tuple:      deserialize_tuple,
        dict:       deserialize_dict,

        #-- known external classes

        numpy.number: deserialize_as_is,

    }

    #===============================================================================================================================
    #   The following methods must be implemented by a subclass of Nucleus
    #===============================================================================================================================
    def serialize(self, embed: bool):
        raise NotImplementedError

    @classmethod
    def deserialize(cls, serialized_data) -> 'Nucleus':
        raise NotImplementedError

    def __repr__(self):
        raise NotImplementedError

    def __str__(self):
        return self.__repr__()

    @classmethod
    def from_str(cls, s: str) -> 'Nucleus':
        raise NotImplementedError

    @classmethod
    def from_any_except_str(cls, value) -> 'Nucleus':
        raise NotImplementedError

    @classmethod
    def from_any(cls, value) -> 'Nucleus':
        if isinstance(value, str):
            return cls.from_str(value)

        return cls.from_any_except_str(value)

    @classmethod
    def same_values(cls, value1, value2) -> bool:
        raise NotImplementedError

    @classmethod
    def choose_from(cls):
        return {}
