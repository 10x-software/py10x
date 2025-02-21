//
// Created by AMD on 1/20/2025.
//

#pragma once

#include "py_linkage.h"
#include "eval_once.h"

class BTrait;

class TID;

class BTraitableClass {
    py::object      m_py_class;
    py::str         m_name;
    py::dict        m_trait_dir;

    eval_once(BTraitableClass, bool, is_storable);
    eval_once(BTraitableClass, bool, is_id_endogenous);

    bool    is_storable_get();
    bool    is_id_endogenous_get();

public:

    explicit BTraitableClass(const py::object& py_cls) {
        m_py_class = py_cls;
        m_name = py_cls.attr("__qualname__");
        m_trait_dir = m_py_class.attr("s_dir");
    }

    const py::object& py_class() const {
        return m_py_class;
    }

    const py::str& name() const {
        return m_name;
    }

    const py::dict& trait_dir() const {
        return m_trait_dir;
    }

    bool known_trait(const py::object& trait_name) const {
        return trait_dir().contains(trait_name);
    }

    BTrait*     find_trait(const py::object& trait_name) const;

    static bool instance_in_cache(const TID& tid);
    bool        instance_in_store(const TID& tid) const;

    bool instance_exists(const TID& tid) const {
        return instance_in_cache(tid) || instance_in_store(tid);
    }

    py::object  deserialize(const py::object& serialized_data, bool reload);
    py::object  deserialize_object(const py::dict& serialized_data, bool reload);
    py::object  load(const py::object& id, bool reload);
    py::object  load_data(const py::object& id) const;

};


