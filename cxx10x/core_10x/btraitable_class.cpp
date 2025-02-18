//
// Created by AMD on 1/20/2025.
//

#include <algorithm>

#include "btraitable_class.h"
#include "btrait.h"
#include "bcache.h"
#include "thread_context.h"

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
    auto oc = cache->find_object_cache(tid, false);
    return oc != nullptr;
}

bool BTraitableClass::instance_exists(const TID &tid) const {
    auto cache = ThreadContext::current_cache();
    auto oc = cache->find_object_cache(tid, false);
    // TODO: add code to check if Traitable with this TID exists in Entity Store!
    return oc != nullptr;
}