//
// Created by AMD on 5/21/2024.
//
//#include <boost/uuid/uuid.hpp>

#include <uuid.h>
#include "btraitable.h"
//#include "crypto/uuid_v4.h"
#include "crypto/hashpp.h"

#include "brc.h"

std::string BTraitable::exogenous_id() {
    //UUIDv4::UUIDGenerator<std::mt19937_64> uuid_gen;
    //return uuid_gen.getUUID().str();
    //TODO: only initialize generator once
    std::random_device rd;
    auto seed_data = std::array<int, std::mt19937::state_size> {};
    std::generate(std::begin(seed_data), std::end(seed_data), std::ref(rd));
    std::seed_seq seq(std::begin(seed_data), std::end(seed_data));
    std::mt19937 generator(seq);
    return uuids::to_string(uuids::uuid_random_generator{generator}());
}

std::string BTraitable::endogenous_id() {
    std::ostringstream regular_part;
    std::ostringstream hashable_part;

    bool first = true;
    bool hashable = false;
    for (auto item : m_class->trait_dir()) {
        auto trait = item.second.cast<BTrait*>();
        if (trait->flags_on(BTraitFlags::ID)) {
            auto value = get_value(trait);
            if (value.is(PyLinkage::XNone()))
                throw py::value_error(py::str("{}.{} is undefined").format(m_class->name(), item.first));

            auto svalue = py::cast<std::string>(py::str("{}").format(value));     // TODO: trait->serialize_for_id(value);
            if (!trait->flags_on(BTraitFlags::HASH)) {
                if (first) {
                    regular_part << svalue;
                    first = false;
                }
                else
                    regular_part << '|' << svalue;

            } else {
                hashable_part << svalue;
                hashable = true;
            }
        }
    }

    if (hashable) {
        auto hashed = hashpp::get::getHash(hashpp::ALGORITHMS::MD5, hashable_part.str());
        regular_part << '|' << hashed << "00";
    }

    return regular_part.str();
}


class IdCache : public BCache {
    BTraitable  *m_obj;
public:
    explicit IdCache(BTraitable* obj) : m_obj(obj)                      {}

    ObjectCache* find_object_cache(const TID& tid, bool must_exist) const final     { return m_obj->id_cache(); }
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
    //m_id_cache = new ObjectCache();
    //m_cache = new IdCache(this);
    m_id_cache = nullptr;
    m_cache = nullptr;
    if (!m_class->is_id_endogenous()) {
        m_id = exogenous_id();
        m_tid.set(m_class, &m_id);
    }
}

BTraitable::BTraitable(const py::object& cls, const std::string& id, const py::kwargs& trait_values) {
    m_id = id;
    m_class = cls.cast<BTraitableClass*>();
    m_tid.set(m_class, &m_id);
    if (trait_values.empty()) {
        m_id_cache = nullptr;
        m_cache = nullptr;
    }
    else {
        auto cache = ThreadContext::current_cache();
        auto oc = cache->find_or_create_object_cache(m_tid);
        BRC rc(set_values(trait_values));
        if (!rc)
            throw py::value_error(rc.error());
    }
}

BTraitable::BTraitable(const py::object& cls, const py::kwargs& trait_values) {
    m_class = cls.cast<BTraitableClass*>();
    m_id_cache = new ObjectCache();
    m_cache = new IdCache(this);

    auto iter = trait_values.begin();
    auto end_iter = trait_values.end();

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
            m_id = endogenous_id();
        }

        m_tid.set(m_class, &m_id);

        if (m_class->instance_exists(m_tid)) {
            if( iter != end_iter)   // there are non ID traits to set - possible revision conflict!
                throw py::value_error(py::str("Trying to set non ID traits for already existing object {}/{}").format(m_class->name(), m_id));

            clear_id_cache();
        }
        else {      // new instance
            auto cache = ThreadContext::current_cache();
            cache->register_object(this);
        }
    }

    // Check if there are non ID traits to set
    for(; iter != end_iter; ++iter) {
        auto trait_name = iter->first.cast<py::object>();
        auto trait = m_class->find_trait(trait_name);
        if (!trait)
            continue;       // skipping unknown trait names

        auto value = iter->second.cast<py::object>();
        BRC rc(set_value(trait, value));
        if (!rc)
            throw py::value_error(py::str(rc.error()));
    }
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

py::object BTraitable::set_values(const py::dict& trait_values, bool ignore_unknown_traits) {
    auto proc = ThreadContext::current_traitable_proc_bound();
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

    py::dict res;
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