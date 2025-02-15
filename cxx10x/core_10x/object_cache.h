//
// Created by AMD on 6/19/2024.
//

#pragma once

#include <unordered_map>

#include "py_support.h"
#include "bnode.h"

class BTrait;
class BTraitable;

using NodesByTrait  = std::unordered_map<BTrait*, BasicNode*>;

class ObjectCache : NodesByTrait {
    protected:
        int         m_default_node_type;
        int         m_refcount;
        //py::object  m_traitable;

    public:
        explicit ObjectCache(int def_node_type = NODE_TYPE::BASIC) : NodesByTrait() {
            //m_traitable = traitable;
            m_default_node_type = def_node_type;
            m_refcount = 1;
        }

        void link() {
            m_refcount += 1;
        }

        void unlink() {
            m_refcount -=1;
            if (!m_refcount)
                clear();
        }

        BasicNode*  find_node(BTrait* trait) const {
            auto it = find(trait);
            return it != end()? it->second : nullptr;
        }

        BasicNode* find_or_create_node(BTrait* trait, int node_type = -1) {
            if(node_type == -1)
                node_type = m_default_node_type;

            auto it = find(trait);
            if (it != end())
                return it->second;

            auto node = BasicNode::create(node_type);
            insert({ trait, node });
            return node;
        }

        void invalidate_value(BTrait* trait) const {
            auto node = find_node(trait);
            if (node)
                node->invalidate();
        }

        void set_value_as_is(BTrait* trait, const py::object& value) {
            auto node = find_or_create_node(trait);
            node->set(value);
        }


};


