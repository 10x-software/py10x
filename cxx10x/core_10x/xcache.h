//
// Created by AMD on 3/7/2025
// A new incarnation of BCache that supports all objects, including ones with invalid IDs
//
#pragma once

#include "py_linkage.h"
#include "tid.h"
#include "bnode.h"
#include "btraitable_class.h"

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

class TraitNodesWithArgs : public std::unordered_map<BTrait*, NodesWithArgs*> {
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

    BasicNode* find_node(BTrait* trait, const py::args& args) const {
        auto iter = find(trait);
        if (iter == end())
            return nullptr;

        auto nwa = iter->second;
        auto it = nwa ->find(args);
        return it != nwa->end() ? it->second : nullptr;
    }

    void insert_node(BTrait* trait, BasicNode* node, const py::args& args) {
        NodesWithArgs* nwa;

        auto iter = find(trait);
        if (iter == end()) {
            nwa = new NodesWithArgs();
            insert({trait, nwa});
        } else
            nwa = iter->second;

        nwa->insert({args, node});
    }

    BasicNode* find_or_create_node(BTrait* trait, int node_type, const py::args& args) {
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

    void remove_node(BTrait* trait, const py::args& args) {
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

class ArglessNodes : public std::unordered_map<BTrait*, BasicNode*> {
public:
    ~ArglessNodes() {
        for (auto item : *this) {
            auto node = item.second;
            node->unlink();
            delete node;
        }
        clear();
    }

    BasicNode* find_node(BTrait* trait) const {
        auto it = find(trait);
        return it != end() ? it->second : nullptr;
    }

    BasicNode* find_or_create_node(BTrait* trait, int node_type) {
        auto it = find(trait);
        if (it != end())
            return it->second;

        auto node = BasicNode::create(node_type);
        insert({ trait, node });
        return node;
    }

    void remove_node(BTrait* trait) {
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

public:

    [[nodiscard]] const ArglessNodes& argless_nodes() const                                 { return m_nodes; }
    [[nodiscard]] const TraitNodesWithArgs& nodes_with_args() const                         { return m_nodes_with_args; }

    BasicNode*  find_node(BTrait* trait) const                                              { return m_nodes.find_node(trait); }
    BasicNode*  find_node(BTrait* trait, const py::args& args) const                        { return m_nodes_with_args.find_node(trait, args); }

    void        insert_node(BTrait* trait, BasicNode* node)                                 { m_nodes.insert({trait, node}); }
    void        insert_node(BTrait* trait, BasicNode* node, const py::args& args)           { m_nodes_with_args.insert_node(trait, node, args); }
    BasicNode*  find_or_create_node(BTrait* trait, int node_type)                           { return m_nodes.find_or_create_node(trait, node_type); }
    BasicNode*  find_or_create_node(BTrait* trait, int node_type, const py::args& args)     { return m_nodes_with_args.find_or_create_node(trait, node_type, args); }

    void        remove_node(BTrait* trait)                                                  { m_nodes.remove_node(trait); }
    void        remove_node(BTrait* trait, const py::args& args)                            { m_nodes_with_args.remove_node(trait, args); }

};

class XCache {
protected:
    using Data      = std::unordered_map<TID, ObjectCache*>;
    using TmpData   = std::unordered_map<TID*, ObjectCache*>;

    static XCache*  s_default;

    Data            m_data;
    TmpData         m_tmp_data;
    int             m_default_node_type = NODE_TYPE::BASIC;

public:
    static void clear() {
        delete s_default;
        s_default = new XCache();
    }

    static XCache* default_cache()      { return s_default; }

    XCache() = default;
    virtual ~XCache() = default;

    [[nodiscard]] int default_node_type() const             { return m_default_node_type; }

    ObjectCache* create_object_cache(const TID& tid, ObjectCache* oc = nullptr) {
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

    virtual ObjectCache* find_or_create_object_cache(const TID& tid);

    [[nodiscard]] ObjectCache* find_object_cache(const TID& tid) const {
        if (tid.is_valid()) {
            auto it = m_data.find(tid);
            return it != m_data.end() ? it->second : nullptr;
        }
        auto it = m_tmp_data.find(tid.ptr());
        return it != m_tmp_data.end() ? it->second : nullptr;
    }

    ObjectCache* remove_object_cache(const TID& tid, bool discard = false) {
        ObjectCache* oc;

        if (tid.is_valid()) {
            auto it = m_data.find(tid);
            if (it == m_data.end())
                return nullptr;

            oc = it->second;
            m_data.erase(it);
        }
        else {
            auto it = m_tmp_data.find(tid.ptr());
            if (it == m_tmp_data.end())
                return nullptr;

            oc = it->second;
            m_tmp_data.erase(it);
        }

        if (discard) {
            delete oc;
            return nullptr;
        }
        return oc;
    }

    bool make_permanent(const TID& tid) {
        if (!tid.is_valid())
            throw std::runtime_error("May not call this with a temp ID");

        auto i2 = m_data.find(tid);
        if (i2 != m_data.end())
            return false;

        auto it = m_tmp_data.find(tid.ptr());
        if (it == m_tmp_data.end())
            throw std::runtime_error("Can't find this ID");

        auto oc = it->second;
        m_tmp_data.erase(it);

        m_data.insert({tid, oc});
        return true;
    }

    [[nodiscard]] bool known_object(const TID& tid) const {
        return tid.is_valid() ? m_data.find(tid) != m_data.end() : m_tmp_data.find(tid.ptr()) != m_tmp_data.end();
    }

    BasicNode* find_node(const TID& tid, BTrait* trait) {
        auto oc = find_object_cache(tid);
        if (!oc)
            return nullptr;

        return oc->find_node(trait);
    }

    BasicNode* find_node(const TID& tid, BTrait* trait, const py::args& args) {
        auto oc = find_object_cache(tid);
        if (!oc)
            return nullptr;

        return oc->find_node(trait, args);
    }

    BasicNode* find_or_create_node(const TID& tid, BTrait* trait) {
        return find_or_create_node(tid, trait, m_default_node_type);
    }

    BasicNode* find_or_create_node(const TID& tid, BTrait* trait, const py::args& args) {
        return find_or_create_node(tid, trait, args, m_default_node_type);
    }

    virtual BasicNode* find_or_create_node(const TID& tid, BTrait* trait, int node_type) {
        auto oc = find_or_create_object_cache(tid);
        return oc->find_or_create_node(trait, node_type);
    }

    virtual BasicNode* find_or_create_node(const TID& tid, BTrait* trait, const py::args& args, int node_type) {
        auto oc = find_or_create_object_cache(tid);
        return oc->find_or_create_node(trait, node_type, args);
    }

    void remove_node(const TID& tid, BTrait* trait) {
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

    void remove_node(const TID& tid, BTrait* trait, const py::args& args) {
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

    virtual void export_nodes() {}
};
