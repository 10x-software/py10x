//
// Created by AMD on 2/22/2025.
//

#include "btrait_processor.h"
#include "btrait.h"
#include "btraitable.h"
#include "btraitable_processor.h"


py::object BTraitProcessor::get_value_off_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait) {
    auto node = proc->cache()->find_node(obj->tid(), trait);
    if (node)    // No need to check if the node is set, as only set nodes could be in the cache in OFF_GRAPH mode
        return node->value();

    return trait->wrapper_f_get(obj);
}

py::object BTraitProcessor::get_value_off_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait, const py::args& args) {
    auto node = proc->cache()->find_node(obj->tid(), trait, args);
    if (node)    // No need to check if the node is set, as only set nodes could be in the cache in OFF_GRAPH mode
        return node->value();

    return trait->wrapper_f_get(obj, args);
}

py::object BTraitProcessor::get_value_on_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait) {
    //-- TODO: need a better solution to choosing the node type!
    auto node = proc->cache()->find_or_create_node(obj->tid(), trait, NODE_TYPE::BASIC_GRAPH);

    auto xstack = proc->exec_stack();
    auto parent = xstack->parent();
    py::object value;

    if (!node->is_valid()) {
        // TODO: PLACEBO_MAKER!
        NodeGuard node_guard(xstack, node);      // push node to the stack

        auto old_children = node->children();
        node->clear_children();

        value = trait->wrapper_f_get(obj);       // calling python getter
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

py::object BTraitProcessor::get_value_on_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait, const py::args& args) {
    auto node = proc->cache()->find_or_create_node(obj->tid(), trait, args, NODE_TYPE::BASIC_GRAPH);

    auto xstack = proc->exec_stack();
    auto parent = xstack->parent();
    py::object value;

    if (!node->is_valid()) {
        // TODO: PLACEBO_MAKER!
        NodeGuard node_guard(xstack, node);      // push node to the stack

        auto old_children = node->children();
        node->clear_children();

        value = trait->wrapper_f_get(obj, args);       // calling python getter with args
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

//---- Invalidating trait value

void BTraitProcessor::invalidate_value_off_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait) {
    proc->cache()->remove_node(obj->tid(), trait);
}

void BTraitProcessor::invalidate_value_off_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait, const py::args& args) {
    proc->cache()->remove_node(obj->tid(), trait, args);
}

void BTraitProcessor::invalidate_value_on_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait) {
    auto cache = proc->cache();
    auto node = cache->find_node(obj->tid(), trait);
    if (node)
        cache->invalidate_node(node);
}

void BTraitProcessor::invalidate_value_on_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait, const py::args& args) {
    auto cache = proc->cache();
    auto node = cache->find_node(obj->tid(), trait, args);
    if (node)
        cache->invalidate_node(node);
}

//---- Setting (raw) trait value

py::object BTraitProcessor::raw_set_value_off_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait, const py::object& value) {
    auto cache = proc->cache();
    // TODO: if the node below is an existing Graph Node, setting its value will continue to work ON Graph despite the OFF Graph mode
    auto node = cache->find_or_create_node(obj->tid(), trait, NODE_TYPE::BASIC);
    cache->set_node(node, value);
    return PyLinkage::RC_TRUE();
}

py::object BTraitProcessor::raw_set_value_off_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait, const py::object& value, const py::args& args ) {
    auto cache = proc->cache();
    auto node = cache->find_or_create_node(obj->tid(), trait, args, NODE_TYPE::BASIC);
    cache->set_node(node, value);
    return PyLinkage::RC_TRUE();
}

py::object BTraitProcessor::raw_set_value_on_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait, const py::object& value) {
    auto cache = proc->cache();
    auto node = cache->find_or_create_node(obj->tid(), trait, NODE_TYPE::BASIC_GRAPH);   // TODO: make sure an existing BASIC node, if any, is converted to GRAPH
    cache->set_node(node, value);
    return PyLinkage::RC_TRUE();
}

py::object BTraitProcessor::raw_set_value_on_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait, const py::object& value, const py::args& args) {
    auto cache = proc->cache();
    auto node = cache->find_or_create_node(obj->tid(), trait, args, NODE_TYPE::BASIC_GRAPH);   // TODO: make sure an existing BASIC node, if any, is converted to GRAPH
    cache->set_node(node, value);
    return PyLinkage::RC_TRUE();
}

//======================================================================================================================
//  Eval Once Trait
//  - always evaluates in the Default BCache
//  - may not be set or invalidated
//======================================================================================================================

py::object EvalOnceProc::get_value_off_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait) {
    auto def_cache = BCache::default_cache();    // Eval Once trait must be evaluated in Default Cache
    auto node = def_cache->find_or_create_node(obj->tid(), trait, NODE_TYPE::BASIC);
    if(node->is_valid())
        return node->value();

    auto value = trait->wrapper_f_get(obj);
    node->assign(value);
    return value;
}

py::object EvalOnceProc::get_value_off_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait, const py::args& args) {
    auto def_cache = BCache::default_cache();    // Eval Once trait must be evaluated in Default Cache
    auto node = def_cache->find_or_create_node(obj->tid(), trait, args, NODE_TYPE::BASIC);
    if(node->is_valid())
        return node->value();

    auto value = trait->wrapper_f_get(obj, args);
    node->assign(value);
    return value;
}

py::object EvalOnceProc::dont_touch_me(BTraitable *obj, BTrait* trait) {
    throw py::type_error(py::str("Trying to modify EVAL_ONCE trait {}.{}").format(obj->class_name(), trait->name()));
}
