//
// Created by AMD on 1/20/2025.
//

#include <algorithm>

#include "btraitable_class.h"
#include "bnucleus.h"
#include "btrait.h"
#include "xcache.h"
#include "thread_context.h"
#include "btraitable.h"
#include "bprocess_context.h"
#include "btraitable_ui_extension.h"


//BTraitableClass::~BTraitableClass() {
//    delete m_ui_class;
//}

BUiClass* BTraitableClass::bui_class() {
    if (!m_ui_class)
        m_ui_class = new BUiClass(this);
    return m_ui_class;
}

bool BTraitableClass::is_storable_get() const {
    for (auto item : trait_dir()) {
        auto trait = item.second.cast<BTrait*>();
        if (!trait->flags_on(BTraitFlags::RUNTIME) && !trait->flags_on(BTraitFlags::RESERVED))
            return true;
    }
    return false;
}

bool BTraitableClass::is_id_endogenous_get() const {
    for (auto item : trait_dir()) {
        auto trait = item.second.cast<BTrait*>();
        if (trait->flags_on(BTraitFlags::ID))
            return true;
    }
    return false;
}

bool BTraitableClass::is_anonymous_get() const {
    return PyLinkage::issubclass(py_class(), PyLinkage::anonymous_class());
}

BTrait* BTraitableClass::find_trait(const py::object& trait_name) const {
    auto trait = PyLinkage::dict_get(trait_dir(), trait_name);
    if (trait.is(PyLinkage::XNone()))
        return nullptr;

    return trait.cast<BTrait*>();
}

bool BTraitableClass::instance_in_cache(const TID &tid) {
    auto cache = ThreadContext::current_traitable_proc()->cache();
    return cache->find_object_cache(tid) != nullptr;
}

bool BTraitableClass::instance_in_store(const TID &tid) const {
    if (!tid.is_valid() || BProcessContext::PC.flags_on(BProcessContext::CACHE_ONLY))
        return false;

    return m_py_class.attr("exists_in_store")(tid.id()).cast<bool>();
}

py::object BTraitableClass::load(const py::object& id) {
    if (!is_storable() || is_anonymous() || !TID::is_valid(id) || BProcessContext::PC.flags_on(BProcessContext::CACHE_ONLY))
        return py::none();

    auto serialized_data = load_data(id);
    if (serialized_data.is_none())
        return serialized_data;

    return BTraitable::deserialize_object(this, id.attr("collection_name"), serialized_data);
}

py::object BTraitableClass::load_data(const py::object& id) const {
    return m_py_class.attr("load_data")(id);
}

