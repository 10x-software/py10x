//
// Created by AMD on 3/7/2025.
//

#include "xcache.h"

XCache* XCache::s_default = new XCache();

ObjectCache* XCache::find_or_create_object_cache(const TID& tid) {
    if (tid.is_valid()) {
        auto it = m_data.find(tid);
        if (it != m_data.end())
            return it->second;

        //-- the object cache is not there, we have a lazy tid reference (if valid) - let's load the object
        tid.cls()->load(tid.id(), true);

        //-- check if loaded successfully, otherwise create it
        it = m_data.find(tid);
        if (it != m_data.end())
            return it->second;

        auto oc = new ObjectCache();
        m_data.insert({tid, oc});
        return oc;
    }

    auto key = (TID*)&tid;
    auto it = m_tmp_data.find(key);
    if (it != m_tmp_data.end())
        return it->second;

    auto oc = new ObjectCache();
    m_tmp_data.insert({key, oc});
    return oc;
}
