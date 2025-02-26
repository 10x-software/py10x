//
// Created by AMD on 7/2/2024.
//

#pragma once

#include <deque>
#include <unordered_map>
#include <thread>

#include "py_linkage.h"

class BasicNode;
class BTraitable;
class BTrait;

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

class Placebo {
    ExecStack* m_stack;
    BasicNode* m_node;
public:
    explicit Placebo(ExecStack* xstack);
    Placebo(const Placebo& p) = default;
    ~Placebo();
};

class BCache;

class BTraitableProcessor {
protected:

    static unsigned s_default_type;

    BCache*     m_cache;
    ExecStack   m_stack;
    unsigned    m_flags;
    bool        m_own_cache = false;

    static BTraitableProcessor* create_raw(unsigned flags);

public:

    inline static const unsigned   PLAIN           = 0x0;
    inline static const unsigned   DEBUG           = 0x1;
    inline static const unsigned   CONVERT_VALUES  = 0x2;
    inline static const unsigned   ON_GRAPH        = 0x4;

    static void set_default_type(unsigned proc_type)        { s_default_type = proc_type; }
    static unsigned default_type()                          { return s_default_type; }

    static BTraitableProcessor* create_default();

    static BTraitableProcessor* create(unsigned flags);
    static BTraitableProcessor* current();

    BTraitableProcessor() : m_cache(nullptr), m_flags(PLAIN) {}
    virtual ~BTraitableProcessor();

    [[nodiscard]] BCache*   own_cache() const               { return m_own_cache ? m_cache : nullptr; }
    void                    use_own_cache(BCache* c)        { m_cache = c; m_own_cache = true; }

    [[nodiscard]] BCache*   cache() const                   { return m_cache; }
    virtual void            use_cache(BCache* c)            { m_cache = c; }

    ExecStack*              exec_stack()                    { return &m_stack; }

    [[nodiscard]] unsigned  flags() const                   { return m_flags; }
    void                    set_flags(unsigned flags)       { m_flags = flags; }
    [[nodiscard]] bool      flags_on(unsigned flags) const  { return m_flags & flags; }

    static py::object       check_value(BTraitable* obj, BTrait* trait, const py::object& value);

    void                    begin_using();
    void                    end_using();
    BTraitableProcessor*    py_enter()                      { begin_using(); return this; }
    void                    py_exit(const py::args&)        { end_using(); }

    virtual py::object      set_trait_value(BTraitable* obj, BTrait* trait, const py::object& value);
    virtual py::object      set_trait_value(BTraitable* obj, BTrait* trait, const py::object& value, const py::args& args);

    virtual void            invalidate_trait_value(BTraitable* obj, BTrait* trait) = 0;
    virtual void            invalidate_trait_value(BTraitable* obj, BTrait* trait, const py::args& args) = 0;

    //virtual py::object      get_trait_value_if_valid(BTraitable* obj, BTrait* trait) = 0;
    virtual py::object      get_trait_value(BTraitable* obj, BTrait* trait) = 0;
    virtual py::object      get_trait_value(BTraitable* obj, BTrait* trait, const py::args& args) = 0;

    virtual py::object      adjust_set_value(BTraitable* obj, BTrait* trait, const py::object& value) = 0;
    virtual py::object      raw_set_trait_value(BTraitable* obj, BTrait* trait, const py::object& value) = 0;
    virtual py::object      raw_set_trait_value(BTraitable* obj, BTrait* trait, const py::object& value, const py::args& args) = 0;

    class Use {
        bool    m_temp;
    public:
        explicit Use(BTraitableProcessor* proc, bool temp = false);
        ~Use();
    };
};

