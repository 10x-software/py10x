//
// Created by AMD on 5/18/2024.
//

#include "cache.h"
#include "btraitable.h"

ObjectCache* Cache::find_object_cache(BTraitable& obj) const {
    auto i = m_by_object.find(&obj);
    return (i != m_by_object.end())? i->second : nullptr;
}

ObjectCache* Cache::find_or_create_object_cache(BTraitable& obj) {
    auto obj_cache = find_object_cache(obj);
    if (obj_cache)
        return obj_cache;

    auto cls = obj.cls();
    auto eid = obj.id();
    auto i = m_by_class.find(cls);
    if (i == m_by_class.end()) {
        auto cache_by_id = new CacheByEID();
        m_by_class.insert({cls, cache_by_id});
        obj_cache = new ObjectCache();
        cache_by_id->insert({eid, obj_cache});
        m_by_object.insert({&obj, obj_cache});
        return obj_cache;
    }

    auto cache_by_id = i->second;
    auto ci= cache_by_id->find(eid);
    if (ci == cache_by_id->end()) {
        obj_cache = new ObjectCache();
        cache_by_id->insert({eid, obj_cache});
        m_by_object.insert({&obj, obj_cache});
        return obj_cache;
    }

    obj_cache = ci->second;
    obj_cache->link();
    m_by_object.insert({&obj, obj_cache});
    return obj_cache;
}

//BasicNode * Cache::find_node(const py::object& cls, const EID& eid, BTrait *trait) const {
//    auto ci = m_by_class.find(cls);
//    if (ci == m_by_class.end())
//        return nullptr;
//
//    auto map_by_eid = ci->second;
//    auto ti = map_by_eid->find(eid);
//    if (ti == map_by_eid->end())
//        return nullptr;
//
//    return ti->second->find_node(trait);
//}
//
//BasicNode* Cache::find_or_create_node(const py::object& cls, const EID& eid, const py::object& traitable, BTrait *trait) {
//    CacheByEID *cache_by_eid;
//    auto ci = m_by_class.find(cls);
//    if (ci == m_by_class.end()) {
//        cache_by_eid = new CacheByEID();
//        m_by_class.insert({cls, cache_by_eid});
//    } else
//        cache_by_eid = ci->second;
//
//    ObjectCache* object_cache;
//    auto ti = cache_by_eid->find(eid);
//    if (ti == cache_by_eid->end()) {
//        object_cache = new ObjectCache(traitable, NODE_TYPE::BASIC );
//        cache_by_eid->insert({eid, object_cache});
//    } else
//        object_cache = ti->second;
//
//    return object_cache->find_or_create_node(trait);
//}