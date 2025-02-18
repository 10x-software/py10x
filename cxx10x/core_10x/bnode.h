//
// Created by AMD on 5/18/2024.
//
#pragma once

#include <set>

#include "py_linkage.h"

const unsigned STATE_VALID          = 0x1;
const unsigned STATE_SET            = 0x2;
const unsigned STATE_VALID_AND_SET  = STATE_VALID | STATE_SET;

class NODE_TYPE {
public:
    inline static const int BASIC          = 0;
    inline static const int TREE           = 1;
    inline static const int BASIC_GRAPH    = 2;
    inline static const int GRAPH          = 3;
};

class BasicNode {
protected:
    using NodeSet = std::set<BasicNode*>;

    py::object  m_value;
    unsigned    m_state;

public:
    static BasicNode* create(int node_type);

    BasicNode() : m_value(PyLinkage::XNone()), m_state(0x0)  {}
    virtual ~BasicNode() = default;

    [[nodiscard]] bool is_valid() const { return m_state & STATE_VALID; }
    [[nodiscard]] bool is_set() const   { return m_state & STATE_SET; }
    [[nodiscard]] bool is_valid_and_not_set() const { return (m_state & STATE_VALID) && ((m_state & STATE_SET) == 0x0); }

    [[nodiscard]] py::object value() const      { return m_value; }

    void assign_value(const py::object& v)      { m_value = v; }
    void assign(const py::object& v)            { assign_value(v); m_state |= STATE_VALID; }

    virtual void set(const py::object& v )      { m_value = v; m_state |= STATE_VALID_AND_SET; }
    virtual void invalidate()                   { m_value = PyLinkage::XNone(); m_state &= ~STATE_VALID_AND_SET; }

    virtual NodeSet* children()                 { return nullptr; }
    virtual void clear_children()               {}
    virtual void remove_child(BasicNode* c)     {}
    virtual void add_child(BasicNode* c)        {}
    virtual void unlink_child(BasicNode* c)     {}
    virtual void unlink_children()              {}

    virtual NodeSet* parents()                  { return nullptr; }
    virtual void clear_parents()                {}
    virtual void remove_parent(BasicNode* p)    {}
    virtual void add_parent(BasicNode* p)       {}
    virtual void unlink_parent(BasicNode* p)    {}
    virtual void unlink_parents()               {}

    virtual void unlink()                       {}
};

class TreeNode : public BasicNode {
protected:
    NodeSet     m_parents;

public:

    ~TreeNode() override = default;

    void invalidate_parents() {
        for (auto p : m_parents)
            if (p->is_valid_and_not_set())
                p->invalidate();
    }

    void invalidate() override                  { BasicNode::invalidate(); invalidate_parents(); }
    void set(const py::object& value) override  { BasicNode::set(value); invalidate_parents(); }

    NodeSet* parents()  override                 { return &m_parents; }
    void clear_parents()  override               { m_parents.clear(); }
    void remove_parent(BasicNode* p)  override   { m_parents.erase(p); }

    void add_parent(BasicNode* p)  override {
        if (p == this)
            throw py::value_error(py::str("A node {} may not be its own parent").format((size_t)this));

        m_parents.insert(p);
        p->add_child(this);
    }

    void unlink_parents() override {
        for(auto p : m_parents)
            p->unlink_child(this);
        clear_parents();
    }

    void unlink() override {
        unlink_parents();
    }
};

class BasicGraphNode : public TreeNode {
protected:
    NodeSet     m_children;

public:

    ~BasicGraphNode() override = default;

    NodeSet* children() override                { return &m_children; }
    void clear_children()  override             { m_children.clear(); }
    void remove_child(BasicNode* c)  override   { m_children.erase(c); }
    void add_child(BasicNode* c)  override      { m_children.insert(c); }

    void unlink_children() override {
        for(auto c : m_children)
            c->unlink_parent(this);
        clear_children();
    }

    void unlink() override {
        unlink_children();
        unlink_parents();
    }
};

class BTrait;

class GraphNode : public BasicGraphNode {
protected:
    py::object m_class;
    //TID*        m_tid;
    //BTrait*     m_trait;

public:
    ~GraphNode() override = default;

    //[[nodiscard]] BTrait* trait() const               { return m_trait; }
    //[[nodiscard]] TID* tid() const                    { return m_tid; }

};
