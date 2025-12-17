//
// Created by AMD on 11/1/2024.
//

#pragma once

#include <thread>
#include <unordered_map>

#include "py_linkage.h"
#include "stackable_context.h"
#include "btraitable_processor.h"
#include "xcache.h"

class ThreadContext;

using TraitableProcessorStack  = StackableContext<BTraitableProcessor>;
using CacheStack               = StackableContext<XCache>;
using ContextByThread = std::unordered_map<std::thread::id, ThreadContext*>;

class ThreadContext {
    std::thread::id             m_tid;
    TraitableProcessorStack     m_traitable_proc_stack;
    CacheStack                  m_cache_stack;
    unsigned                    m_flags = 0;
    std::unordered_set<TID>    m_serialization_memo;

public:
    static constexpr unsigned  SAVE_REFERENCES    = 0x1;
    static void set_flags(const unsigned flags) {current_context().m_flags = flags; }
    [[nodiscard]] static unsigned flags() {return current_context().m_flags;}


    ThreadContext() : m_tid(std::this_thread::get_id()) {}

    static ThreadContext &current_context() {
        thread_local ThreadContext ctx;
        return ctx;
    }

    static XCache* current_cache() {
        auto &context = current_context();
        auto cache = context.m_cache_stack.top();
        if(!cache) {
            cache = XCache::default_cache();
            context.m_cache_stack.push(cache);
        }

        return cache;
    }

    static std::unordered_set<TID> &serialization_memo() {
        auto &context = current_context();
        return context.m_serialization_memo;
    }

    static void cache_push(XCache* cache) {
        auto &context = current_context();
        context.m_cache_stack.push(cache);
    }

    static XCache* cache_pop() {
        auto &context = current_context();
        return context.m_cache_stack.pop();
    }

    static void traitable_proc_push(BTraitableProcessor* proc) {
        auto &context = current_context();
        context.m_traitable_proc_stack.push(proc);
    }

    static BTraitableProcessor* traitable_proc_pop() {
        auto &context = current_context();
        return context.m_traitable_proc_stack.pop();
    }

    static BTraitableProcessor* current_traitable_proc(bool create = true) {
        auto &context = current_context();
        auto proc = context.m_traitable_proc_stack.top();
        if(!proc) {
            proc = BTraitableProcessor::create_default();
            context.m_traitable_proc_stack.push(proc);
        }

        return proc;
    }

};

