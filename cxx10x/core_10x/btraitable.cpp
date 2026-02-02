//
// Created by AMD on 5/21/2024.
//

#include "btraitable.h"
#include "py_hasher.h"
#include "bprocess_context.h"
//#include "btraitable_ui_extension.h"
#include "bnucleus.h"

#include "brc.h"

//BTraitable::BTraitable(const py::object& cls) {
//    m_tid.set_class(cls.cast<BTraitableClass*>());
//

BTraitable::~BTraitable() {
    // TODO: what if it gets collected while a different cache is active? or on different thread?
    // Perhaps,
    // 1) remember creation_thread (together with creation_cache)
    // 2) find current cache on creation_thread
    // 3) remove from the current cache on creation_thread its parents
    // Q: What if nodes exist in caches on other than the creation thread?
    //    Are traitables only usable on the thread they were created on?

    if (!m_tid.is_valid()) {    //-- remove temp obj's nodes
        const auto cache = ThreadContext::current_traitable_proc()->cache();
        cache->remove_temp_object_cache(m_tid);
    }
    //TODO: class flag to indicate if objects is auto-disposable default = true
}

py::object BTraitable::lazy_load_if_needed() {
    const auto flags = lazy_load_flags();

    if (!(flags & XCache::LOAD_REQUIRED))
        return py::none();

    if (flags & XCache::MUST_EXIST_IN_STORE && !my_class()->is_storable())
        throw runtime_error( "is an invalid lazy reference to non-storable that does not exist in memory" );

    auto use = BTraitableProcessor::Use(BTraitableProcessor::create_for_lazy_load(m_origin_cache, flags));
    clear_lazy_load_flags(flags);
    const auto serialized_data = _reload(flags & XCache::LOAD_REV_ONLY);
    set_lazy_load_flags(flags & BTraitableProcessor::DEBUG); // -- only keep the debug flag, if set

    if (serialized_data.is_none() && flags & XCache::MUST_EXIST_IN_STORE) {
        throw runtime_error( "reference not found in store" );
    }
    return serialized_data;
}

py::object BTraitable::exogenous_id() {
    return PyHasher::uuid();
}

py::object BTraitable::endogenous_id() {
    py::list regulars;
    auto hasher = PyHasher();
    const auto proc = ThreadContext::current_traitable_proc();
    for (const auto [trait_name, trait_handle] : my_class()->trait_dir()) {
        if (const auto trait = trait_handle.cast<BTrait*>(); trait->flags_on(BTraitFlags::ID) && !trait->flags_on(BTraitFlags::FAUX)) {
            auto value = proc->get_trait_value(this, trait);
            BTraitableProcessor::check_value(this, trait, value);

            if (value.is(PyLinkage::XNone()))   //-- TODO: we probably don't need this anymore (see above)
                throw py::value_error(py::str("{}.{} is undefined").format(class_name(), trait_name));

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

//======================================================================================================================
//  Must be called right after constructing the object with **kwargs.
//  - kwargs must only have values for traits necessary to build the object ID
//      -- an ID trait (the usual case)
//      -- an ID trait with custom getter may be missing
//      -- a non-ID trait with custom setter which sets some ID traits or used in an ID trait getter may also be present
//  - any traits set in kwargs, other than ID traits will be ignored after the ID is built
//  - ID traits will be set, even if they are computed using getters
//  - trait-name value pairs will be processed in the order they are given
//      -- if setters/getters are used for ID traits, different orders may result in unexpected behavior
//======================================================================================================================
void BTraitable::initialize(const py::dict& trait_values, const bool replace_existing=false) {
    if (const auto cls = my_class(); cls->is_id_endogenous()) {
        const auto proc = ThreadContext::current_traitable_proc();

        /* The following check seems too restrictive: Traitable may have getters for ID traits */
//        if (trait_values.empty()) {  // kwargs empty
//            if (!proc->is_empty_object_allowed())
//                throw py::type_error(py::str("{} expects at least one ID trait value").format(class_name()));
//            return;
//        }

        //-- setting trait values (not calling set_values() for performance reasons and throwing immediately on error
        std::unordered_map<const BTrait *,py::object> non_id_traits_set;
        for (auto &[trait_name, value] : trait_values) {
            if (const auto trait = cls->find_trait(trait_name.cast<py::object>())) {    // skipping unknown trait names
                auto py_value = value.cast<py::object>();
                if (py_value.is(PyLinkage::XNone()))    //-- skipping XNone (deferring ID trait value to the getter)
                    continue;

                if (!trait->flags_on(BTraitFlags::ID)) {
                    if (!replace_existing)
                        throw py::value_error(py::str("{}.{} - non-ID trait value cannot be set during initialization").format(class_name(), trait_name));
                    non_id_traits_set[trait] = py_value;
                    continue;
                }
                if (const BRC rc(proc->set_trait_value(this, trait, py_value)); !rc)
                    throw py::value_error(rc.error());
            }
        }
        if (const BRC rc(proc->share_object(this,!replace_existing, replace_existing)); !rc) // -- this never happens as accept_existing==true
            throw py::value_error(py::str("{}/{} - already exists with potentially different non-ID trait values").format(class_name(), rc.payload()));

        if (replace_existing) {
            //-- now we have a potentially lazy reference which might be loaded as we set any non-id traits below
            for (auto &[trait, value] : non_id_traits_set) {
                if (const BRC rc(proc->set_trait_value(this, trait, value)); !rc)
                    throw py::value_error(rc.error());
            }
        }
    }
    else {        // ID exogenous
        m_tid.set_id_value(exogenous_id());
            clear_lazy_load_flags(XCache::LOAD_REQUIRED_MUST_EXIST);
        if (const BRC rc(set_values(trait_values)); !rc)
            throw py::value_error(py::str(rc.error()));
    }
}

bool BTraitable::id_exists() {
    if (!tid().is_valid())
        return false;

    return ThreadContext::current_traitable_proc()->accept_existing(this);
}

bool BTraitable::accept_existing(const py::dict& trait_values) {
    if (const auto cls = my_class(); !cls->is_id_endogenous())
        return false;

    if (BRC rc(set_values(trait_values)); !rc)
        throw py::value_error(py::str(rc.error()));

    return ThreadContext::current_traitable_proc()->accept_existing(this);
}

py::object BTraitable::from_any(const BTrait* trait, const py::object& value) {
    if (py::isinstance(value, trait->m_datatype))
        return value;

    if (py::isinstance<py::str>(value))
        return trait->wrapper_f_from_str(this, value);

    return trait->wrapper_f_from_any_xstr(this, value);
}

py::object BTraitable::value_to_str(BTrait* trait) {
    const auto value = get_value(trait);
    return trait->wrapper_f_to_str(this, value);
}

py::object BTraitable::set_values(const py::dict& trait_values, bool ignore_unknown_traits) {
    auto proc = ThreadContext::current_traitable_proc();
    for (auto item : trait_values) {
        const auto trait_name = item.first.cast<py::object>();
        const auto trait = my_class()->find_trait(trait_name);
        if (!trait) {
            if (!ignore_unknown_traits)
                throw py::type_error(py::str("{}.{} - unknown trait").format(class_name(), trait_name));

            continue;
        }

        auto value = item.second.cast<py::object>();
        if (BRC rc(proc->set_trait_value(this, trait, value)); !rc)
            return rc();
    }

    return PyLinkage::RC_TRUE();
}

//======================================================================================================================
//  Serialization/Deserialization related methods
//======================================================================================================================

py::object BTraitable::get_revision() {
    const auto rt = my_class()->find_trait(BNucleus::REVISION_TAG());
    return rt ? get_value(rt) : py::int_(0);
}

void BTraitable::set_revision(const py::object& rev) {
    if (const auto rt = my_class()->find_trait(BNucleus::REVISION_TAG()))
        set_value(rt, rev);
}

//-- Nucleus' serialize (not for top-level objects)
py::object BTraitable::serialize_nx(const bool embed) {
    if (!embed) {   //-- external reference
        if (my_class()->is_anonymous())
            throw py::type_error(py::str("{} - anonymous' instance may not be serialized as external reference").format(class_name()));

        py::dict res;
        m_tid.serialize_id(res, embed);
        if (ThreadContext::flags() & ThreadContext::SAVE_REFERENCES && !ThreadContext::serialization_memo().contains(m_tid)) {
            auto py_traitable = my_class()->py_class()(m_tid.traitable_id());    // cls(_id = id)
            if (const auto rc = py_traitable.attr("save")(); !py::cast<bool>(rc))
                throw py::value_error(py::str("{}/{} - failed to save referenced object:").format(class_name(), id_value(),rc.attr("error")()));
        }
        return res;
    }

    if (!my_class()->is_anonymous())
        throw py::type_error(py::str("{}/{} - embedded instance must be anonymous").format(class_name(), id_value()));

    return serialize_traits();
}

py::object BTraitable::deserialize_nx(const BTraitableClass *cls, const py::object& serialized_data) {
    if (auto id = TID::deserialize_id(serialized_data, false); !id.is_none()) {     //-- external reference
        auto lazy_ref = cls->py_class()(id);     // cls(_id = id)   - keep lazy reference
        if (const auto obj = lazy_ref.cast<BTraitable*>(); obj->lazy_load_flags() & BTraitableProcessor::DEBUG) {
            obj->set_lazy_load_flags(XCache::LOAD_REQUIRED);
            obj->lazy_load_if_needed();
        }
        return lazy_ref;
    }

    //-- Embedded traitable
    auto py_traitable = cls->py_class()();      // cls() - exogenous iD!
    py_traitable.cast<BTraitable*>()->deserialize_traits(serialized_data);
    return py_traitable;
}

py::object BTraitable::serialize_object(const bool save_references) {
    if (lazy_load_flags() & XCache::LOAD_REQUIRED) {
        if (my_class()->instance_in_store(m_tid))
            return py::none();                                //-- lazy reference exists in store - nothing to save
        clear_lazy_load_flags(XCache::LOAD_REQUIRED);         //-- does not exist in store - nothing to load
        // we continue on so we can e.g. save new objects with ID traits only
    }

    py::dict serialized_data;

    serialized_data[BNucleus::ID_TAG()] = id_value();
    serialized_data[BNucleus::REVISION_TAG()] = get_revision();

    if (const auto class_id = my_class()->serialize_class_id(); !class_id.is_none())
        serialized_data[BNucleus::CLASS_TAG()] = class_id;

    ThreadContext::SerializationScope scope(save_references, m_tid);
    serialized_data |= serialize_traits();

    return serialized_data;
}

py::object BTraitable::deserialize_object(const BTraitableClass *cls, const py::object& coll_name, const py::dict& serialized_data) {
    if (!cls)
        throw std::runtime_error("BTraitable class is required!");
    if (const auto class_id = cls->get_field(serialized_data, BNucleus::CLASS_TAG(), false); !class_id.is_none())
        cls = cls->deserialize_class_id(class_id).attr("s_bclass").cast<BTraitableClass*>();

    const auto id_value = cls->get_field(serialized_data, BNucleus::ID_TAG());
    const auto rev = cls->get_field(serialized_data, BNucleus::REVISION_TAG());

    auto py_traitable = cls->py_class()(PyLinkage::traitable_id(id_value, coll_name));    // cls(_id = id)

    const auto obj = py_traitable.cast<BTraitable*>();
    obj->clear_lazy_load_flags(XCache::LOAD_REQUIRED_MUST_EXIST);
    obj->deserialize_traits(serialized_data);
    obj->set_revision(rev);

    return py_traitable;
}

py::dict BTraitable::serialize_traits() {
    py::dict res;
    const auto XNone = PyLinkage::XNone();
    const auto proc = ThreadContext::current_traitable_proc();
    for (const auto &[trait_name_handle, trait_value_handle] : my_class()->trait_dir()) {
        if (const auto trait = trait_value_handle.cast<BTrait*>(); !trait->flags_on(BTraitFlags::RUNTIME) && !trait->flags_on(BTraitFlags::RESERVED)) {
            const auto trait_name = trait_name_handle.cast<py::object>();
            const auto value = proc->get_trait_value(this, trait);
            if (value.is_none())    //-- None is never serialized (user's decision to return or set None)
                throw py::value_error(py::str("{}.{} - undefined value").format(class_name(), trait_name));

            //-- XNone is serialized as None (undefined)
            const auto ser_value = value.is(XNone) ? py::none() : trait->wrapper_f_serialize(my_class(), value);
            res[trait_name] = ser_value;
        }
    }
    if (res.empty())
        throw py::value_error(py::str("{}/{} - no storable traits found").format(class_name(), id_value()));

    return res;
}

void BTraitable::deserialize_traits(const py::dict& trait_values) {
    const auto proc = ThreadContext::current_traitable_proc();

    const auto XNone = PyLinkage::XNone();
    for (const auto &[trait_name_handle, trait_handle] : my_class()->trait_dir()) {
        const auto trait = trait_handle.cast<BTrait*>();
        if (trait->flags_on(BTraitFlags::RESERVED) || trait->flags_on(BTraitFlags::RUNTIME) || trait->flags_on(BTraitFlags::ID) && is_set(trait))
            continue;

        const auto trait_name = trait_name_handle.cast<py::object>();
        if (auto value = PyLinkage::dict_get(trait_values, trait_name); value.is(XNone))
            proc->invalidate_trait_value(this, trait);      //-- TODO: should we set None instead?
        else {
            //-- As XNone is serialized as None, get it back, if any
            const auto deser_value = value.is_none() ? XNone : trait->wrapper_f_deserialize(my_class(), value);
            if (const BRC rc(set_value(trait, deser_value)); !rc)
                throw py::value_error(rc.error());
        }
    }
}

py::object BTraitable::_reload(const bool rev_only) {
    if (const auto cls = my_class(); cls->may_exist_in_store() && m_tid.is_valid()) {
        const auto needs_lazy_load = lazy_load_flags() & XCache::LOAD_REQUIRED;
        const auto loaded_data = needs_lazy_load ? lazy_load_if_needed() : cls->load_data(id());
        if (loaded_data.is_none())
            return loaded_data;

        auto serialized_data = loaded_data.cast<py::dict>();
        if (rev_only) {
            const auto revision = cls->get_field(serialized_data, BNucleus::REVISION_TAG());
            serialized_data.clear();
            serialized_data[BNucleus::REVISION_TAG()] = revision;
        }
        if (needs_lazy_load && ThreadContext::current_cache() == m_origin_cache)
            return serialized_data; // -- already loaded in current cache

        const auto revision = cls->get_field(serialized_data, BNucleus::REVISION_TAG());
        set_revision(revision);
        deserialize_traits(serialized_data);
        return serialized_data;
    }
    return py::none();
}

