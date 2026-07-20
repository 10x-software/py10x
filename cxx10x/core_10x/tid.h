//
// Created by AMD on 1/23/2025.
//

#pragma once

#include <string>

#include "btraitable_class.h"
#include "py_linkage.h"

class BTraitableClass;

class PY10X_API TID {
    const BTraitableClass*    m_class;
    py::object          m_id;       //-- python's Traitable.ID instance
    mutable std::size_t m_hash;

public:
    TID(const BTraitableClass* cls, const py::object& id);
    TID(const TID& tid) = default;

    static bool is_valid(const py::object& id)                      { return !id.attr("value").is_none(); }

    void set_id_value(const py::object& id_value) const {
        m_id.attr("value") = id_value;
        m_hash = compute_hash(m_class, m_id);
    }

    [[nodiscard]] bool                  is_valid() const            { return !id_value().is_none(); }
    [[nodiscard]] const TID*            ptr() const                 { return const_cast<TID *>(this); }
    [[nodiscard]] py::object            id() const                  { return m_id; }
    [[nodiscard]] py::object            id_value() const            { return m_id.attr("value"); }
    [[nodiscard]] py::object            coll_name() const           { return m_id.attr("collection_name"); }
    [[nodiscard]] const BTraitableClass*      cls() const           { return m_class; }
    [[nodiscard]] py::object            traitable_id() const        { return PyLinkage::traitable_id(id_value(), coll_name()); }

    bool operator == (const TID& other) const {
        return m_class == other.m_class && id_value().equal(other.id_value()) && coll_name().equal(other.coll_name());
    }
    void serialize_id(const py::dict& res) const;
    static py::object deserialize_id(const py::dict& serialized_data, bool must_exist = true);

private:
    [[nodiscard]] std::size_t hash() const              { return m_hash; }
    static std::size_t compute_hash(const BTraitableClass* cls, const py::object& id) {
        std::size_t seed = 0;
        hash_combine(seed, cls);
        hash_combine(seed, py::hash(id.attr("value")));
        hash_combine(seed, py::hash(id.attr("collection_name")));
        return seed;
    }
    template <typename T>
    static void hash_combine(std::size_t& seed, T v) {
        seed ^= std::hash<T>{}(v) + 0x9e3779b9 + (seed << 6) + (seed >> 2);
    }
    friend struct std::hash<TID>;
};

template<>
struct std::hash<TID> {
    std::size_t operator()(TID const& key) const noexcept(false) {
        return key.hash();
    }
};

template<>
struct std::equal_to<TID> {
    bool operator() (const TID& a, const TID& b) const    { return a == b; }
};

