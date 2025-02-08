//
// Created by AMD on 6/20/2024.
//
#include <deque>
#include <unordered_map>
#include <thread>

#include "bnode.h"

class ExecStack : public std::deque<BasicNode*> {
public:
    [[nodiscard]]BasicNode *parent() const {
        return empty() ? nullptr : back();
    }

    void replace_parent(BasicNode *new_parent) {
        assert(!empty());
        back() = new_parent;
    }

    void push(BasicNode *parent) {
        push_back(parent);
    }

    void pop() {
        pop_back();
    }
};

class NodeGuard {
    ExecStack* m_xstack;
public:
    NodeGuard(ExecStack* xstack, BasicNode* node) : m_xstack(xstack)    { xstack->push(node); }
    ~NodeGuard()                                                        { m_xstack->pop(); }
};

class UpwardDepsOff {
    ExecStack* m_stack;
    BasicNode* m_node;
public:
    UpwardDepsOff(ExecStack* xstack) : m_stack(xstack) {
        if (xstack) {
            auto node = new BasicNode();
            m_node = node;
            xstack->push(node);
        } else
            m_node = nullptr;
    }

    ~UpwardDepsOff() {
        if (m_stack) {
            m_stack->pop();
            delete m_node;
        }
    }
};
