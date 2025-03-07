//
// Created by AMD on 5/21/2024.
//

#include "btraitable.h"
#include "py_hasher.h"
#include "bprocess_context.h"
#include "btraitable_ui_extension.h"

#include "brc.h"

py::object BTraitable::exogenous_id() {
    return PyHasher::uuid();
}

py::object BTraitable::endogenous_id() {
    py::list regulars;
    auto hasher = PyHasher();

    auto proc = ThreadContext::current_traitable_proc();
    for (auto item : m_class->trait_dir()) {
        auto trait = item.second.cast<BTrait*>();
        if (trait->flags_on(BTraitFlags::ID)) {
            auto value = proc->get_trait_value(this, trait);
            if (value.is(PyLinkage::XNone()))
                throw py::value_error(py::str("{}.{} is undefined").format(m_class->name(), item.first));

            auto value_for_id = trait->wrapper_f_to_id(this, value);
            if (!trait->flags_on(BTraitFlags::HASH))
                regulars.append(value_for_id);
            else
                hasher.update(value_for_id);
        }
    }

    if (hasher.is_updated()) {
        regulars.append(hasher.hexdigest());
        regulars.append(py::str("00"));     //-- for possible hash collision
    }

    return py::str("|").attr("join")(regulars);
}

BTraitable::BTraitable(const py::object& cls) {
    m_class = cls.cast<BTraitableClass *>();
}

void BTraitable::set_id(const py::object& id) {
    m_tid.set(m_class, id);
}

//======================================================================================================================
//  Must be called right after constructing the object with **kwargs.
//  - kwargs must only have values for traits necessary to build the object ID
//      -- usually ID trait
//      -- an ID trait with custom getter may be missing
//      -- may have a non-ID trait with custom setter which sets some ID traits
//  - any attempt to set non ID traits (either directly via other setters) will throw
//  - trait-name value pairs will be processed in the order they are given
//      -- if setters/getters are used for ID traits, different orders may result in unexpected behavior
//======================================================================================================================
void BTraitable::initialize(const py::kwargs& trait_values) {
    py::object id;
    if (m_class->is_id_endogenous()) {
        auto proc = ThreadContext::current_traitable_proc();
        if (trait_values.empty()) {  // kwargs empty
            if (!proc->is_empty_object_allowed())
                throw py::type_error(py::str("{} expects at least one ID trait value").format(class_name()));
            return;
        }

        for (auto item : trait_values) {
            auto trait_name = item.first.cast<py::object>();
            auto trait = m_class->find_trait(trait_name);
            if (!trait)
                continue;       // skipping unknown trait names

            auto value = item.second.cast<py::object>();
            BRC rc(proc->set_trait_value(this, trait, value));
            if (!rc)
                throw py::value_error(rc.error());
        }
        id = endogenous_id();

        TID tid(m_class, id);
        if (m_class->instance_exists(tid)) {
            proc->cache()->remove_object_cache(m_tid, true);
            // TODO: this object may have set non-ID traits; in such a case, their values will be "replaced" for the existing instance's, if any
            m_tid.set(m_class, id);
        }
        else {      // new instance
            auto cache = proc->cache();
            m_tid.set(m_class, id);
            cache->make_permanent(m_tid);
        }
    }
    else {        // ID exogenous
        id = exogenous_id();
        m_tid.set(m_class, id);
        BRC rc(set_values(trait_values));
        if (!rc)
            throw py::value_error(py::str(rc.error()));
    }
}

py::object BTraitable::from_any(BTrait* trait, const py::object& value) {
    if (py::isinstance(value, trait->m_datatype))
        return value;

    if (py::isinstance<py::str>(value))
        return trait->wrapper_f_from_str(this, value);

    return trait->wrapper_f_from_any_xstr(this, value);
}

py::object BTraitable::value_to_str(BTrait* trait) {
    auto value = get_value(trait);
    return trait->wrapper_f_to_str(this, value);
}

py::object BTraitable::set_values(const py::dict& trait_values, bool ignore_unknown_traits) {
    if (!BTraitableClass::instance_in_cache(m_tid) && m_class->instance_in_store(tid()))
        reload();

    auto proc = ThreadContext::current_traitable_proc();
    for (auto item : trait_values) {
        auto trait_name = item.first.cast<py::object>();
        auto trait = m_class->find_trait(trait_name);
        if (!trait) {
            if (!ignore_unknown_traits)
                throw py::type_error(py::str("{}.{} - unknown trait").format(m_class->name(), trait_name));

            continue;
        }

        auto value = item.second.cast<py::object>();
        BRC rc(proc->set_trait_value(this, trait, value));
        if (!rc)
            return rc();
    }

    return PyLinkage::RC_TRUE();
}

py::object BTraitable::serialize(bool embed) {
    if (!embed)
        return py::str(id());

    if (!BTraitableClass::instance_in_cache(m_tid))     //-- lazy instance - no reason to reload and then serialize
        return py::none();

    py::dict res;
    res["_id"] = id();

    for (auto item : m_class->trait_dir()) {
        auto trait = item.second.cast<BTrait*>();
        if (!trait->flags_on(BTraitFlags::RUNTIME)) {
            auto trait_name = item.first.cast<py::object>();
            auto value = get_value(trait);
            if (value.is(PyLinkage::XNone()))
                throw py::value_error(py::str("{}.{} - undefined value").format(m_class->name(), trait_name));

            auto ser_value = trait->wrapper_f_serialize(this, value);
            res[trait_name] = ser_value;
        }
    }

    return res;
}

void BTraitable::deserialize(const py::dict& serialized_data) {
    auto cache = ThreadContext::current_traitable_proc()->cache();
    cache->create_object_cache(m_tid);

    for (auto item : serialized_data) {
        auto trait_name = item.first.cast<py::object>();
        if (auto trait = m_class->find_trait(trait_name)) {
            auto value = item.second.cast<py::object>();
            auto deser_value = trait->wrapper_f_deserialize(this, value);
            BRC rc(set_value(trait, deser_value));
            if (!rc)
                throw py::value_error(rc.error());
        }
    }
}

void BTraitable::reload() {
    if (!BProcessContext::PC.flags_on(BProcessContext::CACHE_ONLY) || !m_class->is_storable()) {
        auto serialized_data = m_class->load_data(id());
        if (serialized_data.is_none())
            throw py::value_error(py::str("{}/{} - failed to reload").format(class_name(), id()));

        deserialize(serialized_data);
    }
}

