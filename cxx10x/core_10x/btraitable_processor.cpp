//
// Created by AMD on 7/2/2024.
//

#include "btraitable_processor.h"
#include "bnode.h"
#include "btrait.h"
#include "btraitable.h"
#include "simple_cache_layer.h"

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
    proc->use_cache(BCache::default_cache());
    return proc;
}

void BTraitableProcessor::export_nodes() {
    m_cache->export_nodes();
}

void BTraitableProcessor::begin_using() {
    auto cache = own_cache();
    if (cache)
        ThreadContext::cache_push(cache);

    ThreadContext::traitable_proc_push(this);
}

void BTraitableProcessor::end_using() {
    auto tp = ThreadContext::traitable_proc_pop();
    if (tp != this)
        throw py::value_error(py::str("Mismanaged XControl block"));

    if (own_cache())
        ThreadContext::cache_pop();
}

bool BTraitableProcessor::is_valid(BTraitable* obj, BTrait* trait) const {
    auto node = cache()->find_node(obj->tid(), trait);
    return node != nullptr && node->is_valid();
}

//---- Setting a value

void BTraitableProcessor::check_value(BTraitable *obj, BTrait *trait, const py::object& value) {
    if(!value.get_type().is(trait->data_type()))    // TODO: we may want to use is_acceptable_type() method  of the trait
        throw py::type_error(py::str("Trying to set {}.{} ({}) to {}").format(obj->class_name(), trait->name(), trait->data_type(), value));
}

py::object BTraitableProcessor::set_trait_value(BTraitable *obj, BTrait *trait, const py::object& value) {
    auto converted_value = adjust_set_value(obj, trait, value);
    if (!trait->f_set.is_none())     // custom setter is defined
        return trait->wrapper_f_set(obj, converted_value);

    return raw_set_trait_value(obj, trait, converted_value);
}

py::object BTraitableProcessor::set_trait_value(BTraitable *obj, BTrait *trait, const py::object& value, const py::args& args) {
    auto converted_value = adjust_set_value(obj, trait, value);
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

    py::object get_style_sheet(BTraitable* obj, BTrait* trait) {
        return trait->proc()->get_style_sheet_off_graph(this, obj, trait);
    }

    py::object adjust_set_value(BTraitable* obj, BTrait* trait, const py::object& value) override {
        return value;
    }

    py::object raw_set_trait_value(BTraitable* obj, BTrait* trait, const py::object& value) final {
        return trait->proc()->raw_set_value_off_graph(this, obj, trait, value);
    }

    py::object raw_set_trait_value(BTraitable* obj, BTrait* trait, const py::object& value, const py::args& args) final {
        return trait->proc()->raw_set_value_off_graph(this, obj, trait, value, args);
    }
};

class OffGraphNoConvertDebug : public OffGraphNoConvertNoDebug {
public:
    py::object adjust_set_value(BTraitable* obj, BTrait* trait, const py::object& value) final {
        check_value(obj, trait, value);
        return value;
    }
};

class OffGraphConvertNoDebug : public OffGraphNoConvertNoDebug {
public:
    py::object adjust_set_value(BTraitable* obj, BTrait* trait, const py::object& value) final {
        return obj->from_any(trait, value);
    }
};

class OffGraphConvertDebug : public OffGraphNoConvertNoDebug {
public:
    py::object adjust_set_value(BTraitable* obj, BTrait* trait, const py::object& value) final {
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

    py::object adjust_set_value(BTraitable *obj, BTrait* trait, const py::object& value) override {
        return value;
    }

    py::object raw_set_trait_value(BTraitable* obj, BTrait* trait, const py::object& value) override {
        return trait->proc()->raw_set_value_on_graph(this, obj, trait, value);
    }

    py::object raw_set_trait_value(BTraitable* obj, BTrait* trait, const py::object& value, const py::args& args) override {
        return trait->proc()->raw_set_value_on_graph(this, obj, trait, value, args);
    }
};

class OnGraphNoConvertDebug : public OnGraphNoConvertNoDebug {
public:
    py::object adjust_set_value(BTraitable* obj, BTrait* trait, const py::object& value) final {
        check_value(obj, trait, value);
        return value;
    }
};

class OnGraphConvertNoDebug : public OnGraphNoConvertNoDebug {
public:
    py::object adjust_set_value(BTraitable* obj, BTrait* trait, const py::object& value) final {
        return obj->from_any(trait, value);
    }
};

class OnGraphConvertDebug : public OnGraphNoConvertNoDebug {
public:
    py::object adjust_set_value(BTraitable* obj, BTrait* trait, const py::object& value) final {
        auto converted_value = obj->from_any(trait, value);
        check_value(obj, trait, converted_value);
        return converted_value;
    }
};

BTraitableProcessor* BTraitableProcessor::create_raw(unsigned int flags) {
    BTraitableProcessor *proc;
    switch(flags) {
        case PLAIN:                         proc = new OffGraphNoConvertNoDebug();  break;
        case DEBUG:                         proc = new OffGraphNoConvertDebug();    break;
        case CONVERT_VALUES:                proc = new OffGraphConvertNoDebug();    break;
        case CONVERT_VALUES | DEBUG:        proc = new OffGraphConvertDebug();      break;

        case ON_GRAPH:                      proc = new OnGraphNoConvertNoDebug();   break;
        case ON_GRAPH|DEBUG:                proc = new OnGraphNoConvertDebug();     break;
        case ON_GRAPH|CONVERT_VALUES:       proc = new OnGraphConvertNoDebug();     break;
        case ON_GRAPH|CONVERT_VALUES|DEBUG: proc = new OnGraphConvertDebug();       break;

        default:
            throw std::exception("Unrecognized flags");
    }

    proc->set_flags(flags);
    return proc;
}

BTraitableProcessor* BTraitableProcessor::create(int on_graph, int convert_values, int debug, bool use_parent_cache, bool use_default_cache) {
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

    if (flags & ON_GRAPH) {
        if (!use_parent_cache || !(parent_flags & ON_GRAPH)) {
            auto cache = new SimpleCacheLayer();
            proc->use_own_cache(cache);
        }
        else
            proc->use_cache(parent->cache());
    }
    else {  //-- OFF_GRAPH
        if (use_default_cache)
            proc->use_cache(BCache::default_cache());

        else {
            if (!use_parent_cache || parent_flags & ON_GRAPH) {
                auto cache = new BCache();
                proc->use_own_cache(cache);
            } else
                proc->use_cache(parent->cache());
        }
    }

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

