//
// Created by AMD on 5/21/2024.
//

#pragma once

#include "py_linkage.h"

#include "tid.h"
#include "btrait.h"
#include "btraitable_processor.h"
#include "thread_context.h"
#include "btraitable_class.h"

using TraitValues = std::unordered_map<BTrait*, py::object>;

class BTraitable {
protected:
    BTraitableClass*    m_class;
    BCache              *m_cache;
    ObjectCache         *m_id_cache;
    std::string         m_id;
    TID                 m_tid;

    std::string endogenous_id();

public:
    static std::string exogenous_id();

    explicit BTraitable(const py::object& cls);
    explicit BTraitable(const py::object& cls, const std::string& id);
    explicit BTraitable(const py::object& cls, const py::kwargs& trait_values);
    ~BTraitable();

    [[nodiscard]] const py::str&        class_name() const  { return m_class->name(); }
    [[nodiscard]] BCache*               cache()             { return m_cache; }
    [[nodiscard]] ObjectCache*          id_cache() const    { return m_id_cache; }
    [[nodiscard]] const TID&            tid() const         { return m_tid; }
    [[nodiscard]] const std::string&    id() const          { return m_tid.id(); }

    void clear_id_cache(bool dispose_of = true) {
        if (dispose_of)
            delete m_id_cache;
        m_id_cache = nullptr;
        delete m_cache;
        m_cache = nullptr;
    }

    py::object from_any(BTrait* trait, const py::object& value);

    void invalidate_value(BTrait* trait) {
        auto proc = ThreadContext::current_traitable_proc_bound();
        proc->invalidate_trait_value(this, trait);
    }

    void invalidate_value(BTrait* trait, const py::args& args) {
        auto proc = ThreadContext::current_traitable_proc_bound();
        proc->invalidate_trait_value(this, trait, args);
    }

    py::object get_value(BTrait* trait) {
        auto proc = ThreadContext::current_traitable_proc_bound();
        return proc->get_trait_value(this, trait);
    }

    py::object get_value(BTrait* trait, const py::args& args) {
        auto proc = ThreadContext::current_traitable_proc_bound();
        return proc->get_trait_value(this, trait, args);
    }

    py::object set_value(BTrait* trait, const py::object& value) {
        auto proc = ThreadContext::current_traitable_proc_bound();
        return proc->set_trait_value(this, trait, value);
    }

    py::object set_value(BTrait* trait, const py::object& value, const py::args& args) {
        auto proc = ThreadContext::current_traitable_proc_bound();
        return proc->set_trait_value(this, trait, value, args);
    }

    py::object set_values(const py::dict& trait_values, dict_iter* iter = nullptr, bool ignore_unknown_traits = true);

    py::object raw_set_value(BTrait* trait, const py::object& value) {
        auto proc = ThreadContext::current_traitable_proc_bound();
        return proc->raw_set_trait_value(this, trait, value);
    }

    py::object raw_set_value(BTrait* trait, const py::object& value, const py::args& args) {
        auto proc = ThreadContext::current_traitable_proc_bound();
        return proc->raw_set_trait_value(this, trait, value, args);
    }

    //py::object  raw_get_value(BTrait* trait);

    py::object  serialize(bool embed);
    void        deserialize(const py::dict& serialized_data);
    void        reload();

};


