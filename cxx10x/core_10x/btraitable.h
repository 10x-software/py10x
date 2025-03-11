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


class BTraitable {
protected:
    BTraitableClass*    m_class;
    TID                 m_tid;

public:
    explicit BTraitable(const py::object& cls);

    py::object endogenous_id(bool& non_id_traits_set);
    static py::object exogenous_id();

    void set_id(const py::object& id);
    void initialize(const py::kwargs& trait_values);

    [[nodiscard]] BTraitableClass*      my_class() const    { return m_class; }
    [[nodiscard]] BUiClass*             bui_class() const   { return m_class->bui_class(); }
    [[nodiscard]] const py::object&     class_name() const  { return m_class->name(); }
    [[nodiscard]] const TID&            tid() const         { return m_tid; }
    [[nodiscard]] const py::object&     id() const          { return m_tid.id(); }

    py::object from_any(BTrait* trait, const py::object& value);
    py::object value_to_str(BTrait* trait);

    py::object share(bool accept_existing) {
        return ThreadContext::current_traitable_proc()->share_object(this, accept_existing);
    }

    [[nodiscard]] BTrait* check_trait(const py::str& trait_name) const {
        auto trait = m_class->find_trait(trait_name);
        if (!trait)
            throw py::type_error(py::str("Unknown trait {}.{}").format(class_name(), trait_name));

        return trait;
    }

    bool is_valid(const py::str& trait_name) {
        return is_valid(check_trait(trait_name));
    }

    bool is_valid(BTrait* trait) {
        if (!BTraitableClass::instance_in_cache(m_tid) && m_class->instance_in_store(tid()))
            reload();

        auto proc = ThreadContext::current_traitable_proc();
        return proc->is_valid(this, trait);
    }

    bool is_set(BTrait* trait) {
        if (!BTraitableClass::instance_in_cache(m_tid) && m_class->instance_in_store(tid()))
            reload();

        auto proc = ThreadContext::current_traitable_proc();
        return proc->is_set(this, trait);
    }

    void invalidate_value(const py::str& trait_name) {
        invalidate_value(check_trait(trait_name));
    }

    void invalidate_value(const py::str& trait_name, const py::args& args) {
        invalidate_value(check_trait(trait_name), args);
    }

    void invalidate_value(BTrait* trait) {
        if (!BTraitableClass::instance_in_cache(m_tid) && m_class->instance_in_store(tid()))
            reload();

        auto proc = ThreadContext::current_traitable_proc();
        proc->invalidate_trait_value(this, trait);
    }

    void invalidate_value(BTrait* trait, const py::args& args) {
        if (!BTraitableClass::instance_in_cache(m_tid) && m_class->instance_in_store(tid()))
            reload();

        auto proc = ThreadContext::current_traitable_proc();
        proc->invalidate_trait_value(this, trait, args);
    }

    py::object get_value(const py::str& trait_name) {
        return get_value(check_trait(trait_name));
    }

    py::object get_value(const py::str& trait_name, const py::args& args) {
        return get_value(check_trait(trait_name), args);
    }

    py::object get_value(BTrait* trait) {
        if (!BTraitableClass::instance_in_cache(m_tid) && m_class->instance_in_store(tid()))
            reload();

        auto proc = ThreadContext::current_traitable_proc();
        return proc->get_trait_value(this, trait);
    }

    py::object get_value(BTrait* trait, const py::args& args) {
        if (!BTraitableClass::instance_in_cache(m_tid) && m_class->instance_in_store(tid()))
            reload();

        auto proc = ThreadContext::current_traitable_proc();
        return proc->get_trait_value(this, trait, args);
    }

    py::object get_choices(BTrait* trait) {
        auto proc = ThreadContext::current_traitable_proc();
        return proc->get_choices(this, trait);
    }

    py::object get_style_sheet(BTrait* trait) {
        if (trait->custom_f_style_sheet().is_none())
            return PyLinkage::XNone();

        auto proc = ThreadContext::current_traitable_proc();
        return proc->get_style_sheet(this, trait);
    }

    py::object set_value(const py::str& trait_name, const py::object& value) {
        return set_value(check_trait(trait_name), value);
    }

    py::object set_value(const py::str& trait_name, const py::object& value, const py::args& args) {
        return set_value(check_trait(trait_name), value, args);
    }

    py::object set_value(BTrait* trait, const py::object& value) {
        if (!BTraitableClass::instance_in_cache(m_tid) && m_class->instance_in_store(tid()))
            reload();

        auto proc = ThreadContext::current_traitable_proc();
        return proc->set_trait_value(this, trait, value);
    }

    py::object set_value(BTrait* trait, const py::object& value, const py::args& args) {
        if (!BTraitableClass::instance_in_cache(m_tid) && m_class->instance_in_store(tid()))
            reload();

        auto proc = ThreadContext::current_traitable_proc();
        return proc->set_trait_value(this, trait, value, args);
    }

    py::object set_values(const py::dict& trait_values, bool ignore_unknown_traits = true);

    py::object raw_set_value(const py::str& trait_name, const py::object& value) {
        return raw_set_value(check_trait(trait_name), value);
    }

    py::object raw_set_value(const py::str& trait_name, const py::object& value, const py::args& args) {
        return raw_set_value(check_trait(trait_name), value, args);
    }

    py::object raw_set_value(BTrait* trait, const py::object& value) {
        if (!BTraitableClass::instance_in_cache(m_tid) && m_class->instance_in_store(tid()))
            reload();

        auto proc = ThreadContext::current_traitable_proc();
        return proc->raw_set_trait_value(this, trait, value);
    }

    py::object raw_set_value(BTrait* trait, const py::object& value, const py::args& args) {
        if (!BTraitableClass::instance_in_cache(m_tid) && m_class->instance_in_store(tid()))
            reload();

        auto proc = ThreadContext::current_traitable_proc();
        return proc->raw_set_trait_value(this, trait, value, args);
    }

    //py::object  raw_get_value(BTrait* trait);

    py::object  serialize(bool embed);
    void        deserialize(const py::dict& serialized_data);
    void        reload();

};


