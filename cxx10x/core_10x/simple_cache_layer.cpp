//
// Created by AMD on 2/23/2025.
//

#include "simple_cache_layer.h"
#include "thread_context.h"


SimpleCacheLayer::SimpleCacheLayer(BCache* parent) {
    if (!parent)
        parent = ThreadContext::current_cache();

    m_parent = parent;
    m_default_node_type = NODE_TYPE::BASIC_GRAPH;
}

ObjectCache* SimpleCacheLayer::find_or_create_object_cache(const TID &tid) {
    auto oc = find_object_cache(tid);
    if (oc)
        return oc;

    {
        std::shared_lock guard(*m_parent->shared_mutex());
        oc = m_parent->find_object_cache(tid);
    }

    if (!oc)    //-- the object cache is not there, we have a lazy tid reference - let's load the object
        tid.cls()->load(tid.id(), true);

    //-- create it, if any
    return create_object_cache(tid);
}

BasicNode* SimpleCacheLayer::find_or_create_node(const TID& tid, BTrait* trait, int node_type) {
    std::unique_lock guard(m_rw_mutex);

    auto oc = find_or_create_object_cache(tid);
    auto node = oc->find_node(trait);
    if (node)
        return node;

    auto my_node = BasicNode::create(node_type);
    node = m_parent->find_node(tid, trait);
    if (node && node->is_set())
        my_node->set_imported(node->value());

    oc->insert_node(trait, my_node);
    return my_node;
}

BasicNode* SimpleCacheLayer::find_or_create_node(const TID& tid, BTrait* trait, const py::args& args, int node_type) {
    std::unique_lock guard(m_rw_mutex);

    auto oc = find_or_create_object_cache(tid);
    auto node = oc->find_node(trait, args);
    if (node)
        return node;

    auto my_node = BasicNode::create(node_type);
    node = m_parent->find_node(tid, trait, args);
    if (node && node->is_set())
        my_node->set_imported(node->value());

    oc->insert_node(trait, my_node, args);
    return my_node;
}

//-- Export all BASIC_GRAPH nodes set in this layer
void SimpleCacheLayer::export_nodes() {
    std::shared_lock read_guard(m_rw_mutex);
    std::unique_lock write_guard(*m_parent->shared_mutex());

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
