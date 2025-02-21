//
// Created by AMD on 3/19/2024.
//

#include "py_linkage.h"

#include "btrait.h"
#include "btraitable.h"
#include "btraitable_processor.h"
#include "bcache.h"
#include "brc.h"

BTrait::BTrait() {
    m_datatype = PyLinkage::XNone();
    m_default = PyLinkage::XNone();

    f_get        = py::none();
    f_set        = py::none();
    f_verify        = py::none();
    f_from_str      = py::none();
    f_from_any_xstr = py::none();
    f_to_str        = py::none();
    f_serialize     = py::none();
    f_deserialize   = py::none();
    f_to_id         = py::none();
}

void BTrait::raise(py::error_already_set &exc, BTraitable *obj, const py::object& method, const py::object* value, const py::args* args) {
    auto py_exc = PyLinkage::create_trait_method_error(obj, this, method.attr("__name__"), value, args, &exc);
    PyErr_SetObject(py_exc.get_type().ptr(), py_exc.ptr());
    throw py::error_already_set();
}

py::object BTrait::wrapper_f_get(BTraitable* obj) {
    try {
        return f_get(obj);
    } catch (py::error_already_set& exc) {
        raise(exc, obj, f_get, nullptr, nullptr);
    }
}

py::object BTrait::wrapper_f_get(BTraitable* obj, const py::args& args) {
    try {
        return f_get(obj, *args);
    } catch (py::error_already_set& exc) {
        raise(exc, obj, f_get, nullptr, &args);
    }
}

py::object BTrait::wrapper_f_set(BTraitable* obj, const py::object& value) {
    try {
        return f_set(obj, this, value);
    } catch (py::error_already_set& exc) {
        raise(exc, obj, f_get, &value, nullptr);
    }
}

py::object BTrait::wrapper_f_set(BTraitable* obj, const py::object& value, const py::args& args) {
    try {
        return f_set(obj, this, value, *args);
    } catch (py::error_already_set& exc) {
        raise(exc, obj, f_get, &value, &args);
    }
}

py::object BTrait::wrapper_f_verify(BTraitable* obj, const py::object& value) {
    try {
        return f_verify(obj, value);
    } catch (py::error_already_set& exc) {
        raise(exc, obj, f_get, &value, nullptr);
    }
}

py::object BTrait::wrapper_f_from_str(BTraitable* obj, const py::object& value) {
    try {
        return f_from_str(obj, this, value);
    } catch (py::error_already_set& exc) {
        raise(exc, obj, f_get, &value, nullptr);
    }
}

py::object BTrait::wrapper_f_from_any_xstr(BTraitable* obj, const py::object& value) {
    try {
        return f_from_any_xstr(obj, this, value);
    } catch (py::error_already_set& exc) {
        raise(exc, obj, f_get, &value, nullptr);
    }
}

py::object BTrait::wrapper_f_to_str(BTraitable* obj, const py::object& value) {
    try {
        return f_to_str(obj, this, value);
    } catch (py::error_already_set& exc) {
        raise(exc, obj, f_get, &value, nullptr);
    }
}

py::object BTrait::wrapper_f_serialize(BTraitable* obj, const py::object& value) {
    try {
        return f_serialize(obj, this, value);
    } catch (py::error_already_set& exc) {
        raise(exc, obj, f_get, &value, nullptr);
    }
}

py::object BTrait::wrapper_f_deserialize(BTraitable* obj, const py::object& value) {
    try {
        return f_deserialize(obj, this, value);
    } catch (py::error_already_set& exc) {
        raise(exc, obj, f_get, &value, nullptr);
    }
}

py::object BTrait::wrapper_f_to_id(BTraitable* obj, const py::object& value) {
    try {
        return f_to_id(obj, this, value);
    } catch (py::error_already_set& exc) {
        raise(exc, obj, f_get, &value, nullptr);
    }
}

//======================================================================================================================
//  Regular Trait
//======================================================================================================================

BasicNode* BTrait::find_node(BTraitableProcessor* proc, BTraitable* obj) {
    return proc->cache()->find_node(obj->tid(), this);
}

BasicNode* BTrait::find_node(BTraitableProcessor* proc, BTraitable* obj, const py::args& args) {
    return proc->cache()->find_node(obj->tid(), this, args);
}

BasicNode* BTrait::find_or_create_node(BTraitableProcessor* proc, BTraitable* obj, int node_type) {
    return proc->cache()->find_or_create_node(obj->tid(), this, node_type);
}

BasicNode* BTrait::find_or_create_node(BTraitableProcessor* proc, BTraitable* obj, int node_type, const py::args& args) {
    return proc->cache()->find_or_create_node(obj->tid(), this, args, node_type);
}

py::object BTrait::get_value_off_graph(BTraitableProcessor* proc, BTraitable* obj) {
    auto node = find_node(proc, obj);
    if (node)    // No need to check if the node is set, as only set nodes could be in the cache in OFF_GRAPH mode
        return node->value();

    return wrapper_f_get(obj);
}

py::object BTrait::get_value_off_graph(BTraitableProcessor* proc, BTraitable* obj, const py::args& args) {
    auto node = find_node(proc, obj, args);
    if (node)    // No need to check if the node is set, as only set nodes could be in the cache in OFF_GRAPH mode
        return node->value();

    return wrapper_f_get(obj, args);
}

py::object BTrait::get_value_on_graph(BTraitableProcessor* proc, BTraitable* obj) {
    auto node = find_or_create_node(proc, obj, NODE_TYPE::GRAPH);

    auto xstack = proc->exec_stack();
    auto parent = xstack->parent();
    py::object value;

    if (!node->is_valid()) {
        // TODO: PLACEBO_MAKER!
        NodeGuard node_guard(xstack, node);      // push node to the stack

        auto old_children = node->children();
        node->clear_children();

        value = wrapper_f_get(obj);       // calling python getter
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

py::object BTrait::get_value_on_graph(BTraitableProcessor* proc, BTraitable* obj, const py::args& args) {
    auto node = find_or_create_node(proc, obj, NODE_TYPE::GRAPH, args);

    auto xstack = proc->exec_stack();
    auto parent = xstack->parent();
    py::object value;

    if (!node->is_valid()) {
        // TODO: PLACEBO_MAKER!
        NodeGuard node_guard(xstack, node);      // push node to the stack

        auto old_children = node->children();
        node->clear_children();

        value = wrapper_f_get(obj, args);       // calling python getter
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

void BTrait::invalidate_value_off_graph(BTraitableProcessor* proc, BTraitable* obj) {
    proc->cache()->remove_node(obj->tid(), this);
}

void BTrait::invalidate_value_off_graph(BTraitableProcessor* proc, BTraitable* obj, const py::args& args) {
    proc->cache()->remove_node(obj->tid(), this, args);
}

void BTrait::invalidate_value_on_graph(BTraitableProcessor* proc, BTraitable* obj) {
    auto cache = proc->cache();
    auto node = cache->find_node(obj->tid(), this);
    if (node)
        cache->invalidate_node(node);
}

void BTrait::invalidate_value_on_graph(BTraitableProcessor* proc, BTraitable* obj, const py::args& args) {
    auto cache = proc->cache();
    auto node = cache->find_node(obj->tid(), this, args);
    if (node)
        cache->invalidate_node(node);
}

py::object BTrait::raw_set_value_off_graph_noconvert_nocheck(BTraitableProcessor* proc, BTraitable* obj, const py::object& value) {
    auto cache = proc->cache();
    // TODO: if the node below is an existing Graph Node, setting its value will continue to work ON Graph despite the OFF Graph mode
    auto node = find_or_create_node(proc, obj, NODE_TYPE::BASIC);
    cache->set_node(node, value);
    return PyLinkage::RC_TRUE();
}

py::object BTrait::raw_set_value_off_graph_noconvert_nocheck(BTraitableProcessor* proc, BTraitable* obj, const py::object& value, const py::args& args) {
    auto cache = proc->cache();
    // TODO: if the node below is an existing Graph Node, setting its value will continue to work ON Graph despite the OFF Graph mode
    auto node = find_or_create_node(proc, obj, NODE_TYPE::BASIC, args);
    cache->set_node(node, value);
    return PyLinkage::RC_TRUE();
}

py::object BTrait::raw_set_value_off_graph_noconvert_check(BTraitableProcessor* proc, BTraitable* obj, const py::object& value) {
    if(!value.get_type().is(m_datatype))    // TODO: we may want to use is_acceptable_type() method  of the trait
        throw py::type_error(py::str("Trying to set trait {} ({}) to {}").format(m_name, m_datatype, value));

    return raw_set_value_off_graph_noconvert_nocheck(proc, obj, value);
}

py::object BTrait::raw_set_value_off_graph_noconvert_check(BTraitableProcessor* proc, BTraitable* obj, const py::object& value, const py::args& args) {
    if(!value.get_type().is(m_datatype))    // TODO: we may want to use is_acceptable_type() method  of the trait
        throw py::type_error(py::str("Trying to set trait {} ({}) to {}").format(m_name, m_datatype, value));

    return raw_set_value_off_graph_noconvert_nocheck(proc, obj, value, args);
}

py::object BTrait::raw_set_value_off_graph_convert(BTraitableProcessor* proc, BTraitable* obj, const py::object& value) {
    if(!value.get_type().is(m_datatype)) {
        py::object converted_value = obj->from_any(this, value);
        return raw_set_value_off_graph_noconvert_nocheck(proc, obj, converted_value);
    }

    return raw_set_value_off_graph_noconvert_nocheck(proc, obj, value);
}

py::object BTrait::raw_set_value_off_graph_convert(BTraitableProcessor* proc, BTraitable* obj, const py::object& value, const py::args& args) {
    if(!value.get_type().is(m_datatype)) {
        py::object converted_value = obj->from_any(this, value);
        return raw_set_value_off_graph_noconvert_nocheck(proc, obj, converted_value, args);
    }

    return raw_set_value_off_graph_noconvert_nocheck(proc, obj, value, args);
}

py::object BTrait::raw_set_value_on_graph_noconvert_nocheck(BTraitableProcessor* proc, BTraitable* obj, const py::object& value) {
    auto cache = proc->cache();
    auto node = cache->find_or_create_node(obj->tid(), this, NODE_TYPE::GRAPH);   // TODO: make sure an existing BASIC node, if any, is converted to GRAPH
    cache->set_node(node, value);
    return PyLinkage::RC_TRUE();
}

py::object BTrait::raw_set_value_on_graph_noconvert_nocheck(BTraitableProcessor* proc, BTraitable* obj, const py::object& value, const py::args& args) {
    auto cache = proc->cache();
    auto node = cache->find_or_create_node(obj->tid(), this, args, NODE_TYPE::GRAPH);   // TODO: make sure an existing BASIC node, if any, is converted to GRAPH
    cache->set_node(node, value);
    return PyLinkage::RC_TRUE();
}

py::object BTrait::raw_set_value_on_graph_noconvert_check(BTraitableProcessor* proc, BTraitable* obj, const py::object& value) {
    if(!value.get_type().is(m_datatype))    // TODO: we may want to use is_acceptable_type() method  of the trait
        throw py::type_error(py::str("Trying to set trait {} ({}) to {}").format(m_name, m_datatype, value));

    return raw_set_value_on_graph_noconvert_nocheck(proc, obj, value);
}

py::object BTrait::raw_set_value_on_graph_noconvert_check(BTraitableProcessor* proc, BTraitable* obj, const py::object& value, const py::args& args) {
    if(!value.get_type().is(m_datatype))    // TODO: we may want to use is_acceptable_type() method  of the trait
        throw py::type_error(py::str("Trying to set trait {} ({}) to {}").format(m_name, m_datatype, value));

    return raw_set_value_on_graph_noconvert_nocheck(proc, obj, value, args);
}

py::object BTrait::raw_set_value_on_graph_convert(BTraitableProcessor* proc, BTraitable* obj, const py::object& value) {
    if(!value.get_type().is(m_datatype)) {
        auto converted_value = obj->from_any(this, value);
        return raw_set_value_on_graph_noconvert_nocheck(proc, obj, converted_value);
    }

    return raw_set_value_on_graph_noconvert_nocheck(proc, obj, value);
}

py::object BTrait::raw_set_value_on_graph_convert(BTraitableProcessor* proc, BTraitable* obj, const py::object& value, const py::args& args) {
    if(!value.get_type().is(m_datatype)) {
        auto converted_value = obj->from_any(this, value);
        return raw_set_value_on_graph_noconvert_nocheck(proc, obj, converted_value, args);
    }

    return raw_set_value_on_graph_noconvert_nocheck(proc, obj, value, args);
}

//======================================================================================================================
//  Eval Once Trait
//  - always evaluates in the Default BCache
//  - may not be set or invalidated
//======================================================================================================================

py::object EvalOnceTrait::get_value_off_graph(BTraitableProcessor* proc, BTraitable* obj, const py::args& args) {
    auto def_cache = BCache::default_cache();    // Eval Once trait must be evaluated in Default Cache
    auto node = def_cache->find_or_create_node(obj->tid(), this, args, NODE_TYPE::BASIC);
    if(node->is_valid())
        return node->value();

    return wrapper_f_get(obj, args);
}

void EvalOnceTrait::dont_touch_me(BTraitable *obj) {
    throw py::type_error(py::str("Trying to modify EVAL_ONCE trait {}.{}").format(obj->class_name(), m_name));
}

