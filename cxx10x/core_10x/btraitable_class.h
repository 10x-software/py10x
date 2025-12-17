//
// Created by AMD on 1/20/2025.
//

#pragma once

#include "bprocess_context.h"
#include "py_linkage.h"
#include "eval_once.h"

class BTrait;

class TID;

class BUiClass;

class BTraitableClass {
protected:
    py::object      m_py_class;
    py::str         m_name;
    py::dict        m_trait_dir;
    bool            m_custom_collection;

    BUiClass*       m_ui_class = nullptr;

    eval_once_const(BTraitableClass, bool, is_storable);
    eval_once_const(BTraitableClass, bool, is_id_endogenous);
    eval_once_const(BTraitableClass, bool, is_anonymous);

    [[nodiscard]] bool may_exist_in_store() const {
        return is_storable() && !is_anonymous() && !BProcessContext::PC.flags_on(BProcessContext::CACHE_ONLY);
    }

    bool    is_storable_get() const;
    bool    is_id_endogenous_get() const;
    bool    is_anonymous_get() const;

    BUiClass* bui_class();

public:

    explicit BTraitableClass(const py::object& py_cls) {
        m_py_class = py_cls;
        m_name = py_cls.attr("__qualname__");
        m_trait_dir = m_py_class.attr("s_dir");
        m_custom_collection = m_py_class.attr("s_custom_collection").cast<bool>();
    }

    //~BTraitableClass();

    py::object serialize_class_id() const {
        return m_py_class.attr("serialize_class_id")();
    }

    py::object deserialize_class_id(const py::object& class_id) const {
        return m_py_class.attr("deserialize_class_id")(class_id);
    }

   // bool check_coll_kwargs(py::dict& coll_kwargs);

    const py::object& py_class() const {
        return m_py_class;
    }

    const py::str& name() const {
        return m_name;
    }

    bool is_custom_collection() const {
        return m_custom_collection;
    }

    const py::dict& trait_dir() const {
        return m_trait_dir;
    }

    BTrait*     find_trait(const py::object& trait_name) const;

    static bool instance_in_cache(const TID& tid);
    bool        instance_in_store(const TID& tid) const;

    bool instance_exists(const TID& tid) const {
        return instance_in_cache(tid) || instance_in_store(tid);
    }

    [[nodiscard]] bool is_bundle() const {
        return m_py_class.attr("is_bundle")().cast<bool>();
    }

    py::object get_field(const py::dict& serialized_data, const py::object& field_name, bool must_exist = true) const {
        auto value = PyLinkage::dict_get(serialized_data, field_name);
        if (!value.is(PyLinkage::XNone()))
            return value;

        if (must_exist)
            throw py::value_error(py::str("{} - {} field is missing in {}").format(name(), field_name, serialized_data));

        return py::none();
    }

    py::object load(const py::object& id);
    py::object load_data(const py::object& id) const;

};


