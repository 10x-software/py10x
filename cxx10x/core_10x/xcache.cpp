//
// Created by AMD on 3/7/2025.
//

#include "xcache.h"

#include "btraitable.h"

XCache* XCache::s_default = new XCache();

XCache *XCache::find_origin_cache(const TID &tid) {
    auto parent = this;
    while(parent) {
        if (const auto oc = parent->find_object_cache(tid))
            return parent;
        parent = parent->m_parent;
    }
    return nullptr;
}

ObjectCache * XCache::find_object_cache_and_load(const BTraitable *obj) const {
    // find an existing object cache in this cache or in parents
    // if none found, handle lazy load (if applicable)
    // return nullptr unless found (or created) in *this* cache


    const auto &tid = obj->tid();
    const auto origin_cache = obj->origin_cache();
    auto parent = this;

    while(parent) {
        if (parent == origin_cache)
            break;
        parent = parent->m_parent;
    }

    if (!parent)
        throw py::type_error(py::str("{}.{} - origin cache not reachable").format(obj->class_name(), obj->id_value()));

    if (origin_cache->lazy_load_flags(tid) & XCache::LOAD_REQUIRED) {
        obj->lazy_load();
    }

    return find_object_cache(tid);
}

ObjectCache * XCache::find_or_create_object_cache(BTraitable *obj) {
    if (const auto oc = find_object_cache_and_load(obj))
        return oc;
    return new_object_cache(obj->tid());
}

BasicNode* XCache::find_or_create_node(BTraitable *obj, const BTrait* trait, int node_type, const bool import_from_parents) {
    const auto oc = find_or_create_object_cache(obj);
    auto node = oc->find_node(trait);
    if (!node) {
        node = BasicNode::create(node_type);
        oc->insert_node(trait, node);

        if (!import_from_parents)
            return node;

        const auto parent_node = find_set_or_invalid_node_in_parents(obj->tid(), trait);
        if (!parent_node || !parent_node->is_valid())
            return node;

        node->set_imported(parent_node->value());
    }
    return node;
}

BasicNode* XCache::find_or_create_node(BTraitable *obj, const BTrait* trait, int node_type, const py::args& args, const bool import_from_parents) {
    const auto oc = find_or_create_object_cache(obj);
    auto node = oc->find_node(trait, args);
    if (!node) {
        node = BasicNode::create(node_type);
        oc->insert_node(trait, node, args);

        if (!import_from_parents)
            return node;

        const auto parent_node = find_set_or_invalid_node_in_parents(obj->tid(), trait, args);
        if (!parent_node || !parent_node->is_valid())
            return node;

        node->set_imported(parent_node->value());
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