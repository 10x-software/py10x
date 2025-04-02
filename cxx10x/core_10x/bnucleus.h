//
// Created by AMD on 3/26/2025.
//

#pragma once

#include "py_linkage.h"

class BNucleus {
public:
    using DeserializationRecordMethod = std::function<py::object(py::object data_type, py::object serialized_data)>;
    using DeserializationRecordMap = std::unordered_map<py::object, DeserializationRecordMethod>;
    static DeserializationRecordMap *s_record_map;
    static DeserializationRecordMethod deserialization_record_method(const py::object& record_tag);

    using DeserializationMethod = std::function<py::object(py::object serialized_data)>;
    using DeserializationMap = std::unordered_map<py::object, DeserializationMethod >;
    static DeserializationMap* s_deserialization_map;
    static DeserializationMethod deserialization_method(const py::object& data_type);

    using SerializationMethod = std::function<py::object(py::object value, bool embed)>;
    using SerializationMap = std::unordered_map<py::object, SerializationMethod >;
    static SerializationMap* s_serialization_map;
    static SerializationMethod serialization_method(const py::object& data_type);

    static py::object TYPE_TAG()            { return py::str("_type"); };
    static py::object CLASS_TAG()           { return py::str("_cls"); }
    static py::object REVISION_TAG()        { return py::str("_rev"); }
    static py::object OBJECT_TAG()          { return py::str("_obj"); }
    static py::object COLLECTION_TAG()      { return py::str("_coll"); }
    static py::object ID_TAG()              { return py::str("_id"); }
    static py::object NX_RECORD_TAG()       { return py::str("_nx"); }
    static py::object TYPE_RECORD_TAG()     { return py::str("_dt"); }
    static py::object PICKLE_RECORD_TAG()   { return py::str("_pkl"); }

    static py::object deserialize_record(const py::dict& record);

    static py::object serialize_any(const py::object& value, bool embed);
    static py::object deserialize_any(const py::object& value, const py::object& expected_class = py::none());

    static py::object serialize_list(const py::object& list, bool embed);
    static py::object deserialize_list(const py::object& list);
    static py::object deserialize_tuple(const py::object& list)                 { return deserialize_list(list).cast<py::tuple>(); }

    static py::object serialize_dict(const py::object& dict, bool embed);
    static py::object deserialize_dict(const py::object& dict);

    static py::object serialize_as_is(const py::object& value, bool)            { return value; }
    static py::object deserialize_as_is(const py::object& value)                { return value; }

    static py::object serialize_complex(const py::object& value, bool)          { return py::str(value); }
    static py::object deserialize_complex(const py::object& value)              { return PyLinkage::complex_class()(value); }

    static py::object serialize_date(const py::object& date, bool)              { return py::str(date); }
    static py::object deserialize_date(const py::object& date)                  { return PyLinkage::fromisoformat(date); }

    static py::object serialize_type(const py::object& type, bool)              { return PyLinkage::find_class_id(type); }
    static py::object deserialize_type(const py::object& cls_id)                { return PyLinkage::find_class(cls_id); }


};
