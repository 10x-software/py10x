//
// Created by AMD on 5/21/2024.
//

#include "btraitable.h"
#include "py_hasher.h"
#include "bprocess_context.h"
#include "btraitable_ui_extension.h"
#include "bnucleus.h"

#include "brc.h"

//BTraitable::BTraitable(const py::object& cls) {
//    m_tid.set_class(cls.cast<BTraitableClass*>());
//}

BTraitable::~BTraitable() {
    if (!m_tid.is_valid()) {    //-- remove temp obj's nodes
        auto cache = ThreadContext::current_traitable_proc()->cache();
        cache->remove_object_cache(m_tid, true);
    }
}

py::object BTraitable::exogenous_id() {
    return PyHasher::uuid();
}

py::object BTraitable::endogenous_id(bool& non_id_traits_set) {
    py::list regulars;
    auto hasher = PyHasher();

    auto proc = ThreadContext::current_traitable_proc();
    auto cache = proc->cache();
    bool non_id_set = false;
    for (auto item : my_class()->trait_dir()) {
        auto trait = item.second.cast<BTrait*>();
        if (trait->flags_on(BTraitFlags::ID)) {
            auto value = proc->get_trait_value(this, trait);

            BTraitableProcessor::check_value(this, trait, value);

            if (value.is(PyLinkage::XNone()))   //-- TODO: we probably don't need this anymore (see above)
                throw py::value_error(py::str("{}.{} is undefined").format(class_name(), item.first));

            auto value_for_id = trait->wrapper_f_to_id(this, value);
            if (!trait->flags_on(BTraitFlags::HASH))
                regulars.append(value_for_id);
            else
                hasher.update(value_for_id);
        }
        else
            non_id_set |= proc->is_set(this, trait);
    }
    non_id_traits_set = non_id_set;

    if (hasher.is_updated()) {
        regulars.append(hasher.hexdigest());
        regulars.append(py::str("00"));     //-- for possible hash collision
    }

    return py::str("|").attr("join")(regulars);
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
void BTraitable::initialize(const py::dict& trait_values) {
    auto cls = my_class();
    if (cls->is_id_endogenous()) {
        auto proc = ThreadContext::current_traitable_proc();
        if (trait_values.empty()) {  // kwargs empty
            if (!proc->is_empty_object_allowed())
                throw py::type_error(py::str("{} expects at least one ID trait value").format(class_name()));
            return;
        }

        //-- setting trait values (not calling set_values() for performance reasons and throwing immediately on error
        for (auto item : trait_values) {
            auto trait_name = item.first.cast<py::object>();
            auto trait = cls->find_trait(trait_name);
            if (trait) {    // skipping unknown trait names
                auto value = item.second.cast<py::object>();
                BRC rc(proc->set_trait_value(this, trait, value));
                if (!rc)
                    throw py::value_error(rc.error());
            }
        }

        BRC rc(proc->share_object(this, false));   //-- not silently accepting possibly existing instance
        if (!rc)
            throw py::value_error(py::str("{}/{} - already exists with potentially different non-ID trait values").format(class_name(), rc.payload()));
    }
    else {        // ID exogenous
        m_tid.set_id_value(exogenous_id());
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
    auto proc = ThreadContext::current_traitable_proc();
    for (auto item : trait_values) {
        auto trait_name = item.first.cast<py::object>();
        auto trait = my_class()->find_trait(trait_name);
        if (!trait) {
            if (!ignore_unknown_traits)
                throw py::type_error(py::str("{}.{} - unknown trait").format(class_name(), trait_name));

            continue;
        }

        auto value = item.second.cast<py::object>();
        BRC rc(proc->set_trait_value(this, trait, value));
        if (!rc)
            return rc();
    }

    return PyLinkage::RC_TRUE();
}

//======================================================================================================================
//  Serialization/Deserialization related methods
//======================================================================================================================

py::object BTraitable::get_revision() {
    auto rt = my_class()->find_trait(BNucleus::REVISION_TAG());
    return rt ? get_value(rt) : py::int_(0);
}

void BTraitable::set_revision(const py::object& rev) {
    auto rt = my_class()->find_trait(BNucleus::REVISION_TAG());
    if (rt)
        set_value(rt, rev);
}

//-- Nucleus' serialize (not for top-level objects)
py::object BTraitable::serialize_nx(bool embed) {
    if (!embed) {   //-- external reference
        if (PyLinkage::issubclass(my_class()->py_class(), PyLinkage::anonymous_class()))
            throw py::type_error(py::str("{} - anonymous' instance may not be serialized as external reference").format(class_name()));

        py::dict res;
        m_tid.serialize_id(res, embed);
        //-- TODO: must save the object if not in store!
        return res;
    }

    if (!PyLinkage::issubclass(my_class()->py_class(), PyLinkage::anonymous_class()))
        throw py::type_error(py::str("{}/{} - embedded instance must be anonymous").format(class_name(), id_value()));

    return serialize_traits();
}

py::object BTraitable::deserialize_nx(BTraitableClass *cls, const py::object& serialized_data) {
    auto id = TID::deserialize_id(serialized_data, false);  //-- may or may not be there
    if (!id.is_none()) {     //-- external reference
        if (ThreadContext::current_traitable_proc()->flags_on(BTraitableProcessor::DEBUG))
            return cls->load(id);

        return cls->py_class()(id);     // cls(_id = id)   - keep lazy reference
    }

    //-- Embedded traitable
    auto py_traitable = cls->py_class()();      // cls() - exogeneous iD!
    auto obj = py_traitable.cast<BTraitable*>();
    obj->deserialize_traits(serialized_data);
    return py_traitable;
}

py::object BTraitable::serialize_object() {
    py::dict serialized_data;

    serialized_data[BNucleus::ID_TAG()] = id_value();
    serialized_data[BNucleus::REVISION_TAG()] = get_revision();

    auto class_id = my_class()->serialize_class_id();
    if (!class_id.is_none())
        serialized_data[BNucleus::CLASS_TAG()] = class_id;

    return serialized_data | serialize_traits();
}

py::object BTraitable::deserialize_object(BTraitableClass *cls, const py::object& coll_name, const py::dict& serialized_data) {
    auto class_id = cls->get_field(serialized_data, BNucleus::CLASS_TAG(), false);
    if (!class_id.is_none()) {
        auto py_class = cls->deseriaize_class_id(class_id);
        cls = py_class.attr("s_bclass").cast<BTraitableClass*>();
    }

    auto id_value = cls->get_field(serialized_data, BNucleus::ID_TAG());
    auto id = PyLinkage::traitable_id(id_value, coll_name);
    auto rev = cls->get_field(serialized_data, BNucleus::REVISION_TAG());

    auto py_traitable = cls->py_class()(id);    // cls(_id = id)
    auto obj = py_traitable.cast<BTraitable*>();
    obj->set_revision(rev);

    obj->deserialize_traits(serialized_data);
    return py_traitable;
}

py::dict BTraitable::serialize_traits() {
    py::dict res;
    auto XNone = PyLinkage::XNone();
    auto proc = ThreadContext::current_traitable_proc();
    for (auto item : my_class()->trait_dir()) {
        auto trait = item.second.cast<BTrait*>();
        if (!trait->flags_on(BTraitFlags::RUNTIME) && !trait->flags_on(BTraitFlags::RESERVED)) {
            auto trait_name = item.first.cast<py::object>();
            auto value = proc->get_trait_value(this, trait);
            if (value.is_none())    //-- None is never serialized (user's decision to return or set None)
                throw py::value_error(py::str("{}.{} - undefined value").format(class_name(), trait_name));

            //-- XNone is serialized as None (undefined)
            auto ser_value = value.is(XNone) ? py::none() : trait->wrapper_f_serialize(this, value);
            res[trait_name] = ser_value;
        }
    }
    if (res.empty())
        throw py::value_error(py::str("{}/{} - no storable traits found").format(class_name(), id_value()));

    return res;
}

void BTraitable::deserialize_traits(const py::dict& trait_values) {
    auto proc = ThreadContext::current_traitable_proc();
    proc->cache()->create_object_cache(m_tid);

    auto XNone = PyLinkage::XNone();
    for (auto item : my_class()->trait_dir()) {
        auto trait = item.second.cast<BTrait*>();
        if (trait->flags_on(BTraitFlags::RESERVED) || trait->flags_on(BTraitFlags::RUNTIME))
            continue;

        auto trait_name = item.first.cast<py::object>();
        auto value = PyLinkage::dict_get(trait_values, trait_name);
        if (value.is(XNone))
            proc->invalidate_trait_value(this, trait);      //-- TODO: should we set None instead?
        else {
            //-- As XNone is serialized as None, get it back, if any
            auto deser_value = value.is_none() ? XNone : trait->wrapper_f_deserialize(this, value);
            BRC rc(set_value(trait, deser_value));
            if (!rc)
                throw py::value_error(rc.error());
        }
    }
}

bool BTraitable::reload() {
    if (my_class()->is_storable() && m_tid.is_valid() && !BProcessContext::PC.flags_on(BProcessContext::CACHE_ONLY)) {
        const auto serialized_data = my_class()->load_data(id());
        if (!serialized_data.is_none()) {
            deserialize_traits(serialized_data);
            return true;
        }
    }
    return false;
}

