//
// Created by AMD on 2/23/2025.
//

#pragma once

#include "bcache.h"

class SimpleCacheLayer : public BCache {
protected:
    BCache*     m_parent;

public:
    explicit SimpleCacheLayer(BCache* parent) : m_parent(parent) {
        m_default_node_type = NODE_TYPE::BASIC_GRAPH;
    }

    ObjectCache*    find_or_create_object_cache(const TID& tid) override;
    BasicNode*      find_or_create_node(const TID& tid, BTrait* trait, int node_type) override;
    BasicNode*      find_or_create_node(const TID& tid, BTrait* trait, const py::args& args, int node_type) override;

    void            export_nodes();

};

