//
// Created by AMD on 3/3/2025.
//
#include "btraitable_ui_extension.h"
#include "btrait.h"
#include "btrait_processor.h"
#include "btraitable_class.h"
#include "btraitable.h"
#include "bnode.h"

class UiTraitProcessor : public BTraitProcessor {
public:
    //---- Getting trait value

    py::object get_value_off_graph(BTraitableProcessor* proc, BTraitable* obj, const BTrait* trait) final {
        assert(false);  return py::none();
    }

    py::object get_value_off_graph(BTraitableProcessor* proc, BTraitable* obj, const BTrait* trait, const py::args& args) final {
        assert(false);   return py::none();
    }

    static py::object ui_getter(BTraitable* obj, const BTrait* trait) {
        obj->get_value(trait);          //-- dep on the value node
        obj->get_style_sheet(trait);    //-- dep on the style_sheet node
        return PyLinkage::XNone();
    }

    py::object get_value_on_graph(BTraitableProcessor* proc, BTraitable* obj, const BTrait* trait) final {
        auto ui_class = obj->bui_class();
        auto ui_trait = ui_class->bui_trait(trait);
        auto ui_node = proc->cache()->find_node(obj->tid(), ui_trait);
        if (!ui_node)
            throw py::value_error(py::str("get_value_on_graph: {}.{} - ui node must've been already created").format(obj->class_name(), trait->name()));

        auto bound_getter = [obj, trait]() { return ui_getter(obj, trait); };
        return BTraitProcessor::get_node_value_on_graph(proc, ui_node, bound_getter);
    }

    py::object get_value_on_graph(BTraitableProcessor* proc, BTraitable* obj, const BTrait* trait, const py::args& args) final {
        assert(false);   return py::none();
    }

    //---- Invalidating trait value

    void invalidate_value_off_graph(const BTraitableProcessor *proc, BTraitable *obj, const BTrait *trait) const final {
        assert(false);
    }

    void invalidate_value_off_graph(const BTraitableProcessor *proc, BTraitable *obj, const BTrait *trait, const py::args &args) const final {
        assert(false);
    }

    void invalidate_value_on_graph(const BTraitableProcessor *proc, BTraitable *obj, const BTrait *trait) const final {
        assert(false);
    }

    void invalidate_value_on_graph(const BTraitableProcessor *proc, BTraitable *obj, const BTrait *trait, const py::args &args) final {
        assert(false);
    }

    //---- Setting (raw) trait value

    py::object raw_set_value_off_graph(const BTraitableProcessor* proc, BTraitable* obj, const BTrait* trait, const py::object& value) const final {
        assert(false);   return py::none();
    }

    py::object raw_set_value_off_graph(const BTraitableProcessor* proc, BTraitable* obj, const BTrait* trait, const py::object& value, const py::args& args) const final {
        assert(false);  return py::none();
    }

    py::object raw_set_value_on_graph(const BTraitableProcessor* proc, BTraitable* obj, const BTrait* trait, const py::object& value) const final {
        assert(false);  return py::none();
    }

    py::object raw_set_value_on_graph(const BTraitableProcessor* proc, BTraitable* obj, const BTrait* trait, const py::object& value, const py::args& args) const final {
        assert(false);  return py::none();
    }

};

BUiClass::BUiClass(BTraitableClass* cls) : m_class(cls) {
    //-- skipping HIDDEN traits and traits with custom getters/setters with params
    for (auto item : cls->trait_dir()) {
        auto py_trait = item.second.cast<py::object>();
        auto gp = py_trait.attr("getter_params").cast<py::tuple>();
        if (!gp.empty())
            continue;

        auto trait = item.second.cast<BTrait*>();
        if (trait->flags_on(BTraitFlags::HIDDEN))
            continue;

        auto my_trait = new BTrait();
        my_trait->set_name(trait->m_name);
        my_trait->m_flags = trait->m_flags;
        my_trait->set_flags(BTraitFlags::RUNTIME);
        my_trait->m_proc = new UiTraitProcessor();
        m_own_dir[trait] = my_trait;
    }
}

BTrait* BUiClass::bui_trait(const BTrait *trait) const {
    auto i = m_own_dir.find(trait);
    if (i == m_own_dir.end())
        throw py::type_error(py::str("{}.{} - missing ui trait").format(m_class->name(), trait->name()));

    return i->second;
}

void BUiClass::create_ui_node(BTraitable *obj, BTrait *trait, py::object f_refresh) {
    auto ui_trait = bui_trait(trait);
    auto proc = ThreadContext::current_traitable_proc();
    const auto ui_node = static_cast<BUiNode *>(proc->cache()->find_or_create_node(obj, ui_trait, NODE_TYPE::UI, false));
    ui_node->set_refresh_emit(f_refresh);

    ui_trait->proc()->get_value_on_graph(proc, obj, trait);  //-- to create necessary deps for ui_node!
}

void BUiClass::update_ui_node(BTraitable *obj, BTrait *trait) {
    auto ui_trait = bui_trait(trait);
    auto proc = ThreadContext::current_traitable_proc();
    auto node = proc->cache()->find_node(obj->tid(), ui_trait);
    if (!node)
        throw py::value_error(py::str("update_ui_node: {}.{} - ui node must've been already created").format(obj->class_name(), trait->name()));
    node->set_state(STATE_VALID);
}
