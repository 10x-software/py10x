//
// Created by AMD on 7/2/2024.
//

#include "btraitable_processor.h"

#include <filesystem>

#include "bnode.h"
#include "bprocess_context.h"
#include "btrait.h"
#include "btraitable.h"
#include "xcache.h"
#include "brc.h"


Placebo::Placebo(ExecStack* xstack) : m_stack(xstack) {
    if (xstack) {
        auto node = new BasicNode();
        m_node = node;
        xstack->push(node);
    } else
    m_node = nullptr;
}

Placebo::~Placebo() {
    if (m_stack) {
        m_stack->pop();
        delete m_node;
    }
}

unsigned BTraitableProcessor::s_default_type = PLAIN;   // = OffGraphNoConvertNoDebug;

BTraitableProcessor::~BTraitableProcessor() {
    if (m_own_cache)
        delete m_cache;
}

BTraitableProcessor* BTraitableProcessor::create_default() {
    auto proc = create_raw(s_default_type);
    proc->use_cache(XCache::default_cache());
    return proc;
}


bool BTraitableProcessor::accept_existing(BTraitable *obj) const {
    // returns true if the object existed in cache or storage
    const auto id_value = obj->tid().is_valid() ? obj->id_value() : obj->endogenous_id();
    const auto tid = TID(obj->my_class(), PyLinkage::traitable_id(id_value, obj->tid().coll_name()));
    if (const auto origin_cache = m_cache->find_origin_cache(tid)) {
        if ( origin_cache->lazy_load_flags(tid) & XCache::LOAD_REQUIRED_MUST_EXIST && !obj->my_class()->instance_in_store(tid))
            // e.g. created with existing_object_by_id
            return false;
        obj->set_id_value(id_value);
        obj->set_origin_cache(origin_cache);
        return true;
    }
    if (obj->my_class()->instance_in_store(tid)) {
        m_cache->remove_temp_object_cache(obj->tid());
        obj->set_id_value(id_value);
        obj->set_origin_cache(m_cache);
        obj->set_lazy_load_flags(XCache::LOAD_REQUIRED_MUST_EXIST| flags() & DEBUG);
        return true;
    }
    return false;
}

py::object BTraitableProcessor::share_object(BTraitable* obj, const bool accept_existing) const {
    if (obj->tid().is_valid())
        return PyLinkage::RC_TRUE();

    const auto id_value = obj->endogenous_id(); //-- raises if any id trait is undefined
    const auto &tid = obj->tid();
    if (const auto origin_cache =  m_cache->find_origin_cache(TID(tid.cls(), PyLinkage::traitable_id(id_value, tid.coll_name())))) {
        if (!accept_existing) {
            // -- possible conflict with existing instance!
            BRC rc;
            rc.add_data(id_value);
            return rc();
        }
        m_cache->remove_temp_object_cache(tid);
        obj->set_id_value(id_value);
        obj->set_origin_cache(origin_cache);
        return PyLinkage::RC_TRUE();
    }

    // -- object does not exist in any cache
    obj->set_id_value(id_value);
    obj->set_origin_cache(m_cache);
    m_cache->make_permanent(tid);
    if (accept_existing && obj->my_class()->may_exist_in_store())
        obj->set_lazy_load_flags(XCache::LOAD_REQUIRED | flags() & DEBUG);
    return PyLinkage::RC_TRUE();
}

void BTraitableProcessor::export_nodes() const {
    m_cache->export_nodes();
}

void BTraitableProcessor::begin_using() {
    if (const auto cache = own_cache())
        ThreadContext::cache_push(cache);

    ThreadContext::traitable_proc_push(this);
}

void BTraitableProcessor::end_using() const {
    auto tp = ThreadContext::traitable_proc_pop();
    if (tp != this)
        throw py::value_error(py::str("Mismanaged XControl block"));

    if (own_cache())
        ThreadContext::cache_pop();
}

bool BTraitableProcessor::is_valid(const BTraitable* obj, const BTrait* trait) const {
    const auto node = cache()->find_node(obj->tid(), trait);
    return node != nullptr && node->is_valid();
}

bool BTraitableProcessor::is_valid(const BTraitable* obj, const BTrait* trait, const py::args& args) const {
    const auto node = cache()->find_node(obj->tid(), trait, args);
    return node != nullptr && node->is_valid();
}

bool BTraitableProcessor::is_set(const BTraitable* obj, const BTrait* trait) const {
    const auto node = cache()->find_node(obj->tid(), trait);
    return node != nullptr && node->is_set();
}

bool BTraitableProcessor::is_set(const BTraitable* obj, const BTrait* trait, const py::args& args) const {
    const auto node = cache()->find_node(obj->tid(), trait, args);
    return node != nullptr && node->is_set();
}

// BasicNode* BTraitableProcessor::get_node(BTraitable *obj, BTrait *trait) const {
//     return cache()->find_node(obj->tid(), trait);
// }
//
// BasicNode* BTraitableProcessor::get_node(BTraitable *obj, BTrait *trait, const py::args& args) const {
//     return cache()->find_node(obj->tid(), trait, args);
// }

//---- Setting a value

void BTraitableProcessor::check_value(BTraitable *obj, const BTrait *trait, const py::object& value) {
    const auto value_type = PyLinkage::type(value);
    if (const auto rc = trait->wrapper_f_is_acceptable_type(obj, value_type); !rc)
        throw py::type_error(py::str("{}.{} ({}) - invalid value '{}'").format(obj->class_name(), trait->name(), trait->data_type(), value));
}

py::object BTraitableProcessor::set_trait_value(BTraitable *obj, const BTrait *trait, const py::object& value) const {
    if (trait->flags_on(BTraitFlags::ID) && obj->tid().is_valid() && obj->is_set(trait))
        return PyLinkage::RC_TRUE(); // nothing to do for ID traits that are already set if ID is already valid
    const auto converted_value = adjust_set_value(obj, trait, value);
    if (!trait->f_set.is_none())     // custom setter is defined
        return trait->wrapper_f_set(obj, converted_value);

    return raw_set_trait_value(obj, trait, converted_value);
}

py::object BTraitableProcessor::set_trait_value(BTraitable *obj, BTrait *trait, const py::object& value, const py::args& args) const {
    const auto converted_value = adjust_set_value(obj, trait, value);
    if (!trait->f_set.is_none())     // custom setter is defined
        return trait->wrapper_f_set(obj, converted_value, args);

    return raw_set_trait_value(obj, trait, converted_value, args);
}

class OffGraphNoConvertNoDebug : public BTraitableProcessor {
public:
    void invalidate_trait_value(BTraitable* obj, BTrait* trait) final {
        trait->proc()->invalidate_value_off_graph(this, obj, trait);
    }

    void invalidate_trait_value(BTraitable* obj, BTrait* trait, const py::args& args) final {
        trait->proc()->invalidate_value_off_graph(this, obj, trait, args);
    }

    py::object get_trait_value(BTraitable* obj, BTrait* trait) final {
        return trait->proc()->get_value_off_graph(this, obj, trait);
    }

    py::object get_trait_value(BTraitable* obj, BTrait* trait, const py::args& args) final {
        return trait->proc()->get_value_off_graph(this, obj, trait, args);
    }

    py::object get_choices(BTraitable* obj, BTrait* trait) final {
        return trait->proc()->get_choices_off_graph(this, obj, trait);
    }

    py::object get_style_sheet(BTraitable* obj, BTrait* trait) final {
        return trait->proc()->get_style_sheet_off_graph(this, obj, trait);
    }

    py::object adjust_set_value(BTraitable* obj, const BTrait* trait, const py::object& value) const override {
        return value;
    }

    py::object raw_set_trait_value(BTraitable* obj, const BTrait* trait, const py::object& value) const final {
        return trait->proc()->raw_set_value_off_graph(this, obj, trait, value);
    }

    py::object raw_set_trait_value(BTraitable* obj, const BTrait* trait, const py::object& value, const py::args& args) const final {
        return trait->proc()->raw_set_value_off_graph(this, obj, trait, value, args);
    }
};

class OffGraphNoConvertDebug : public OffGraphNoConvertNoDebug {
public:
    py::object adjust_set_value(BTraitable* obj, const BTrait* trait, const py::object& value) const final {
        if (value.is_none() || value.is(PyLinkage::XNone()))
            return value;

        check_value(obj, trait, value);
        return value;
    }
};

class OffGraphConvertNoDebug : public OffGraphNoConvertNoDebug {
public:
    py::object adjust_set_value(BTraitable* obj, const BTrait* trait, const py::object& value) const final {
        if (value.is_none() || value.is(PyLinkage::XNone()))
            return value;

        return obj->from_any(trait, value);
    }
};

class OffGraphConvertDebug : public OffGraphNoConvertNoDebug {
public:
    py::object adjust_set_value(BTraitable* obj, const BTrait* trait, const py::object& value) const final {
        if (value.is_none() || value.is(PyLinkage::XNone()))
            return value;

        auto converted_value = obj->from_any(trait, value);
        check_value(obj, trait, converted_value);
        return converted_value;
    }
};

class OnGraphNoConvertNoDebug : public BTraitableProcessor {
public:
    void invalidate_trait_value(BTraitable* obj, BTrait* trait) final {
        trait->proc()->invalidate_value_on_graph(this, obj, trait);
    }

    void invalidate_trait_value(BTraitable* obj, BTrait* trait, const py::args& args) final {
        trait->proc()->invalidate_value_on_graph(this, obj, trait, args);
    }

    py::object get_trait_value(BTraitable* obj, BTrait* trait) final {
        return trait->proc()->get_value_on_graph(this, obj, trait);
    }

    py::object get_trait_value(BTraitable* obj, BTrait* trait, const py::args& args) final {
        return trait->proc()->get_value_on_graph(this, obj, trait, args);
    }

    py::object get_choices(BTraitable* obj, BTrait* trait) final {
        return trait->proc()->get_choices_on_graph(this, obj, trait);
    }

    py::object get_style_sheet(BTraitable* obj, BTrait* trait) final {
        return trait->proc()->get_style_sheet_on_graph(this, obj, trait);
    }

    py::object adjust_set_value(BTraitable *obj, const BTrait* trait, const py::object& value) const override {
        return value;
    }

    py::object raw_set_trait_value(BTraitable* obj, const BTrait* trait, const py::object& value) const override {
        return trait->proc()->raw_set_value_on_graph(this, obj, trait, value);
    }

    py::object raw_set_trait_value(BTraitable* obj, const BTrait* trait, const py::object& value, const py::args& args) const override {
        return trait->proc()->raw_set_value_on_graph(this, obj, trait, value, args);
    }
};

class OnGraphNoConvertDebug : public OnGraphNoConvertNoDebug {
public:
    py::object adjust_set_value(BTraitable* obj, const BTrait* trait, const py::object& value) const final {
        if (value.is_none() || value.is(PyLinkage::XNone()))
            return value;

        check_value(obj, trait, value);
        return value;
    }
};

class OnGraphConvertNoDebug : public OnGraphNoConvertNoDebug {
public:
    py::object adjust_set_value(BTraitable* obj, const BTrait* trait, const py::object& value) const final {
        if (value.is_none() || value.is(PyLinkage::XNone()))
            return value;

        return obj->from_any(trait, value);
    }
};

class OnGraphConvertDebug : public OnGraphNoConvertNoDebug {
public:
    py::object adjust_set_value(BTraitable* obj, const BTrait* trait, const py::object& value) const final {
        if (value.is_none() || value.is(PyLinkage::XNone()))
            return value;

        auto converted_value = obj->from_any(trait, value);
        check_value(obj, trait, converted_value);
        return converted_value;
    }
};

BTraitableProcessor* BTraitableProcessor::create_raw(const unsigned int flags) {
    BTraitableProcessor *proc;
    switch(flags & PROC_TYPE) {
        case PLAIN:                         proc = new OffGraphNoConvertNoDebug();  break;
        case DEBUG:                         proc = new OffGraphNoConvertDebug();    break;
        case CONVERT_VALUES:                proc = new OffGraphConvertNoDebug();    break;
        case CONVERT_VALUES | DEBUG:        proc = new OffGraphConvertDebug();      break;

        case ON_GRAPH:                      proc = new OnGraphNoConvertNoDebug();   break;
        case ON_GRAPH|DEBUG:                proc = new OnGraphNoConvertDebug();     break;
        case ON_GRAPH|CONVERT_VALUES:       proc = new OnGraphConvertNoDebug();     break;
        case ON_GRAPH|CONVERT_VALUES|DEBUG: proc = new OnGraphConvertDebug();       break;

        default:
            throw std::runtime_error("Unrecognized flags");
    }

    proc->set_flags(flags);
    return proc;
}

BTraitableProcessor* BTraitableProcessor::create_root() {
    // create a processor with no parent cache
    auto parent = current();
    auto flags = parent->flags();
    auto proc = create_raw(flags);
    auto cache = new XCache();
    if (flags & ON_GRAPH)
        cache->set_default_node_type(NODE_TYPE::BASIC_GRAPH);
    proc->use_own_cache(cache);
    return proc;
}

BTraitableProcessor* BTraitableProcessor::create(const int on_graph, const int convert_values, const int debug, const bool use_parent_cache, const bool use_default_cache) {
    auto parent = current();
    auto parent_flags = parent->flags();

    auto flags = parent_flags;
    if (on_graph >= 0)
        flags = on_graph == 1 ? flags | ON_GRAPH : flags & ~ON_GRAPH;

    if (convert_values >= 0)
        flags = convert_values == 1 ? flags | CONVERT_VALUES : flags & ~CONVERT_VALUES;

    if (debug >= 0)
        flags = debug == 1? flags | DEBUG : flags & ~DEBUG;

    auto proc = create_raw(flags);

    // 1. use_parent_cache uses parent's cache as its own *only* when parent and new proc are either ON_GRAPH or OFF_GRAPH
    // 2. use_default_cache forces using the default cache *only* when the new processor is OFF_GRAPH
    // 3. when both use_parent_cache and use_default_cache are true, use_default_cache takes precedence for OFF_GRAPH processors
    // TODO: should we throw exceptions when parameters are ignored?

    if (flags & ON_GRAPH) {
        if (!use_parent_cache || !(parent_flags & ON_GRAPH)) {
            auto cache = new XCache(parent->cache());
            cache->set_default_node_type(NODE_TYPE::BASIC_GRAPH);
            proc->use_own_cache(cache);
        }
        else
            proc->use_cache(parent->cache());
    }
    else {  //-- OFF_GRAPH
        if (use_default_cache)
            proc->use_cache(XCache::default_cache());

        else {
            if (!use_parent_cache || parent_flags & ON_GRAPH) {
                auto cache = new XCache(parent->cache());
                proc->use_own_cache(cache);
            } else
                proc->use_cache(parent->cache());
        }
    }

    return proc;
}

BTraitableProcessor * BTraitableProcessor::create_for_lazy_load(XCache *cache, const unsigned lazy_load_flags) {
    const auto proc_type = cache->default_node_type() == NODE_TYPE::BASIC_GRAPH ? ON_GRAPH : PLAIN;
    const auto proc = create_raw(proc_type|(lazy_load_flags&DEBUG));
    proc->use_cache(cache);
    return proc;
}

BTraitableProcessor* BTraitableProcessor::current() {
    return ThreadContext::current_traitable_proc();
}

BTraitableProcessor::Use::Use(BTraitableProcessor *proc, bool temp) : m_temp(temp) {
    ThreadContext::traitable_proc_push(proc);
}

BTraitableProcessor::Use::~Use() {
    auto tp = ThreadContext::traitable_proc_pop();
    if (m_temp)
        delete tp;
}

