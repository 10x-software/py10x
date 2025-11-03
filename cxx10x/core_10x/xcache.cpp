//
// Created by AMD on 3/7/2025.
//

#include "xcache.h"

XCache* XCache::s_default = new XCache();

ObjectCache* XCache::find_or_create_object_cache(const TID& tid,bool load_if_missing) {
    auto oc = find_object_cache(tid);
    if (oc)
        return oc;

    if (m_parent) {
        oc = m_parent->find_object_cache(tid);
        if (oc)
            return new_object_cache(tid);
    }

    //-- The object cache doesn't exist, we have a lazy reference - let's load the object, if any
    oc = new_object_cache(tid);
    if (load_if_missing)
        tid.cls()->load(tid.id());
    return oc;
}

BasicNode* XCache::find_or_create_node(const TID& tid, BTrait* trait, int node_type) {
    auto oc = find_or_create_object_cache(tid, true);
    auto node = oc->find_node(trait);
    if (!node) {
        node = BasicNode::create(node_type);
        oc->insert_node(trait, node);

        if (m_parent) {
            auto parent_node = m_parent->find_node(tid, trait);
            if (parent_node && parent_node->is_set())
                node->set_imported(parent_node->value());
        }
    }
    return node;
}

BasicNode* XCache::find_or_create_node(const TID& tid, BTrait* trait, int node_type, const py::args& args) {
    auto oc = find_or_create_object_cache(tid,true);
    auto node = oc->find_node(trait, args);
    if (!node) {
        node = BasicNode::create(node_type);
        oc->insert_node(trait, node, args);

        if (m_parent) {
            auto parent_node = m_parent->find_node(tid, trait, args);
            if (parent_node && parent_node->is_set())
                node->set_imported(parent_node->value());
        }
    }
    return node;
}

void XCache::export_nodes() const {
    auto dst_node_type = m_parent->default_node_type();
    for (const auto& oc_item : m_data) {
        const auto& tid = oc_item.first;
        auto oc = oc_item.second;

        auto dst_oc = m_parent->create_object_cache(tid);
        //-- argsless nodes
        for (auto item : oc->argless_nodes()) {
            auto trait = item.first;
            auto node = item.second;
            if (node->node_type() != NODE_TYPE::BASIC_GRAPH || !node->is_set())
                continue;

            auto dst_node = dst_oc->find_or_create_node(trait, dst_node_type);
            dst_node->set(node->value());
        }

        //-- nodes with args
        for (auto item : oc->nodes_with_args()) {
            auto trait = item.first;
            for (const auto& i: *item.second) {
                auto args = i.first;
                auto node = i.second;
                if (node->node_type() != NODE_TYPE::BASIC_GRAPH || !node->is_set())
                    continue;

                auto dst_node = dst_oc->find_or_create_node(trait, dst_node_type, args);
                dst_node->set(node->value());
            }
        }
    }
}