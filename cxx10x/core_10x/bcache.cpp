//
// Created by AMD on 12/16/2024.
//

#include "bcache.h"
#include "btraitable.h"

TraitNodesWithArgs::~TraitNodesWithArgs() {
    for(auto iter = begin(); iter != end(); ++iter) {
        auto nwa = iter->second;
        for(auto it = nwa->begin(); it != nwa->end(); ++it) {
            auto node = it->second;
            node->unlink();
            delete node;
        }
        delete nwa;
    }
    clear();
}

BCache *BCache::s_default = new BCache();

//ObjectCache* BCache::find_object_cache(const TID& tid, bool must_exist) const {
//    auto it = m_data.find(tid);
//    if (it != m_data.end())
//        return it->second;
//
//    auto oc = m_parent ? m_parent->find_object_cache(tid, false) : nullptr;
//    if (!oc && must_exist)
//        throw py::value_error(py::str(
//                "Unknown instance of {}.\n"
//                "Most probably, it's been created in out of reach Cache Layer\n"
//                "id = {}"
//        ).format(tid.cls()->name(), tid.id()));
//
//    return oc;
//}

ObjectCache* BCache::create_object_cache(const TID &tid) {
    auto it = m_data.find(tid);
    if (it != m_data.end())
        return it->second;

    auto oc = new ObjectCache();
    m_data.insert({tid, oc});
    return oc;
}

ObjectCache* BCache::find_or_create_object_cache(const TID &tid) {
    auto it = m_data.find(tid);
    if (it != m_data.end())
        return it->second;

    //-- the object cache is not there, we have a lazy tid reference - let's load the object
    tid.cls()->load(tid.id(), true);

    //-- check if loaded successfully, otherwise create it
    return create_object_cache(tid);
}

void BCache::register_object(BTraitable* obj) {
    std::unique_lock guard(m_rw_mutex);

    auto tid= obj->tid();
    auto it = m_data.find(tid);
    if (it != m_data.end())
        obj->clear_id_cache();

    else {
        m_data.insert({ tid, obj->id_cache() });
        obj->clear_id_cache(false);
    }
}

void BCache::unregister_object(const TID& tid) {
    std::unique_lock guard(m_rw_mutex);

    auto it = m_data.find(tid);
    if (it != m_data.end()) {
        auto oc = it->second;
        delete oc;
        m_data.erase(it);
    }
}

void BCache::unregister_object(BTraitable *obj) {
    unregister_object(obj->tid());
}
