//
// Created by AMD on 12/16/2024.
//

#pragma once

//#include <shared_mutex>
// AMD-1: we have decided to rid of locking the cache. As the only "user" for now is python interpreter, it can't interrupt
// the current thread within a C++ call. So, all the cache operations are thread-safe.

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

class BCache {
protected:
    using Data = std::unordered_map<TID, ObjectCache*>;

    static BCache  *s_default;

    Data    m_data;
    int     m_default_node_type = NODE_TYPE::BASIC;

    //-- (AMD-1) mutable std::shared_mutex   m_rw_mutex;

public:
    static void clear() {
        delete s_default;
        s_default = new BCache();
    }

    static BCache* default_cache()      { return s_default; }

    BCache() = default;
    virtual ~BCache() = default;

    //-- AMD-1 //[[nodiscard]] std::shared_mutex* shared_mutex() const   { return &m_rw_mutex; }
    [[nodiscard]] int default_node_type() const             { return m_default_node_type; }

    void                    register_object(BTraitable* obj);
    void                    unregister_object(BTraitable* obj);
    void                    unregister_object(const TID& tid);

    ObjectCache*            create_object_cache(const TID& tid);
    bool                    insert_object_cache(const TID& tid, ObjectCache* oc);
    virtual ObjectCache*    find_or_create_object_cache(const TID& tid);

    [[nodiscard]] virtual ObjectCache* find_object_cache(const TID& tid) const {
        auto it = m_data.find(tid);
        return it != m_data.end() ? it->second : nullptr;
    }

    [[nodiscard]] bool known_object(const TID& tid) const {
        auto it = m_data.find(tid);
        return it != m_data.end();
    }

    BasicNode* find_node(const TID& tid, BTrait* trait) {
        //-- AMD-1 //std::shared_lock guard(m_rw_mutex);

        auto oc = find_object_cache(tid);
        if (!oc)
            return nullptr;

        return oc->find_node(trait);
    }

    BasicNode* find_node(const TID& tid, BTrait* trait, const py::args& args) {
        //-- AMD-1 //std::shared_lock guard(m_rw_mutex);

        auto oc = find_object_cache(tid);
        if (!oc)
            return nullptr;

        return oc->find_node(trait, args);
    }

//    virtual BasicNode* find_or_create_node(const TID& tid, BTrait* trait, int node_type) {
//        //-- AMD-1 //std::unique_lock guard(m_rw_mutex);
//
//        auto oc = find_or_create_object_cache(tid);
//
//        if (node_type == -1)
//            node_type = m_default_node_type;
//
//        return oc->find_or_create_node(trait, node_type);
//    }

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
        //-- AMD-1 //std::unique_lock guard(m_rw_mutex);

        auto oci = m_data.find(tid);
        if (oci != m_data.end())
            oci->second->remove_node(trait);
    }

    void remove_node(const TID& tid, BTrait* trait, const py::args& args) {
        //-- AMD-1 //std::unique_lock guard(m_rw_mutex);

        auto oci = m_data.find(tid);
        if (oci != m_data.end())
            oci->second->remove_node(trait, args);
    }

    void set_node(BasicNode* node, const py::object& value) {
        //-- AMD-1 //std::unique_lock guard(m_rw_mutex);
        node->set(value);
    }

    void invalidate_node(BasicNode* node) {
        //-- AMD-1 //std::unique_lock guard(m_rw_mutex);
        node->invalidate();
    }

    virtual void export_nodes() {}
};

class PrivateCache : public BCache {
    TID*            m_owner;
    ObjectCache*    m_oc;
    BCache*         m_parent;

public:
    explicit PrivateCache(TID& tid, BCache* parent) {
        m_owner = &tid;
        m_oc = new ObjectCache();
        m_parent = parent;
    }

    ~PrivateCache() override;

    [[nodiscard]] ObjectCache*  object_cache() const { return m_oc; }

    [[nodiscard]] ObjectCache*  find_object_cache(const TID& tid) const final;
    ObjectCache*                find_or_create_object_cache(const TID& tid) final;

    bool release();
};
