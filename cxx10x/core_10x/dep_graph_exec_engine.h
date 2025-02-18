//
// Created by AMD on 5/21/2024.
//

#pragma once

#include <deque>
#include <unordered_map>
#include <thread>

#include "bnode.h"

class ExecStack : public std::deque<BasicNode*> {
public:
    [[nodiscard]]BasicNode * parent() const {
        return empty()? nullptr : back();
    }

    void replace_parent(BasicNode* new_parent) {
        assert(!empty());
        back() = new_parent;
    }

    void push(BasicNode* parent) {
        push_back(parent);
    }

    void pop() {
        pop_back();
    }

    class NodeGuard {
        ExecStack* m_xstack;
    public:
        NodeGuard(ExecStack* xstack, BasicNode* node) : m_xstack(xstack)    { xstack->push(node); }
        NodeGuard(const NodeGuard& ng) = default;
        ~NodeGuard()                                                        { m_xstack->pop(); }
    };

    class Placebo {
        ExecStack* m_stack;
        BasicNode* m_node;
    public:
        Placebo(ExecStack* xstack) : m_stack(xstack) {
            if (xstack) {
                auto node = new BasicNode();
                m_node = node;
                xstack->push(node);
            } else
                m_node = nullptr;
        }
        Placebo(const Placebo& p) = default;
        ~Placebo() {
            if (m_stack) {
                m_stack->pop();
                delete m_node;
            }
        }
    };
};

using XStackByThread = std::unordered_map<std::thread::id, ExecStack*>;

class DepGraphExecEngine {
    XStackByThread m_xstacks;

public:
    DepGraphExecEngine() = default;
    ExecStack* exec_stack();

    py::object eval_graph_node(BasicNode* node);        // TODO: *args, **kwargs

    ExecStack::Placebo withUpwardDependenciesOff();
};

