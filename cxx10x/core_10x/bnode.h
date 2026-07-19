//
// Created by AMD on 5/18/2024.
//
#pragma once

#include <set>
#include <stdexcept>

#include "py_linkage.h"

const unsigned STATE_VALID          = 0x1;
const unsigned STATE_SET            = 0x2;
const unsigned STATE_IMPORTED       = 0x4;
const unsigned STATE_GETTER_GUARD   = 0x8;      // transient: this node's getter is evaluating
const unsigned STATE_VALID_AND_SET  = STATE_VALID | STATE_SET;

class NODE_TYPE {
public:
    inline static const int BASIC           = 0;
    inline static const int TREE            = 1;
    inline static const int BASIC_GRAPH     = 2;
    inline static const int UI              = 3;
    inline static const int GRAPH           = 4;
};

class PY10X_API BasicNode {
protected:
    using NodeSet = std::set<BasicNode*>;

    py::object  m_value;
    unsigned    m_state;

public:
    static BasicNode* create(int node_type);

    BasicNode() : m_value(PyLinkage::XNone()), m_state(0x0)  {}
    virtual ~BasicNode() = default;

    [[nodiscard]] bool is_getter_guarded() const { return m_state & STATE_GETTER_GUARD; }
    void set_getter_guard(bool on)              { on ? m_state |= STATE_GETTER_GUARD : m_state &= ~STATE_GETTER_GUARD; }

    // throw if a set()/invalidate() reaches a node whose own getter is still evaluating
    void throw_if_getter_guarded() const {
        if (m_state & STATE_GETTER_GUARD)
            throw std::runtime_error(
                "write-during-read: a getter mutated a graph node it depends on while "
                "that getter is still evaluating; see the Python traceback for the "
                "getter and the mutation site");
    }

    [[nodiscard]] bool is_valid() const         { return m_state & STATE_VALID; }
    [[nodiscard]] bool is_set() const           { return (m_state & ~STATE_GETTER_GUARD) == STATE_VALID_AND_SET; }
    [[nodiscard]] bool is_valid_and_not_set() const { return (m_state & STATE_VALID) && ((m_state & STATE_SET) == 0x0); }

    [[nodiscard]] py::object value() const      { return m_value; }

    [[nodiscard]] virtual int node_type() const { return NODE_TYPE::BASIC; }

    void assign_value(const py::object& v)      { m_value = v; }
    void assign(const py::object& v)            { assign_value(v); m_state |= STATE_VALID; }
    void set_imported(const py::object& v)      { set(v); m_state |= STATE_IMPORTED; }
    void make_valid()                           { m_state |= STATE_VALID; }
    void make_invalid()                         { m_state &= ~STATE_VALID_AND_SET; }
    void set_state(unsigned state)              { m_state = state; }

    virtual void set(const py::object& v )      { m_value = v; m_state = (m_state & STATE_GETTER_GUARD) | STATE_VALID_AND_SET; }

    virtual void invalidate() {
        if (is_valid()) {
            m_value = PyLinkage::XNone();
            m_state &= ~STATE_VALID_AND_SET;
        }
    }

    virtual NodeSet* children()                 { return nullptr; }
    virtual void clear_children()               {}
    virtual void remove_child(BasicNode* c)     {}
    virtual void add_child(BasicNode* c)        {}
    virtual void unlink_children()              {}

    virtual NodeSet* parents()                  { return nullptr; }
    virtual void clear_parents()                {}
    virtual void remove_parent(BasicNode* p)    {}
    virtual void add_parent(BasicNode* p)       {}
    virtual void unlink_parents()               {}

    virtual void unlink()                       {}

    virtual bool is_successor_of(const BasicNode* node) const   { return false; }

};

// marks a node's "getter is evaluating" bit for the duration of its getter call
class GetterGuard {
    BasicNode* m_node;
public:
    explicit GetterGuard(BasicNode* n) : m_node(n)  { m_node->set_getter_guard(true); }
    ~GetterGuard()                                  { m_node->set_getter_guard(false); }
    GetterGuard(const GetterGuard&) = delete;
    GetterGuard& operator=(const GetterGuard&) = delete;
};

class PY10X_API TreeNode : public BasicNode {
protected:
    NodeSet     m_parents;

public:

    ~TreeNode() override = default;

    [[nodiscard]] int node_type() const override    { return NODE_TYPE::TREE; }

    void invalidate_parents() const {
        for (auto p : m_parents)
            if (p->is_getter_guarded() || p->is_valid_and_not_set())
                p->invalidate();
    }

    void invalidate() override {
        throw_if_getter_guarded();      // must precede the is_valid() early return
        if (is_valid()) {
            m_value = PyLinkage::XNone();
            m_state &= STATE_GETTER_GUARD;      // clear all but the guard bit
            invalidate_parents();
        }
    }

    void set(const py::object& value) override {
        throw_if_getter_guarded();
        BasicNode::set(value);
        invalidate_parents();
    }

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
            p->remove_child(this);
        clear_parents();
    }

    void unlink() override {
        unlink_parents();
    }

    bool is_successor_of(const BasicNode* node) const override {
        return std::ranges::any_of(m_parents, [&](auto p) {
            return p == node || p->is_successor_of(node);
        });
    }
};

class PY10X_API BasicGraphNode : public TreeNode {
protected:
    NodeSet     m_children;

public:

    ~BasicGraphNode() override = default;

    [[nodiscard]] int node_type() const override    { return NODE_TYPE::BASIC_GRAPH; }

    NodeSet* children() override                { return &m_children; }
    void clear_children()  override             { m_children.clear(); }
    void remove_child(BasicNode* c)  override   { m_children.erase(c); }
    void add_child(BasicNode* c)  override      { m_children.insert(c); }

    void unlink_children() override {
        for(auto c : m_children)
            c->remove_parent(this);
        clear_children();
    }

    void unlink() override {
        unlink_children();
        unlink_parents();
    }

};

class BTrait;

class PY10X_API GraphNode : public BasicGraphNode {
protected:
    py::object m_class;
    //TID*        m_tid;
    //BTrait*     m_trait;

public:
    ~GraphNode() override = default;

    [[nodiscard]] int node_type() const override    { return NODE_TYPE::GRAPH; }

    //[[nodiscard]] BTrait* trait() const               { return m_trait; }
    //[[nodiscard]] TID* tid() const                    { return m_tid; }

};

class PY10X_API BUiNode : public BasicGraphNode {
    py::object  f_refresh_emit;

public:
    BUiNode() {
        f_refresh_emit = py::none();
    }

    [[nodiscard]] int node_type() const final { return NODE_TYPE::UI; }

    void set_refresh_emit(py::object f)     { f_refresh_emit = f; }

    void invalidate() final {
        throw_if_getter_guarded();
        if (is_valid()) {
            m_state &= STATE_GETTER_GUARD;
            f_refresh_emit();
        }
    }
};