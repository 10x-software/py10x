//
// Created by AMD on 7/2/2024.
//

#include "btraitable_processor.h"
#include "bnode.h"
#include "btrait.h"
#include "btraitable.h"

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

unsigned BTraitableProcessor::s_default_type = PLAIN;   // = OffGraphNoConvertNoCheck;

BTraitableProcessor* BTraitableProcessor::create_default() {
    auto proc = create(s_default_type);
    assert(proc);
    proc->use_cache(BCache::default_cache());
    return proc;
}

//---- Setting a value

py::object BTraitableProcessor::check_value(BTraitable *obj, BTrait *trait, const py::object& value) {
    if(!value.get_type().is(trait->data_type()))    // TODO: we may want to use is_acceptable_type() method  of the trait
        throw py::type_error(py::str("Trying to set {}.{} ({}) to {}").format(obj->class_name(), trait->name(), trait->data_type(), value));

    return value;
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

class OffGraphNoConvertNoCheck : public BTraitableProcessor {
public:
    void invalidate_trait_value(BTraitable* obj, BTrait* trait) final {
        trait->invalidate_value_off_graph(this, obj);
    }

    void invalidate_trait_value(BTraitable* obj, BTrait* trait, const py::args& args) final {
        trait->invalidate_value_off_graph(this, obj, args);
    }

    py::object get_trait_value(BTraitable* obj, BTrait* trait) final {
        return trait->get_value_off_graph(this, obj);
    }

    py::object get_trait_value(BTraitable* obj, BTrait* trait, const py::args& args) final {
        return trait->get_value_off_graph(this, obj, args);
    }

    py::object adjust_set_value(BTraitable* obj, BTrait* trait, const py::object& value) override {
        return value;
    }

    py::object raw_set_trait_value(BTraitable* obj, BTrait* trait, const py::object& value) final {
        return trait->raw_set_value_off_graph(this, obj, value);
    }

    py::object raw_set_trait_value(BTraitable* obj, BTrait* trait, const py::object& value, const py::args& args) final {
        return trait->raw_set_value_off_graph(this, obj, value, args);
    }
};

class OffGraphNoConvertCheck : public OffGraphNoConvertNoCheck {
public:
    py::object adjust_set_value(BTraitable* obj, BTrait* trait, const py::object& value) final {
        return check_value(obj, trait, value);
    }
};

class OffGraphConvert : public OffGraphNoConvertNoCheck {
public:
    py::object adjust_set_value(BTraitable* obj, BTrait* trait, const py::object& value) final {
        return obj->from_any(trait, value);
    }
};

class OnGraphNoConvertNoCheck : public BTraitableProcessor {
public:
    void invalidate_trait_value(BTraitable* obj, BTrait* trait) final {
        trait->invalidate_value_on_graph(this, obj);
    }

    void invalidate_trait_value(BTraitable* obj, BTrait* trait, const py::args& args) final {
        trait->invalidate_value_on_graph(this, obj, args);
    }

    py::object get_trait_value(BTraitable* obj, BTrait* trait) final {
        return trait->get_value_on_graph(this, obj);
    }

    py::object get_trait_value(BTraitable* obj, BTrait* trait, const py::args& args) final {
        return trait->get_value_on_graph(this, obj, args);
    }

    py::object adjust_set_value(BTraitable *obj, BTrait* trait, const py::object& value) override {
        return value;
    }

    py::object raw_set_trait_value(BTraitable* obj, BTrait* trait, const py::object& value) override {
        return trait->raw_set_value_on_graph(this, obj, value);
    }

    py::object raw_set_trait_value(BTraitable* obj, BTrait* trait, const py::object& value, const py::args& args) override {
        return trait->raw_set_value_on_graph(this, obj, value, args);
    }
};

class OnGraphNoConvertCheck : public OnGraphNoConvertNoCheck {
public:
    py::object adjust_set_value(BTraitable* obj, BTrait* trait, const py::object& value) final {
        return check_value(obj, trait, value);
    }
};

class OnGraphConvert : public OnGraphNoConvertNoCheck {
public:
    py::object adjust_set_value(BTraitable* obj, BTrait* trait, const py::object& value) final {
        return obj->from_any(trait, value);
    }
};

BTraitableProcessor* BTraitableProcessor::create(unsigned proc_type) {
//    static const unsigned  DEBUG            = 0x1;
//    static const unsigned  CONVERT_VALUES   = 0x2;
//    static const unsigned  ON_GRAPH         = 0x4;
    BTraitableProcessor *proc;
    switch(proc_type) {
        case PLAIN:                     proc = new OffGraphNoConvertNoCheck();  break;
        case DEBUG:                     proc = new OffGraphNoConvertCheck();    break;
        case CONVERT_VALUES:            proc = new OffGraphConvert();           break;

        case ON_GRAPH:                  proc = new OnGraphNoConvertNoCheck();   break;
        case ON_GRAPH|DEBUG:            proc = new OnGraphNoConvertCheck();     break;
        case ON_GRAPH|CONVERT_VALUES:   proc = new OnGraphConvert();            break;

        default:
            assert(false);
            return nullptr;
    }

    proc->set_flags(proc_type);
    return proc;
}



