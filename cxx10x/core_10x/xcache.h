//
// Created by AMD on 3/7/2025
// A new incarnation of BCache that supports all objects, including ones with invalid IDs
//
#pragma once

#include <ranges>

#include "py_linkage.h"
#include "tid.h"
#include "bnode.h"
#include "btraitable_class.h"
#include "btraitable_processor.h"
#include "debug.h"

class BTrait;
class BTraitable;

//======================================================================================================================
//  Cache Structure
//
//  Note:
//      while we could map a node by a single key, we decided to have a double map: first by Traitable ID (its class
//      and ID) and then by Trait and possible args. This allows to clean up nodes of a Traitable when it goes
//      out of scope.
//
//  Cache:
//      TID  -> ObjectCache - object caches for permanent objects
//      TID* -> ObjectCache - object caches for temporary objects (with invalid IDs)
//      ObjectCache: node_key -> node
//
//======================================================================================================================

using NodesWithArgs = std::unordered_map<py::args, BasicNode*>;

class TraitNodesWithArgs : public std::unordered_map<const BTrait*, NodesWithArgs*> {
public:
    ~TraitNodesWithArgs() {
        for (auto item : *this) {
            auto nodes = item.second;
            for (const auto& i : *nodes) {
                auto node = i.second;
                node->unlink();
                delete node;
            }
            delete nodes;
        }
        clear();
    }

    BasicNode* find_node(const BTrait* trait, const py::args& args) const {
        auto iter = find(trait);
        if (iter == end())
            return nullptr;

        auto nwa = iter->second;
        auto it = nwa->find(args);
        return it != nwa->end() ? it->second : nullptr;
    }

    void insert_node(const BTrait* trait, BasicNode* node, const py::args& args) {
        NodesWithArgs* nwa;

        auto iter = find(trait);
        if (iter == end()) {
            nwa = new NodesWithArgs();
            insert({trait, nwa});
        } else
            nwa = iter->second;

        nwa->insert({args, node});
    }

    BasicNode* find_or_create_node(const BTrait* trait, int node_type, const py::args& args) {
        NodesWithArgs* nwa;

        auto iter = find(trait);
        if (iter == end()) {
            nwa = new NodesWithArgs();
            insert({ trait, nwa });
            auto node = BasicNode::create(node_type);
            nwa->insert({ args, node });
            return node;
        }

        nwa = iter->second;
        auto it = nwa->find(args);
        if (it != nwa->end())
            return it->second;

        auto node = BasicNode::create(node_type);
        nwa->insert({ args, node });
        return node;
    }

    void remove_node(const BTrait* trait, const py::args& args) {
        auto iter = find(trait);
        if (iter == end())
            return;

        auto nwa = iter->second;
        auto it = nwa->find(args);
        if (it == nwa->end())
            return;

        auto node = it->second;
        node->unlink();
        delete node;
        nwa->erase(it);
    }
};

class ArglessNodes : public std::unordered_map<const BTrait*, BasicNode*> {
public:
    ~ArglessNodes() {
        for (auto item : *this) {
            auto node = item.second;
            node->unlink();
            delete node;
        }
        clear();
    }

    BasicNode* find_node(const BTrait* trait) const {
        auto it = find(trait);
        return it != end() ? it->second : nullptr;
    }

    BasicNode* find_or_create_node(const BTrait* const trait, const int node_type) {
        auto it = find(trait);
        if (it != end())
            return it->second;

        auto node = BasicNode::create(node_type);
        insert({ trait, node });
        return node;
    }

    void remove_node(const BTrait* trait) {
        auto it = find(trait);
        if (it == end())
            return;

        auto node = it->second;
        node->unlink();
        delete node;
        erase(it);
    }
};

class ObjectCache {
    ArglessNodes        m_nodes;
    TraitNodesWithArgs  m_nodes_with_args;
    unsigned            m_lazy_load_flags = 0;

public:

    [[nodiscard]] const ArglessNodes& argless_nodes() const                                     { return m_nodes; }
    [[nodiscard]] const TraitNodesWithArgs& nodes_with_args() const                             { return m_nodes_with_args; }
    [[nodiscard]] unsigned lazy_load_flags() const                                              { return m_lazy_load_flags; }

    BasicNode*  find_node(const BTrait* trait) const                                            { return m_nodes.find_node(trait); }
    BasicNode*  find_node(const BTrait* trait, const py::args& args) const                      { return m_nodes_with_args.find_node(trait, args); }

    void        insert_node(const BTrait* trait, BasicNode* node)                               { m_nodes.insert({trait, node}); }
    void        insert_node(const BTrait* trait, BasicNode* node, const py::args& args)         { m_nodes_with_args.insert_node(trait, node, args); }
    BasicNode*  find_or_create_node(const BTrait* trait, int node_type)                         { return m_nodes.find_or_create_node(trait, node_type); }
    BasicNode*  find_or_create_node(const BTrait* trait, int node_type, const py::args& args)   { return m_nodes_with_args.find_or_create_node(trait, node_type, args); }

    void        remove_node(const BTrait* trait)                                                { m_nodes.remove_node(trait); }
    void        remove_node(const BTrait* trait, const py::args& args)                          { m_nodes_with_args.remove_node(trait, args); }

    void        set_lazy_load_flags(const unsigned lazy_load_flags)                             { m_lazy_load_flags |= lazy_load_flags; }
    void        clear_lazy_load_flags(const unsigned lazy_load_flags)                           { m_lazy_load_flags &= ~lazy_load_flags; }
};

class XCache {
protected:
    using Data      = std::unordered_map<TID, ObjectCache*>;
    using TmpData   = std::unordered_map<const TID*, ObjectCache*>;

    static XCache*  s_default;

    XCache*         m_parent = nullptr;
    Data            m_data;
    TmpData         m_tmp_data;
    int             m_default_node_type = NODE_TYPE::BASIC;
    ObjectCache* _find_or_create_object_cache(const TID& tid, ObjectCache* oc = nullptr) {
        if (tid.is_valid()) {
            auto it = m_data.find(tid);
            if (it != m_data.end())
                return it->second;

            if (!oc)
                oc = new ObjectCache();
            m_data.insert({tid, oc});
            return oc;
        }

        auto it = m_tmp_data.find(tid.ptr());
        if (it != m_tmp_data.end())
            return it->second;

        if (!oc)
            oc = new ObjectCache();
        m_tmp_data.insert({tid.ptr(), oc});
        return oc;
    }
public:
    // lazy load flags flags
    static constexpr unsigned   LOAD_REQUIRED                = 64;
    static constexpr unsigned   MUST_EXIST_IN_STORE          = 128;
    static constexpr unsigned   LOAD_REV_ONLY                = 256;
    static constexpr unsigned   LOAD_REQUIRED_MUST_EXIST     = LOAD_REQUIRED|MUST_EXIST_IN_STORE;
    [[nodiscard]] unsigned lazy_load_flags(const TID& tid) const {
        if (!tid.is_valid())
            return 0;
        const ObjectCache * oc = find_object_cache(tid);
        if (!oc)
            throw py::value_error(py::str("{}/{} - no object cache found in origin cache").format(tid.cls()->name(), tid.id_value()));
        return oc->lazy_load_flags();
    }

    void set_lazy_load_flags(const TID& tid, const unsigned lazy_load_flags) {
        if (!tid.is_valid())
            throw py::value_error("Cannot set lazy load flags for temporary object");

       _find_or_create_object_cache(tid)->set_lazy_load_flags(lazy_load_flags);
    }

    void clear_lazy_load_flags(const TID & tid, unsigned lazy_load_flags) {
        if (!tid.is_valid())
            throw py::value_error("Cannot set lazy load flags for temporary object");
        _find_or_create_object_cache(tid)->clear_lazy_load_flags(lazy_load_flags);
    }

    static void clear() {
        delete s_default;
        s_default = new XCache();
    }

    static XCache* default_cache()      { return s_default; }

    explicit XCache(XCache* parent = nullptr) : m_parent(parent)     {}

    [[nodiscard]] int default_node_type() const             { return m_default_node_type; }
    void set_default_node_type(int node_type)               { m_default_node_type = node_type; }

    ObjectCache* new_object_cache(const TID& tid) {
        auto oc = new ObjectCache();
        if (tid.is_valid())
            m_data.insert({tid, oc});
        else
            m_tmp_data.insert({tid.ptr(), oc});
        return oc;
    }

    XCache *find_origin_cache(const TID &tid);

    BasicNode* find_set_or_invalid_node_in_parents(const TID& tid, const BTrait* trait, const bool parents_only=true) const {
        auto parent = parents_only ? m_parent : this;
        while(parent) {
            if (const auto node = parent->find_node(tid, trait)) {
                if (node->is_set() || !node->is_valid()) {
                    return node;
                }
            }
            parent = parent->m_parent;
        }
        return nullptr;
    }
    BasicNode* find_set_or_invalid_node_in_parents(const TID& tid, const BTrait* trait, const py::args& args, const bool parents_only=true) const {
        auto parent = parents_only ? m_parent : this;
        while(parent) {
            if (const auto node = parent->find_node(tid, trait, args)) {
                if (node->is_set() || !node->is_valid())
                    return node;
            }
            parent = parent->m_parent;
        }
        return nullptr;
    }
    ObjectCache* find_or_create_object_cache(BTraitable *obj);

    //-- Lookup in this cache ONLY! (ignore the parent)
    [[nodiscard]] ObjectCache* find_object_cache(const TID& tid) const {
        if (tid.is_valid()) {
            auto it = m_data.find(tid);
            return it != m_data.end() ? it->second : nullptr;
        }
        auto it = m_tmp_data.find(tid.ptr());
        return it != m_tmp_data.end() ? it->second : nullptr;
    }

    void remove_temp_object_cache(const TID& tid) {
        auto it = m_tmp_data.find(tid.ptr());
        if (it == m_tmp_data.end())
            return;

        auto oc = it->second;
        m_tmp_data.erase(it);
        delete oc;
    }

    ObjectCache* remove_object_cache(const TID& tid, const bool discard = false) {
        auto it = m_data.find(tid);
        if (it == m_data.end())
            return nullptr;

        const auto oc = it->second;
        m_data.erase(it);

        if (discard) {
            delete oc;
            return nullptr;
        }
        return oc;
    }

    bool make_permanent(const TID& tid) {
        if (!tid.is_valid())
            throw std::runtime_error("May not call this with a temp ID");

        if ( m_data.contains(tid) )
            return false; // already permanent

        const auto it = m_tmp_data.find(tid.ptr());
        if (it == m_tmp_data.end())
            throw std::runtime_error("Can't find this ID");

        m_data.insert({tid, it->second});
        m_tmp_data.erase(it);

        return true;
    }

//    [[nodiscard]] bool known_object(const TID& tid) const {
//        if (tid.is_valid()) {
//            auto it = m_data.find(tid);
//            return it != m_data.end();
//        }
//        auto it = m_tmp_data.find(tid.ptr());
//        return it != m_tmp_data.end();
//    }

    //-- Lookup in this cache ONLY! (ignore the parent)
    BasicNode* find_node(const TID& tid, const BTrait* trait) const {
        auto oc = find_object_cache(tid);
        if (!oc)
            return nullptr;

        return oc->find_node(trait);
    }

    //-- Lookup in this cache ONLY! (ignore the parent)
    BasicNode* find_node(const TID& tid, const BTrait* trait, const py::args& args) const {
        auto oc = find_object_cache(tid);
        if (!oc)
            return nullptr;

        return oc->find_node(trait, args);
    }

    BasicNode* find_or_create_node(BTraitable *obj, const BTrait* trait, const bool import_from_parents) {
        return find_or_create_node(obj, trait, m_default_node_type, import_from_parents);
    }

    BasicNode* find_or_create_node(BTraitable *obj, const BTrait* trait, const py::args& args, const bool import_from_parents) {
        return find_or_create_node(obj, trait, m_default_node_type, args, import_from_parents);
    }

    BasicNode* find_or_create_node(BTraitable *obj, const BTrait* trait, int node_type, bool import_from_parents);
    BasicNode* find_or_create_node(BTraitable *obj, const BTrait* trait, int node_type, const py::args& args, bool import_from_parents);

    void remove_node(const TID& tid, const BTrait* trait) {
        if (tid.is_valid()) {
            auto oci = m_data.find(tid);
            if (oci != m_data.end())
                oci->second->remove_node(trait);
        } else {
            auto oci = m_tmp_data.find(tid.ptr());
            if (oci != m_tmp_data.end())
                oci->second->remove_node(trait);
        }
    }

    void remove_node(const TID& tid, const BTrait* trait, const py::args& args) {
        if (tid.is_valid()) {
            auto oci = m_data.find(tid);
            if (oci != m_data.end())
                oci->second->remove_node(trait, args);
        } else {
            auto oci = m_tmp_data.find(tid.ptr());
            if (oci != m_tmp_data.end())
                oci->second->remove_node(trait, args);
        }
    }

    void export_nodes() const;
};
