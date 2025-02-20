//
// Created by AMD on 12/16/2024.
//

#pragma once

#include <shared_mutex>

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
//      TID -> ObjectCache
//      ObjectCache: node_key -> node
//
//======================================================================================================================

using NodesWithArgs = std::unordered_map<py::args, BasicNode*>;

class TraitNodesWithArgs : public std::unordered_map<BTrait*, NodesWithArgs*> {
public:
    ~TraitNodesWithArgs();

    BasicNode* find_node(BTrait* trait, const py::args& args) const {
        auto iter = find(trait);
        if (iter == end())
            return nullptr;

        auto nwa = iter->second;
        auto it = nwa ->find(args);
        return it != nwa->end() ? it->second : nullptr;
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
        for( auto it = begin(); it != end(); ++it) {
            auto node = it->second;
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

    BasicNode*  find_node(BTrait* trait) const                                              { return m_nodes.find_node(trait); }
    BasicNode*  find_node(BTrait* trait, const py::args& args) const                        { return m_nodes_with_args.find_node(trait, args); }

    BasicNode*  find_or_create_node(BTrait* trait, int node_type)                           { return m_nodes.find_or_create_node(trait, node_type); }
    BasicNode*  find_or_create_node(BTrait* trait, int node_type, const py::args& args)     { return m_nodes_with_args.find_or_create_node(trait, node_type, args); }

    void        remove_node(BTrait* trait)                                                  { m_nodes.remove_node(trait); }
    void        remove_node(BTrait* trait, const py::args& args)                            { m_nodes_with_args.remove_node(trait, args); }

};

class BCache {
protected:
    using Data = std::unordered_map<TID, ObjectCache*>;

    static BCache   s_default;

    Data    m_data;
    int     m_default_node_type;
    BCache* m_parent;

    mutable std::shared_mutex   m_rw_mutex;

public:

    static BCache* default_cache()      { return &s_default; }

    BCache() : m_default_node_type(NODE_TYPE::BASIC), m_parent(nullptr) {}
    explicit BCache(BCache* parent) : m_default_node_type(parent->m_default_node_type), m_parent(nullptr) {}

    [[nodiscard]] std::shared_mutex* shared_mutex() const  { return &m_rw_mutex; }

    void                    register_object(BTraitable* obj);
    void                    unregister_object(BTraitable* obj);
    void                    unregister_object(const TID& tid);

    //virtual ObjectCache*    find_object_cache(const TID& tid, bool must_exists) const;
    void                    create_object_cache(const TID& tid);
    virtual ObjectCache*    find_or_create_object_cache(const TID& tid);

    virtual ObjectCache* find_object_cache(const TID& tid) const {
        auto it = m_data.find(tid);
        return it != m_data.end() ? it->second : nullptr;
    }

    bool known_object(const TID& tid) const {
        auto it = m_data.find(tid);
        return it != m_data.end();
    }

    BasicNode* find_node(const TID& tid, BTrait* trait) {
        std::shared_lock guard(m_rw_mutex);

        auto oc = find_object_cache(tid);
        if (!oc)
            return nullptr;

        return oc->find_node(trait);
    }

    BasicNode* find_node(const TID& tid, BTrait* trait, const py::args& args) {
        std::shared_lock guard(m_rw_mutex);

        auto oc = find_object_cache(tid);
        if (!oc)
            return nullptr;

        return oc->find_node(trait, args);
    }

    BasicNode* find_or_create_node(const TID& tid, BTrait* trait, int node_type = -1) {
        std::unique_lock guard(m_rw_mutex);

        auto oc = find_or_create_object_cache(tid);

        if (node_type == -1)
            node_type = m_default_node_type;

        return oc->find_or_create_node(trait, node_type);
    }

    BasicNode* find_or_create_node(const TID& tid, BTrait* trait, const py::args& args, int node_type = -1) {
        std::unique_lock guard(m_rw_mutex);

        auto oc = find_or_create_object_cache(tid);

        if (node_type == -1)
            node_type = m_default_node_type;

        return oc->find_or_create_node(trait, node_type, args);
    }

    void remove_node(const TID& tid, BTrait* trait) {
        std::unique_lock guard(m_rw_mutex);

        auto oci = m_data.find(tid);
        if (oci != m_data.end())
            oci->second->remove_node(trait);
    }

    void remove_node(const TID& tid, BTrait* trait, const py::args& args) {
        std::unique_lock guard(m_rw_mutex);

        auto oci = m_data.find(tid);
        if (oci != m_data.end())
            oci->second->remove_node(trait, args);
    }

    void set_node(BasicNode* node, const py::object& value) {
        std::unique_lock guard(m_rw_mutex);
        node->set(value);
    }

    void invalidate_node(BasicNode* node) {
        std::unique_lock guard(m_rw_mutex);
        node->invalidate();
    }

};

