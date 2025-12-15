//
// Created by AMD on 1/23/2025.
//

#pragma once

#include <string>

#include "py_linkage.h"

class BTraitableClass;

class TID {
    BTraitableClass*    m_class;
    py::object          m_id;       //-- python's Traitable.ID instance

public:
    TID(BTraitableClass* cls, const py::object& id);
    TID(const TID& tid) = default;

    static bool is_valid(const py::object& id)                      { return !id.attr("value").is_none(); }

    void set_id_value(const py::object& id_value) const             { m_id.attr("value") = id_value; }

    [[nodiscard]] bool                  is_valid() const            { return !id_value().is_none(); }
    [[nodiscard]] TID*                  ptr() const                 { return const_cast<TID *>(this); }
    [[nodiscard]] py::object            id() const                  { return m_id; }
    [[nodiscard]] py::object            id_value() const            { return m_id.attr("value"); }
    [[nodiscard]] py::object            coll_name() const           { return m_id.attr("collection_name"); }
    [[nodiscard]] BTraitableClass*      cls() const                 { return m_class; }

    bool operator == (const TID& other) const {
        return m_class == other.m_class && id_value().equal(other.id_value());
    }

    void serialize_id(py::dict& res, bool embed);
    static py::object deserialize_id(const py::dict& serialized_data, bool must_exist = true);

};

template<>
struct std::hash<TID> {
    std::size_t operator() (TID const& key) const noexcept {
        std::size_t seed = 0;
        seed ^= (size_t) key.cls() + 0x9e3779b9 + (seed << 6) + (seed >> 2);
        seed ^= py::hash(key.id_value())+ 0x9e3779b9 + (seed << 6) + (seed >> 2);
        return seed;
    }
};

template<>
struct std::equal_to<TID> {
    bool operator() (const TID& a, const TID& b) const    { return a == b; }
};

