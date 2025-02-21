//
// Created by AMD on 5/21/2024.
//

#include <uuid.h>
#include "btraitable.h"
#include "py_hasher.h"

#include "brc.h"

py::object BTraitable::exogenous_id() {
    return PyHasher::uuid();
}

py::object BTraitable::endogenous_id() {
    py::list regulars;
    auto hasher = PyHasher();

    for (auto item : m_class->trait_dir()) {
        auto trait = item.second.cast<BTrait*>();
        if (trait->flags_on(BTraitFlags::ID)) {
            auto value = get_value(trait);
            if (value.is(PyLinkage::XNone()))
                throw py::value_error(py::str("{}.{} is undefined").format(m_class->name(), item.first));

            auto value_for_id = trait->wrapper_f_to_id(this, value);
            if (!trait->flags_on(BTraitFlags::HASH))
                regulars.append(value_for_id);
            else
                hasher.update(value_for_id);
        }
    }

    if (hasher.is_updated())
        regulars.append(hasher.hexdigest());

    regulars.append(py::str("00"));
    return py::str("").attr("join")(regulars);
}

class IdCache : public BCache {
    BTraitable  *m_obj;
public:
    explicit IdCache(BTraitable* obj) : m_obj(obj)                      {}

    ObjectCache* find_object_cache(const TID& tid) const final      { return m_obj->id_cache(); }
    ObjectCache* find_or_create_object_cache(const TID& tid) final  { return m_obj->id_cache(); }
};

class CacheMocker {
    BTraitableProcessor*    m_proc;
    BCache*                 m_cur_cache;

public:

    explicit CacheMocker(BTraitableProcessor* proc, BTraitable* obj) : m_proc(proc) {
        m_cur_cache = proc->cache();
        m_cur_cache->shared_mutex()->lock();
        proc->use_cache(obj->cache());
    }

    ~CacheMocker() {
        m_proc->use_cache(m_cur_cache);
        m_cur_cache->shared_mutex()->unlock();
    }
};

BTraitable::BTraitable(const py::object& cls) {
    m_class = cls.cast<BTraitableClass*>();
    m_id_cache = nullptr;
    m_cache = nullptr;
    if (!m_class->is_id_endogenous()) {
        auto id = exogenous_id();
        m_tid.set(m_class, id);
    }
}

BTraitable::BTraitable(const py::object& cls, const py::object& id) {
    m_class = cls.cast<BTraitableClass*>();
    m_tid.set(m_class, id);
    m_id_cache = nullptr;
    m_cache = nullptr;
}

BTraitable::BTraitable(const py::object& cls, const py::kwargs& trait_values) {
    m_class = cls.cast<BTraitableClass*>();
    m_id_cache = new ObjectCache();
    m_cache = new IdCache(this);

    auto iter = trait_values.begin();
    auto end_iter = trait_values.end();

    py::object id;
    if (m_class->is_id_endogenous()) {
        {
            CacheMocker cache_guard(ThreadContext::current_traitable_proc(), this);

            for (; iter != end_iter; ++iter) {
                auto trait_name = iter->first.cast<py::object>();

                auto trait = m_class->find_trait(trait_name);
                if (!trait)
                    continue;       // skipping unknown trait names

                if (!trait->flags_on(BTraitFlags::ID))    // No ID traits anymore -> out to build the ID
                    break;

                // set an ID trait
                auto value = iter->second.cast<py::object>();
                BRC rc(set_value(trait, value));
                if (!rc)
                    throw py::value_error(rc.error());
            }
            id = endogenous_id();
        }

        m_tid.set(m_class, id);

        if (m_class->instance_exists(m_tid)) {
            if( iter != end_iter)   // there are non ID traits to set - possible revision conflict!
                throw py::value_error(py::str("Trying to set non ID traits for already existing object {}/{}").format(m_class->name(), id));

            clear_id_cache();
        } else {      // new instance
            auto cache = ThreadContext::current_cache();
            cache->register_object(this);
        }
    } else {        // ID exogenous
        id = exogenous_id();
        m_tid.set(m_class, id);
    }

    // Check if there are non ID traits to set
    BRC rc(set_values(trait_values, &iter));
    if (!rc)
        throw py::value_error(py::str(rc.error()));
}

BTraitable::~BTraitable() {
    delete m_cache;
    //auto cache = ThreadContext::current_cache();
    //cache->unlink_object(tid());
    delete m_id_cache;
}

py::object BTraitable::from_any(BTrait* trait, const py::object& value) {
    if (py::isinstance(value, trait->m_datatype))
        return value;

    if (py::isinstance<py::str>(value))
        return trait->f_from_str(this, trait, value);

    return trait->f_from_any_xstr(this, trait, value);
}

py::object BTraitable::set_values(const py::dict& trait_values, dict_iter* p_iter, bool ignore_unknown_traits) {
    auto iter = p_iter ? *p_iter : trait_values.begin();
    auto proc = ThreadContext::current_traitable_proc_bound();
    for (; iter != trait_values.end(); ++iter) {
        auto trait_name = iter->first.cast<py::object>();
        auto trait = m_class->find_trait(trait_name);
        if (!trait) {
            if (!ignore_unknown_traits)
                throw py::type_error(py::str("{}.{} - unknown trait").format(m_class->name(), trait_name));

            continue;
        }

        auto value = iter->second.cast<py::object>();
        BRC rc(proc->set_trait_value(this, trait, value));
        if (!rc)
            return rc();
    }

    return PyLinkage::RC_TRUE();
}

py::object BTraitable::serialize(bool embed) {
    if (!embed)
        return py::str(id());

    py::dict res;
    res["_id"] = id();

    for (auto item : m_class->trait_dir()) {
        auto trait = item.second.cast<BTrait*>();
        if (!trait->flags_on(BTraitFlags::RUNTIME)) {
            auto trait_name = item.first.cast<py::object>();
            auto value = get_value(trait);
            if (value.is(PyLinkage::XNone()))
                throw py::value_error(py::str("{}.{} - undefined value").format(m_class->name(), trait_name));

            auto ser_value = trait->f_serialize(this, trait, value);
            res[trait_name] = ser_value;
        }
    }

    return res;
}

void BTraitable::deserialize(const py::dict& serialized_data) {
    auto cache = ThreadContext::current_cache();
    cache->create_object_cache(m_tid);

    for (auto item : serialized_data) {
        auto trait_name = item.first.cast<py::object>();
        auto trait = m_class->find_trait(trait_name);
        if (trait) {
            auto value = item.second.cast<py::object>();
            auto deser_value = trait->f_deserialize(nullptr, trait, value);
            BRC rc(set_value(trait, deser_value));
            if (!rc)
                throw py::value_error(rc.error());
        }
    }
}

void BTraitable::reload() {
    auto serialized_data = m_class->load_data(id());
    if (serialized_data.is_none())
        throw py::value_error(py::str("{}/{} - failed to reload").format(class_name(), id()));

    deserialize(serialized_data);
}