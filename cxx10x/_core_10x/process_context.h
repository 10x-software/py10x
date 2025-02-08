//
// Created by AMD on 5/20/2024.
//
#pragma once

#include <unordered_map>
#include <thread>

class BTraitableProcessor;

using BTraitableProcessorStack = std::unordered_map<std::thread::id, BTraitableProcessor*>;

class BProcessContext {
    BTraitableProcessorStack    m_traitable_proc_stack;

public:

    static BProcessContext  s_PC;

    BProcessContext();

    BTraitableProcessor*    traitable_processor();

};

//class ProcessContext {
//    unsigned            m_state;
//    Cache               m_cache;
//    XStackByThread      m_xstacks;
//
//public:
//    static const unsigned  DEBUG            = 0x1;
//    static const unsigned  CONVERT_VALUES   = 0x2;
//    static const unsigned  ON_GRAPH         = 0x4;
//
//    static ProcessContext PC;
//
//    ProcessContext() : m_state(DEBUG) {}
//
//    [[nodiscard]] Cache& cache() {
//        return m_cache;     // TODO: handle cache layers
//    }
//
//    ExecStack* exec_stack();
//
//    void change_mode(unsigned to_set, unsigned to_reset)    { m_state = (m_state | to_set) & ~to_reset; }
//    void set_mode(unsigned flags)                           { m_state = flags; }
//    [[nodiscard]] bool on(unsigned flags) const             { return m_state & flags; }
//    [[nodiscard]] bool off(unsigned flags) const            { return (m_state & flags) == 0; }
//
//};

