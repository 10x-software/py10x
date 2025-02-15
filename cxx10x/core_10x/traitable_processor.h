//
// Created by AMD on 7/2/2024.
//

#pragma once

#include <deque>
#include <unordered_map>
#include <thread>

#include "py_support.h"
#include "exec_stack.h"

class BasicNode;
/*
class ExecStack : public std::deque<BasicNode*> {
public:
    [[nodiscard]]
    BasicNode*  parent() const                          { return empty() ? nullptr : back(); }

    void        replace_parent(BasicNode *new_parent)   { assert(!empty()); back() = new_parent; }
    void        push(BasicNode *parent)                 { push_back(parent); }
    void        pop()                                   { pop_back(); }
};

class NodeGuard {
    ExecStack* m_xstack;
public:
    NodeGuard(ExecStack* xstack, BasicNode* node) : m_xstack(xstack)    { xstack->push(node); }
    NodeGuard(const NodeGuard& ng) = default;
    ~NodeGuard()                                                        { m_xstack->pop(); }
};
*/

class Placebo {
    ExecStack* m_stack;
    BasicNode* m_node;
public:
    Placebo(ExecStack* xstack);
    Placebo(const Placebo& p) = default;
    ~Placebo();
};

using XStackByThread = std::unordered_map<std::thread::id, ExecStack*>;

class BTraitable;
class BTrait;

class BTraitableProcessor {
public:
    static const unsigned  DEBUG            = 0x1;
    static const unsigned  CONVERT_VALUES   = 0x2;
    static const unsigned  ON_GRAPH         = 0x4;

    using ProcessorStack = std::deque<BTraitableProcessor*>;
    static ProcessorStack s_stack;

    static BTraitableProcessor* current()   { return s_stack.empty() ? nullptr : s_stack.back(); }

    static BTraitableProcessor* create(unsigned flags);

    virtual py::object  get_trait_value(BTraitable* obj, BTrait* trait);
    virtual py::object  get_trait_value_if_valid(BTraitable* obj, BTrait* trait);
    virtual py::object  set_trait_value(BTraitable* obj, BTrait* trait, const py::object& value);
    virtual void        invalidate_trait_value(BTraitable* obj, BTrait* trait);
};

class BTraitableProcessorContext {
public:
    BTraitableProcessorContext(unsigned flags);
    ~BTraitableProcessorContext();
};

