//
// Created by AMD on 5/18/2024.
//
#pragma once

#include "py_support.h"
#include "bnode.h"
#include "btrait.h"
#include "object_cache.h"
#include "brc.h"

namespace py = pybind11;

class BTraitable;

using CacheByEID    = std::unordered_map<EID, ObjectCache*>;
using CacheByClass  = std::unordered_map<py::object, CacheByEID*>;
using CacheByObject = std::unordered_map<BTraitable*, ObjectCache*>;


class Cache {
protected:
    CacheByClass    m_by_class;
    CacheByObject   m_by_object;

public:
    Cache() = default;

    ObjectCache*    find_object_cache(BTraitable& obj) const;
    ObjectCache*    find_or_create_object_cache(BTraitable& obj);

//    BasicNode*      find_node(const py::object& cls, const EID& eid, BTrait* trait) const;
//    BasicNode*      find_or_create_node(const py::object& cls, const EID& eid, const py::object& traitable, BTrait* trait);

};


