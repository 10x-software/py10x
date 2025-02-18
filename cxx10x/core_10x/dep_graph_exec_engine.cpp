//
// Created by AMD on 5/21/2024.
//

#include "dep_graph_exec_engine.h"
#include "process_context.h"

ExecStack* DepGraphExecEngine::exec_stack() {
    auto tid = std::this_thread::get_id();
    auto i = m_xstacks.find(tid);
    if (i == m_xstacks.end()) {
        auto xstack = new ExecStack();
        m_xstacks.insert({tid, xstack});
        return xstack;
    }

    return i->second;
}

py::object DepGraphExecEngine::eval_graph_node(BasicNode *node) {
    auto xstack = exec_stack();
    auto parent = xstack->parent();
    py::object value;

    if (!node->is_valid()) {
        // TODO: PLACEBO_MAKER!
        ExecStack::NodeGuard node_guard(xstack, node);      // push node to the stack

        auto old_children = node->children();
        node->clear_children();
        auto trait = node->trait();

        value = trait->f_get(*node->eid());       // calling a python getter (no args)
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

ExecStack::Placebo DepGraphExecEngine::withUpwardDependenciesOff() {
    auto xstack = ProcessContext::PC.on(ProcessContext::ON_GRAPH)? exec_stack() : nullptr;
    return ExecStack::Placebo(xstack);
}
