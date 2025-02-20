//
// Created by AMD on 1/20/2025.
//

#include <algorithm>

#include "btraitable_class.h"
#include "btrait.h"
#include "bcache.h"
#include "thread_context.h"
#include "btraitable.h"

bool BTraitableClass::is_storable_get() {
    for (auto item : trait_dir()) {
        auto trait = item.second.cast<BTrait*>();
        if (!trait->flags_on(BTraitFlags::RUNTIME))
            return true;
    }
    return false;
}

bool BTraitableClass::is_id_endogenous_get() {
    for (auto item : trait_dir()) {
        auto trait = item.second.cast<BTrait*>();
        if (trait->flags_on(BTraitFlags::ID))
            return true;
    }
    return false;
}

BTrait* BTraitableClass::find_trait(const py::object& trait_name) const {
    auto dir = trait_dir();
    if (!dir.contains(trait_name))
        return nullptr;

    return dir[trait_name].cast<BTrait*>();
}

bool BTraitableClass::known_object(std::string& id) {
    auto cache = ThreadContext::current_cache();
    TID tid(this, &id);
    auto oc = cache->find_object_cache(tid);
    return oc != nullptr;
}

bool BTraitableClass::instance_exists(const TID &tid) const {
    auto cache = ThreadContext::current_cache();
    auto oc = cache->find_object_cache(tid);
    // TODO: add code to check if Traitable with this TID exists in Entity Store!
    return oc != nullptr;
}

py::object BTraitableClass::deserialize(const py::object& serialized_data) {
    if (py::isinstance<py::str>(serialized_data)) {     //-- just traitable's ID
        auto proc = ThreadContext::current_traitable_proc();
        if (proc->is_debug())
            return load(serialized_data);

        return m_py_class(serialized_data);     // cls(_id = serialized_data)
    }

    if (!py::isinstance<py::dict>(serialized_data))
        throw py::type_error(py::str("{}.deserialize() expects a dict, got {}").format(m_name, serialized_data));


    auto trait_values = serialized_data.cast<py::dict>();
    auto id_value = trait_values.attr("pop")("_id", py::none());
    if (id_value.is_none())
        throw py::value_error(py::str("{}.deserialize() - _id field is missing in {}").format(m_name, trait_values));

    auto py_traitable = m_py_class(id_value);    // cls(_id = id_value)
    auto traitable = py_traitable.cast<BTraitable*>();
    traitable->deserialize(trait_values);

    return py_traitable;
}

py::object BTraitableClass::load(const py::object &id) {
    return m_py_class.attr("load")(id);
}
