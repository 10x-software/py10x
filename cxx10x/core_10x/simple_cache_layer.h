//
// Created by AMD on 2/23/2025.
//

#pragma once

#include "xcache.h"

class SimpleCacheLayer : public XCache {
protected:
    XCache*     m_parent;

public:
    SimpleCacheLayer() : SimpleCacheLayer(nullptr) {}
    explicit SimpleCacheLayer(XCache* parent);

    ObjectCache*    find_or_create_object_cache(const TID& tid) override;
    BasicNode*      find_or_create_node(const TID& tid, BTrait* trait, int node_type) override;
    BasicNode*      find_or_create_node(const TID& tid, BTrait* trait, const py::args& args, int node_type) override;

    void            export_nodes() override;

};

