//
// Created by AMD on 2/22/2025.
//

#include "btrait_processor.h"
#include "btrait.h"
#include "btraitable.h"
#include "btraitable_processor.h"
#include "thread_context.h"


py::object BTraitProcessor::get_value_off_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait) {
    const auto & tid = obj->tid();
    const auto cache = proc->cache();
    cache->find_object_cache_and_load(obj); // handle lazy load
    if (const auto node = cache->find_set_or_invalid_node_in_parents(obj->tid(), trait, false))
        if (node->is_valid())
            return node->value();

    return trait->wrapper_f_get(obj);
}

py::object BTraitProcessor::get_value_off_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait, const py::args& args) {
    const auto & tid = obj->tid();
    const auto cache = proc->cache();
    cache->find_object_cache_and_load(obj); // handle lazy load
    if (const auto node = cache->find_set_or_invalid_node_in_parents(tid, trait, args, false))
        if (node->is_valid())
            return node->value();

    return trait->wrapper_f_get(obj, args);
}

py::object BTraitProcessor::get_node_value_on_graph(BTraitableProcessor* proc, BasicNode *node, const PyBoundMethod& f) {
    auto xstack = proc->exec_stack();
    auto parent = xstack->parent();
    py::object value;

    if (!node->is_valid()) {
        // TODO: PLACEBO_MAKER!
        NodeGuard node_guard(xstack, node);      // push node to the stack

        auto old_children = node->children();
        node->clear_children();

        value = f();       // calling a fully bound python method
        node->assign(value);
        auto new_children = node->children();
        for (auto c: *old_children)
            if (new_children->find(c) == new_children->end())
                c->remove_parent(node);
    } else
        value = node->value();

    if (parent) {
        node->add_parent(parent);
        // TODO: layer -> notify_node_parent_addition(node, parent);
    }

    return value;
}

py::object BTraitProcessor::get_value_on_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait) {
    const auto node = proc->cache()->find_or_create_node(obj, trait, true);
    auto bound_getter = [trait, obj]() { return trait->wrapper_f_get(obj); };
    return BTraitProcessor::get_node_value_on_graph(proc, node, bound_getter);
}

py::object BTraitProcessor::get_value_on_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait, const py::args& args) {
    const auto node = proc->cache()->find_or_create_node(obj, trait, args, true);
    auto bound_getter = [trait, obj, args]() { return trait->wrapper_f_get(obj, args); };
    return BTraitProcessor::get_node_value_on_graph(proc, node, bound_getter);
}

py::object BTraitProcessor::get_choices_off_graph(BTraitableProcessor *proc, BTraitable *obj, BTrait *trait) {
    return trait->wrapper_f_choices(obj);
}

py::object BTraitProcessor::get_choices_on_graph(BTraitableProcessor *proc, BTraitable *obj, BTrait *trait) {
    const auto node = proc->cache()->find_or_create_node(obj, trait, PyLinkage::choices_args(), true);
    auto bound_getter = [trait, obj]() { return trait->wrapper_f_choices(obj); };
    return BTraitProcessor::get_node_value_on_graph(proc, node, bound_getter);
}

py::object BTraitProcessor::get_style_sheet_off_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait) {
    return trait->wrapper_f_style_sheet(obj);
}

py::object BTraitProcessor::get_style_sheet_on_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait) {
    const auto node = proc->cache()->find_or_create_node(obj, trait, PyLinkage::style_sheet_args(), true);
    auto bound_getter = [trait, obj]() { return trait->wrapper_f_style_sheet(obj); };
    return BTraitProcessor::get_node_value_on_graph(proc, node, bound_getter);
}

//---- Invalidating trait value

void BTraitProcessor::invalidate_value_off_graph(const BTraitableProcessor* proc, BTraitable* obj, BTrait* trait) {
    const auto cache = proc->cache();
    cache->remove_node(obj->tid(), trait);
    if (auto node = cache->find_set_or_invalid_node_in_parents(obj->tid(), trait))
        if (node->is_valid())
            cache->find_or_create_node(obj, trait, false); // create invalid node
}

void BTraitProcessor::invalidate_value_off_graph(const BTraitableProcessor* proc, BTraitable* obj, BTrait* trait, const py::args& args) {
    const auto cache = proc->cache();
    cache->remove_node(obj->tid(), trait, args);
    if (const auto node = cache->find_set_or_invalid_node_in_parents(obj->tid(), trait, args))
        if (node->is_valid())
            cache->find_or_create_node(obj, trait, args, false); // create invalid node
}

void BTraitProcessor::invalidate_value_on_graph(const BTraitableProcessor* proc, BTraitable* obj, BTrait* trait) {
    const auto cache = proc->cache();
    const auto &tid = obj->tid();
    cache->find_object_cache_and_load(obj); // handle lazy load
    if (const auto node = cache->find_node(tid, trait))
        node->invalidate();
    else if (const auto parent_node = cache->find_set_or_invalid_node_in_parents(tid, trait))
        if (parent_node->is_valid())
            cache->find_or_create_node(obj, trait, false); // create invalid node
}

void BTraitProcessor::invalidate_value_on_graph(const BTraitableProcessor* proc, BTraitable* obj, const BTrait* trait, const py::args& args) {
    const auto cache = proc->cache();
    const auto &tid = obj->tid();
    cache->find_object_cache_and_load(obj); // handle lazy load
    if (const auto node = cache->find_node(tid, trait, args))
        node->invalidate();
    else if (const auto parent_node = cache->find_set_or_invalid_node_in_parents(tid, trait, args))
        if (parent_node->is_valid())
            cache->find_or_create_node(obj, trait, args, false); // create invalid node
}

//---- Setting (raw) trait value

py::object BTraitProcessor::raw_set_value_off_graph(const BTraitableProcessor* proc, BTraitable* obj, const BTrait* trait, const py::object& value) const {
    auto cache = proc->cache();
    auto node = cache->find_or_create_node(obj, trait, false);
    node->set(value);
    return PyLinkage::RC_TRUE();
}

py::object BTraitProcessor::raw_set_value_off_graph(const BTraitableProcessor* proc, BTraitable* obj, const BTrait* trait, const py::object& value, const py::args& args ) const {
    auto cache = proc->cache();
    auto node = cache->find_or_create_node(obj, trait, args, false);
    node->set(value);
    return PyLinkage::RC_TRUE();
}

py::object BTraitProcessor::raw_set_value_on_graph(const BTraitableProcessor* proc, BTraitable* obj, const BTrait* trait, const py::object& value) const {
    auto cache = proc->cache();
    auto node = cache->find_or_create_node(obj, trait, false);   // TODO: make sure an existing BASIC node, if any, is converted to GRAPH
    node->set(value);
    return PyLinkage::RC_TRUE();
}

py::object BTraitProcessor::raw_set_value_on_graph(const BTraitableProcessor* proc, BTraitable* obj, const BTrait* trait, const py::object& value, const py::args& args) const {
    auto cache = proc->cache();
    auto node = cache->find_or_create_node(obj, trait, args, false);   // TODO: make sure an existing BASIC node, if any, is converted to GRAPH
    node->set(value);
    return PyLinkage::RC_TRUE();
}

//======================================================================================================================
//  Eval Once Trait
//  - always evaluates in the Default BCache
//  - may not be set or invalidated
//======================================================================================================================

py::object EvalOnceProc::get_value_off_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait) {
    const auto def_cache = XCache::default_cache();    // Eval Once trait must be evaluated in Default Cache
    const auto node = def_cache->find_or_create_node(obj, trait, NODE_TYPE::BASIC, true);
    if(node->is_valid())
        return node->value();

    auto value = trait->wrapper_f_get(obj);
    node->assign(value);
    return value;
}

py::object EvalOnceProc::get_value_off_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait, const py::args& args) {
    const auto def_cache = XCache::default_cache();    // Eval Once trait must be evaluated in Default Cache
    const auto node = def_cache->find_or_create_node(obj, trait, NODE_TYPE::BASIC, args, true);
    if(node->is_valid())
        return node->value();

    auto value = trait->wrapper_f_get(obj, args);
    node->assign(value);
    return value;
}

py::object EvalOnceProc::dont_touch_me(const BTraitable *obj, const BTrait* trait) {
    throw py::type_error(py::str("Trying to modify EVAL_ONCE trait {}.{}").format(obj->class_name(), trait->name()));
}
