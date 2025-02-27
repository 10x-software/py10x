//
// Created by AMD on 5/22/2024.
//

#include "bnode.h"

BasicNode* BasicNode::create(int node_type) {
    switch (node_type) {
        case NODE_TYPE::BASIC:          return new BasicNode();
        case NODE_TYPE::TREE:           return new TreeNode();
        case NODE_TYPE::BASIC_GRAPH:    return new BasicGraphNode();
        case NODE_TYPE::UI:             return new BUiNode();
        case NODE_TYPE::GRAPH:          return new GraphNode();     // TODO: must take care of the node "address" data

        default:
            throw py::type_error(py::str("Unknown node type {}").format(node_type));
    }
}