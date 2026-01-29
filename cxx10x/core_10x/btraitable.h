//
// Created by AMD on 5/21/2024.
//

#pragma once

#include <format>
#include "py_linkage.h"

#include "tid.h"
#include "btrait.h"
#include "btraitable_processor.h"
#include "thread_context.h"
#include "btraitable_class.h"

/*
[x] Traitables keep the following member variables:
  [x] creation_cache (ptr)

[x] Object cache keeps the storage flags:
      [x] load_required (bool)
      [x] must_exist_in_storage (bool)

[x] Traitable constructors:
    [x] Using trait values
      [x] trait values are only used for ID construction and must be ID or ID_LIKE - anything else will throw
      [x] constructor makes ID, sets ID and ID_LIKE traits (in share - accept_existing=true)
      [x] storage flags (in share - accept_exiting=true)
        [x] load_required = true (only if not runtime object) (in share, accept_existing=true)
        [x] must_exist_in_storage = false (in initialize())
      [x] creation_cache = current_cache (in BTraitable ctor) or existing_cache, if found (in share)
    [x] Using ID (lazy ref)
      [x] if runtime object and not in memory
        [x] same as below, but will throw on use. this is used in existing_object_by_id(_throw=False) for runtime objects.
      [x] storage flags (in BTraitable  ctor)
        [x] load_required = true (in BTraitable ctor)
        [x] must_exist_in_storage = true (in BTraitable ctor)
      [x] creation_cache = current_cache or existing_cache, if found (in BTraitable ctor)
    [x] Empty object (when is_empty_object_allowed)
      [x] storage flags (in share - accept_existing=false)
        [x] load_required = false (in share, accept_existing=false)
        [x] must_exist_in_storage = false (in share, accept_existing=false)
      [x] creation_cache = current_cache (in BTraitable ctor)

- Traitable validation/lazy load
    - When in the course of normal operations we need access to object cache, we do the following
      [x] if creation_cache is not reachable from the current cache via parent chain
          [x] it's an error! (in find_or_create_object_cache)
      [x] If creation_cache has load_required flag (this is all in lazy_load)
          [x] set load_required=false
          [x] load in creation_cache
            [x] If not found, and must_exist_in_storage==true
              [x] it's an error! + specific error for non-storable objects (in lazy_load)

- Note: get_value_off_graph already needs access to object_cache
  currently to make sure lazy load occurs if necessary, so we are not
  adding extra overhead, except onetime detection of creation_cache
  reachability.

- In debug mode deserialization (forced load)
      - Set load_required=false
      - Load in current cache (same as creation cache)
      - If not found, it's an error
 */
class BTraitable {
protected:
    TID     m_tid;
    XCache* m_origin_cache;


public:
    explicit BTraitable(BTraitableClass* cls, const py::object& id) : m_tid(cls, id) {
        const auto proc = ThreadContext::current_traitable_proc();
        m_origin_cache = proc->cache();
        if (m_tid.is_valid()) {
            //-- lazy reference, must exist in store unless exists in memory
            if (const auto existing_cache = m_origin_cache->find_origin_cache(m_tid))
                set_origin_cache(existing_cache);
            else {
                set_lazy_load_flags(XCache::LOAD_REQUIRED_MUST_EXIST|proc->flags()&BTraitableProcessor::DEBUG);
            }
        }
    }
    virtual ~BTraitable();

    py::object endogenous_id();

    void set_lazy_load_flags(const unsigned flags) const        { m_origin_cache->set_lazy_load_flags(m_tid, flags); }
    void clear_lazy_load_flags(unsigned lazy_load_flags) const  { m_origin_cache->clear_lazy_load_flags(m_tid, lazy_load_flags); }
    [[nodiscard]] unsigned lazy_load_flags() const              { return m_origin_cache->lazy_load_flags(m_tid); }

    py::object lazy_load_if_needed();

    std::runtime_error runtime_error(const char *str) const {
        return std::runtime_error(std::format("{}/{}: object {}:\n{}", std::string(class_name()), std::string(id_value()), str, current_stacktrace()));
    }

    static py::object exogenous_id();

    void initialize(const py::dict &trait_values, bool create_or_replace);
    bool accept_existing(const py::dict& trait_values);
    bool id_exists();

    void set_id_value(const py::object& id_value) const         { m_tid.set_id_value(id_value); }
    void set_origin_cache(XCache *oc)                           { m_origin_cache = oc; }

    [[nodiscard]] XCache*           origin_cache() const        { return m_origin_cache; }
    [[nodiscard]] BTraitableClass*  my_class() const            { return m_tid.cls(); }
    [[nodiscard]] BUiClass*         bui_class() const           { return my_class()->bui_class(); }
    [[nodiscard]] py::str           class_name() const          { return my_class()->name(); }
    [[nodiscard]] const TID&        tid() const                 { return m_tid; }
    [[nodiscard]] py::object        id() const                  { return m_tid.id(); }
    [[nodiscard]] py::str           id_value() const            { return m_tid.id_value(); }
    [[nodiscard]] py::str           custom_coll_name() const    { return m_tid.coll_name(); }

    py::object from_any(const BTrait *trait, const py::object &value);
    py::object value_to_str(BTrait* trait);

    py::object share(const bool accept_existing) {
        return ThreadContext::current_traitable_proc()->share_object(this, accept_existing);
    }

    [[nodiscard]] BTrait* check_trait(const py::str& trait_name) const {
        const auto trait = my_class()->find_trait(trait_name);
        if (!trait)
            throw py::type_error(py::str("Unknown trait {}.{}").format(class_name(), trait_name));

        return trait;
    }

    [[nodiscard]] bool is_valid(const py::str& trait_name) {
        return is_valid(check_trait(trait_name));
    }

    [[nodiscard]] bool is_valid(const BTrait* trait) {
        const auto proc = ThreadContext::current_traitable_proc();
        return proc->is_valid(this, trait);
    }

    [[nodiscard]] bool is_set(const BTrait* trait) const {
        const auto proc = ThreadContext::current_traitable_proc();
        return proc->is_set(this, trait);
    }

    void invalidate_value(const py::str& trait_name) {
        invalidate_value(check_trait(trait_name));
    }

    void invalidate_value(const py::str& trait_name, const py::args& args) {
        invalidate_value(check_trait(trait_name), args);
    }

    void invalidate_value(BTrait* trait) {
        auto proc = ThreadContext::current_traitable_proc();
        proc->invalidate_trait_value(this, trait);
    }

    void invalidate_value(BTrait* trait, const py::args& args) {
        auto proc = ThreadContext::current_traitable_proc();
        proc->invalidate_trait_value(this, trait, args);
    }

    py::object get_value(const py::str& trait_name) {
        return get_value(check_trait(trait_name));
    }

    py::object get_value(const py::str& trait_name, const py::args& args) {
        return get_value(check_trait(trait_name), args);
    }

    py::object get_value(const BTrait* trait) {
        auto proc = ThreadContext::current_traitable_proc();
        return proc->get_trait_value(this, trait);
    }

    py::object get_value(const BTrait* trait, const py::args& args) {
        auto proc = ThreadContext::current_traitable_proc();
        return proc->get_trait_value(this, trait, args);
    }

    py::object get_choices(BTrait* trait) {
        auto proc = ThreadContext::current_traitable_proc();
        return proc->get_choices(this, trait);
    }

    py::object get_style_sheet(const BTrait* trait) {
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
        auto proc = ThreadContext::current_traitable_proc();
        return proc->set_trait_value(this, trait, value);
    }

    py::object set_value(BTrait* trait, const py::object& value, const py::args& args) {
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
        auto proc = ThreadContext::current_traitable_proc();
        return proc->raw_set_trait_value(this, trait, value);
    }

    py::object raw_set_value(BTrait* trait, const py::object& value, const py::args& args) {
        auto proc = ThreadContext::current_traitable_proc();
        return proc->raw_set_trait_value(this, trait, value, args);
    }

    //py::object  raw_get_value(BTrait* trait);

//    void load_if_needed() {
//        if (!BTraitableClass::instance_in_cache(m_tid) && my_class()->instance_in_store(tid()))
//            reload();
//    }

    py::object          get_revision();
    void                set_revision(const py::object& rev);

    py::dict            serialize_traits();
    py::object          serialize_object(bool save_references);
    py::object          serialize_nx(bool embed);      //-- Nucleus' method

    static py::object   deserialize_object(const BTraitableClass* cls, const py::object& coll_name, const py::dict& serialized_data);
    virtual void        deserialize_traits(const py::dict& trait_values);
    static py::object   deserialize_nx(const BTraitableClass* cls, const py::object& serialized_data);
    py::object          _reload(const bool rev_only = false);
    bool                reload() {return !_reload().is_none();}

};


