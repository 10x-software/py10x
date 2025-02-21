//
// Created by AMD on 1/23/2025.
//

#pragma once

#include <string>

#include "py_linkage.h"

class BTraitableClass;

class TID {
    BTraitableClass*    m_class;
    py::object          m_id;

public:
    TID() : m_class(nullptr)                                        {}
    TID(BTraitableClass* cls, const py::object& id) : m_class(cls)  { m_id = id; }

    void set(BTraitableClass* cls, const py::object& id)            { m_class = cls; m_id = id; }

    [[nodiscard]] const py::object&     id() const                  { return m_id; }
    [[nodiscard]] BTraitableClass*      cls() const                 { return m_class; }

    bool operator == (const TID& other) const {
        return m_class == other.m_class && m_id.equal(other.m_id);
    }

};

template<>
struct std::hash<TID> {
    std::size_t operator() (TID const& key) const noexcept {
        std::size_t seed = 0;
        seed ^= (size_t) key.cls() + 0x9e3779b9 + (seed << 6) + (seed >> 2);
        seed ^= py::hash(key.id())+ 0x9e3779b9 + (seed << 6) + (seed >> 2);
        return seed;
    }
};

template<>
struct std::equal_to<TID> {
    bool operator() (const TID& a, const TID& b) const    { return a == b; }
};

