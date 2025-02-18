//
// Created by AMD on 5/22/2024.
//
#include "process_context.h"

ProcessContext ProcessContext::PC;

ExecStack* ProcessContext::exec_stack() {
    auto tid = std::this_thread::get_id();
    auto i = m_xstacks.find(tid);
    if (i == m_xstacks.end()) {
        auto xstack = new ExecStack();
        m_xstacks.insert({tid, xstack});
        return xstack;
    }

    return i->second;
}
