//
// Created by AMD on 3/26/2025.
//

#include "bnucleus.h"

py::object BNucleus::deserialize_record(const py::dict& record) {
    auto XNone = PyLinkage::XNone();
    auto record_type = PyLinkage::dict_get(record, TYPE_TAG());
    if (record_type.is(XNone))
        return py::none();      //-- it's not a Nucleus record

    auto cls_id = PyLinkage::dict_get(record, CLASS_TAG());
    if (cls_id.is(XNone))
        throw py::type_error(py::str("Nucleus record is corrupted - '{}' is missing\n{}").format(CLASS_TAG(), record));

    auto data_type = PyLinkage::find_class(cls_id);

    auto serialized_data = PyLinkage::dict_get(record, OBJECT_TAG());
    if (serialized_data.is(XNone))
        throw py::type_error(py::str("Nucleus record is corrupted - '{}' is missing\n{}").format(OBJECT_TAG(), record));

    auto deserializer = deserialization_record_method(record_type);
    if (!deserializer)
        throw py::type_error(py::str("Unknown record type '{}'\n{}").format(record_type, record));

    return deserializer(data_type, serialized_data);
}

py::object deserialize_nx_record(const py::object& data_type, const py::object& serialized_data) {
    if (!PyLinkage::issubclass(data_type, PyLinkage::nucleus_class()))
        throw py::type_error(py::str("NX_RECORD - data_type = {} is not a subclass of Nucleus\n{}").format(data_type));

    return data_type.attr("deserialize")(serialized_data);
}

py::object deserialize_type_record(const py::object& data_type, const py::object& serialized_data) {
    const auto method = BNucleus::deserialization_method(data_type);
    if (!method)
        throw py::type_error(py::str("{} - deserializer is missing").format(data_type));

    return method(serialized_data);
}

py::object deserialize_pickle_record(const py::object& data_type, const py::object& serialized_data) {
    auto res = PyLinkage::unpickle(serialized_data);
    if (!py::type::of(res).is(data_type))
        throw py::type_error(py::str("PICKLE_RECORD - {} is expected, unpickled {}").format(data_type, py::type::of(res)));
    return res;
}

py::object BNucleus::serialize_any(const py::object& value, bool embed) {
    auto cls = PyLinkage::type(value);

    //-- 1. Check if there's a built-in serializer
    if (const auto serializer = serialization_method(cls)) {
        auto serialized = serializer(value, embed);
        auto serialized_type = PyLinkage::type(serialized);

        if (!serialized_type.is(cls)) {     //-- different type, e.g., date serialized as str
            py::dict res;
            res[TYPE_TAG()] = TYPE_RECORD_TAG();
            res[CLASS_TAG()] = PyLinkage::find_class_id(cls);
            res[OBJECT_TAG()] = serialized;
            return res;
        } else
            return serialized;
    }

    //-- 2. Check if it is Nucleus
    if (PyLinkage::issubclass(cls, PyLinkage::nucleus_class())) {
        auto serialized = cls.attr("serialize")(value, embed);
        py::dict res;
        res[TYPE_TAG()] = NX_RECORD_TAG();
        res[CLASS_TAG()] = PyLinkage::find_class_id(cls);
        res[OBJECT_TAG()] = serialized;
        return res;
    }

    //-- 3. Last resort - let's try to pickle it
    py::dict res;
    res[TYPE_TAG()] = PICKLE_RECORD_TAG();
    res[CLASS_TAG()] = PyLinkage::find_class_id(cls);
    res[OBJECT_TAG()] = PyLinkage::pickle(value);
    return res;
}

py::object BNucleus::deserialize_any(const py::object& value, const py::object& expected_class) {
    auto cls = expected_class.is_none() ? PyLinkage::type(value) : expected_class;
    const auto deserializer = deserialization_method(cls);
    if (!deserializer)
        throw py::value_error(py::str("May not deserialize {}").format(cls));

    return deserializer(value);
}

py::object BNucleus::serialize_list(const py::object& list, bool embed) {
    py::list res;
    for (const auto &item : list) {
        const auto value = serialize_any(item.cast<py::object>(), embed);
        res.append(value);
    }
    return res;
}

py::object BNucleus::deserialize_list(const py::object& list) {
    py::list res;
    for (const auto &item : list) {
        const auto value = deserialize_any(item.cast<py::object>());
        res.append(value);
    }
    return res;
}

py::object BNucleus::serialize_dict(const py::object& dict, bool embed) {
    py::dict res;
    for (const auto &[key, value] : dict.cast<py::dict>()) {
        const auto serialized_value = serialize_any(value.cast<py::object>(), embed);
        res[key] = serialized_value;
    }
    return res;
}

py::object BNucleus::deserialize_dict(const py::object& dict) {
    const auto rec = dict.cast<py::dict>();
    if (const auto res1 = deserialize_record(rec); !res1.is_none())
        return res1;

    //-- this must be just a dict of values then
    py::dict res2;
    for (const auto &[key, serialized_value] : rec) {
        const auto value = deserialize_any(serialized_value.cast<py::object>());
        res2[key] = value;
    }
    return res2;
}

BNucleus::DeserializationRecordMap * BNucleus::s_record_map = nullptr;
BNucleus::DeserializationRecordMethod BNucleus::deserialization_record_method(const py::object& record_tag) {
    if (!s_record_map) {
        s_record_map = new DeserializationRecordMap();
        s_record_map->insert({BNucleus::NX_RECORD_TAG(),     deserialize_nx_record});
        s_record_map->insert({BNucleus::TYPE_RECORD_TAG(),   deserialize_type_record});
        s_record_map->insert({BNucleus::PICKLE_RECORD_TAG(), deserialize_pickle_record});
    }
    auto it = s_record_map->find(record_tag);
    return it != s_record_map->end() ? it->second : nullptr;
}

BNucleus::SerializationMap* BNucleus::s_serialization_map = nullptr;
BNucleus::SerializationMethod BNucleus::serialization_method(const py::object& data_type) {
    if (!s_serialization_map) {
        s_serialization_map = new SerializationMap();
        s_serialization_map->insert({PyLinkage::type_class(),       serialize_type});
        s_serialization_map->insert({PyLinkage::bool_class(),       serialize_as_is});
        s_serialization_map->insert({PyLinkage::int_class(),        serialize_as_is});
        s_serialization_map->insert({PyLinkage::float_class(),      serialize_as_is});
        s_serialization_map->insert({PyLinkage::complex_class(),    serialize_complex});
        s_serialization_map->insert({PyLinkage::str_class(),        serialize_as_is});
        s_serialization_map->insert({PyLinkage::bytes_class(),      serialize_as_is});
        s_serialization_map->insert({PyLinkage::type(py::none()),   serialize_as_is});
        s_serialization_map->insert({PyLinkage::datetime_class(),   serialize_as_is});
        s_serialization_map->insert({PyLinkage::date_class(),       serialize_date});
        s_serialization_map->insert({PyLinkage::list_class(),       serialize_list});
        s_serialization_map->insert({PyLinkage::tuple_class(),      serialize_list});
        s_serialization_map->insert({PyLinkage::dict_class(),       serialize_dict});

        //-- known external classes
        s_serialization_map->insert({py::module_::import("numpy").attr("number"),   serialize_as_is});
        s_serialization_map->insert({py::module_::import("numpy").attr("float64"),   serialize_as_is});
    }

    auto it = s_serialization_map->find(data_type);
    return it != s_serialization_map->end() ? it->second : nullptr;
}

BNucleus::DeserializationMap* BNucleus::s_deserialization_map = nullptr;
BNucleus::DeserializationMethod BNucleus::deserialization_method(const py::object& data_type) {
    if (!s_deserialization_map) {
        s_deserialization_map = new DeserializationMap();
        s_deserialization_map->insert({PyLinkage::type_class(),         deserialize_type});
        s_deserialization_map->insert({PyLinkage::bool_class(),         deserialize_as_is});
        s_deserialization_map->insert({PyLinkage::int_class(),          deserialize_as_is});
        s_deserialization_map->insert({PyLinkage::float_class(),        deserialize_as_is});
        s_deserialization_map->insert({PyLinkage::complex_class(),      deserialize_complex});
        s_deserialization_map->insert({PyLinkage::str_class(),          deserialize_as_is});
        s_deserialization_map->insert({PyLinkage::bytes_class(),        deserialize_as_is});
        s_deserialization_map->insert({PyLinkage::type(py::none()),     deserialize_as_is});
        s_deserialization_map->insert({PyLinkage::datetime_class(),     deserialize_as_is});
        s_deserialization_map->insert({PyLinkage::date_class(),         deserialize_date});
        s_deserialization_map->insert({PyLinkage::list_class(),         deserialize_list});
        s_deserialization_map->insert({PyLinkage::tuple_class(),        deserialize_tuple});
        s_deserialization_map->insert({PyLinkage::dict_class(),         deserialize_dict});

        //-- known external classes
        s_deserialization_map->insert({py::module_::import("numpy").attr("number"), deserialize_as_is});
        s_deserialization_map->insert({py::module_::import("numpy").attr("float64"), deserialize_as_is});
    }

    auto it = s_deserialization_map->find(data_type);
    return it != s_deserialization_map->end() ? it->second : nullptr;
}
