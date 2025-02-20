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

unsigned BTraitableProcessor::s_default_type = 0x0;   // = BTraitableProcessor::CONVERT_VALUES;

BTraitableProcessor* BTraitableProcessor::create_default() {
    auto proc = create(s_default_type);
    assert(proc);
    proc->use_cache(BCache::default_cache());
    return proc;
}

//---- Setting a value

py::object BTraitableProcessor::set_trait_value(BTraitable *obj, BTrait *trait, const py::object& value) {
    if (!trait->f_set.is_none())     // custom setter is defined
        return trait->wrapper_f_set(obj, value);

    return raw_set_trait_value(obj, trait, value);
}

py::object BTraitableProcessor::set_trait_value(BTraitable *obj, BTrait *trait, const py::object& value, const py::args& args) {
    if (!trait->f_set.is_none())     // custom setter is defined
        return trait->wrapper_f_set(obj, value, args);

    return raw_set_trait_value(obj, trait, value, args);
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

    py::object raw_set_trait_value(BTraitable* obj, BTrait* trait, const py::object& value) override {
        return trait->raw_set_value_off_graph_noconvert_nocheck(this, obj, value);
    }

    py::object raw_set_trait_value(BTraitable* obj, BTrait* trait, const py::object& value, const py::args& args) override {
        return trait->raw_set_value_off_graph_noconvert_nocheck(this, obj, value, args);
    }
};

class OffGraphNoConvertCheck : public OffGraphNoConvertNoCheck {
public:
    py::object raw_set_trait_value(BTraitable* obj, BTrait* trait, const py::object& value) final {
        return trait->raw_set_value_off_graph_noconvert_check(this, obj, value);
    }

    py::object raw_set_trait_value(BTraitable* obj, BTrait* trait, const py::object& value, const py::args& args) final {
        return trait->raw_set_value_off_graph_noconvert_check(this, obj, value, args);
    }
};

class OffGraphConvert : public OffGraphNoConvertNoCheck {
public:
    py::object raw_set_trait_value(BTraitable* obj, BTrait* trait, const py::object& value) final {
        return trait->raw_set_value_off_graph_convert(this, obj, value);
    }

    py::object raw_set_trait_value(BTraitable* obj, BTrait* trait, const py::object& value, const py::args& args) final {
        return trait->raw_set_value_off_graph_convert(this, obj, value, args);
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

    py::object raw_set_trait_value(BTraitable* obj, BTrait* trait, const py::object& value) override {
        return trait->raw_set_value_on_graph_noconvert_nocheck(this, obj, value);
    }

    py::object raw_set_trait_value(BTraitable* obj, BTrait* trait, const py::object& value, const py::args& args) override {
        return trait->raw_set_value_on_graph_noconvert_nocheck(this, obj, value, args);
    }
};

class OnGraphNoConvertCheck : public OnGraphNoConvertNoCheck {
public:
    py::object raw_set_trait_value(BTraitable* obj, BTrait* trait, const py::object& value) final {
        return trait->raw_set_value_on_graph_noconvert_check(this, obj, value);
    }

    py::object raw_set_trait_value(BTraitable* obj, BTrait* trait, const py::object& value, const py::args& args) final {
        return trait->raw_set_value_on_graph_noconvert_check(this, obj, value, args);
    }
};

class OnGraphConvert : public OnGraphNoConvertNoCheck {
public:
    py::object raw_set_trait_value(BTraitable* obj, BTrait* trait, const py::object& value) final {
        return trait->raw_set_value_on_graph_convert(this, obj, value);
    }

    py::object raw_set_trait_value(BTraitable* obj, BTrait* trait, const py::object& value, const py::args& args) final {
        return trait->raw_set_value_on_graph_convert(this, obj, value, args);
    }
};

BTraitableProcessor* BTraitableProcessor::create(unsigned int flags) {
//    static const unsigned  DEBUG            = 0x1;
//    static const unsigned  CONVERT_VALUES   = 0x2;
//    static const unsigned  ON_GRAPH         = 0x4;
    BTraitableProcessor *proc;
    switch(flags) {
        case 0x0:       proc = new OffGraphNoConvertNoCheck();  break;
        case 0x1:       proc = new OffGraphNoConvertCheck();    break;
        case 0x2:       proc = new OffGraphConvert();           break;

        case 0x4:       proc = new OnGraphNoConvertNoCheck();   break;
        case 0x5:       proc = new OnGraphNoConvertCheck();     break;
        case 0x6:       proc = new OnGraphConvert();            break;

        //case 0x10:      return new IdCalc();

        default:
            assert(false);
            return nullptr;
    }

    proc->set_flags(flags);
    return proc;
}


