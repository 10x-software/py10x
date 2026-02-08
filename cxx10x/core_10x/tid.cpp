//
// Created by AMD on 1/23/2025.
//

#include "tid.h"
#include "btraitable_class.h"
#include "bnucleus.h"

TID::TID(BTraitableClass* cls, const py::object& id) : m_class(cls) {
    m_id = id;
    if (cls->is_custom_collection()) {
        if (!py::bool_(coll_name()))
            throw py::type_error(py::str("{}() requires _collection_name").format(cls->name()));
    }
    else if (py::bool_(coll_name()))
        throw py::type_error(py::str("{}() _collection_name may not be provided").format(cls->name()));
}

void TID::serialize_id(const py::dict& res, const bool embed) const {
    res[BNucleus::ID_TAG()] = id_value();
    if (auto cname = coll_name(); !embed && !cname.is_none())
        res[BNucleus::COLLECTION_TAG()] = cname;
}

py::object TID::deserialize_id(const py::dict& serialized_data, bool must_exist) {
    const auto XNone = PyLinkage::XNone();
    const auto id_value = PyLinkage::dict_get(serialized_data, BNucleus::ID_TAG());
    if (id_value.is(XNone)) {
        if (must_exist)
            throw py::value_error(py::str("Corrupted record - missing {} field\n{}").format(BNucleus::ID_TAG(), serialized_data));
        return py::none();
    }
    if (!py::isinstance<py::str>(id_value))
        throw py::type_error(py::str("Expected a string ID value, but found a {}").format(id_value.get_type().attr("__name__")));

    auto cname = PyLinkage::dict_get(serialized_data, BNucleus::COLLECTION_TAG());
    if (cname.is(XNone))
        cname = py::none();
    return PyLinkage::traitable_id(id_value, cname);
}
