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

using TraitableProcessorStack   = StackableContext<BTraitableProcessor>;
using CacheStack                = StackableContext<XCache>;
using ContextByThread = std::unordered_map<std::thread::id, ThreadContext*>;

class ThreadContext {
    std::thread::id             m_tid;
    TraitableProcessorStack     m_traitable_proc_stack;
    CacheStack                  m_cache_stack;

    static ContextByThread      s_context_by_thread;

public:
    explicit ThreadContext(std::thread::id tid ) : m_tid(tid) {}

    static ThreadContext* current_context() {
        auto tid = std::this_thread::get_id();
        auto i = s_context_by_thread.find(tid);
        if(i == s_context_by_thread.end()) {
            auto context = new ThreadContext(tid);
            s_context_by_thread.insert({tid, context});
            return context;
        }

        return i->second;
    }

    static XCache* current_cache() {
        auto context = current_context();
        auto cache = context->m_cache_stack.top();
        if(!cache) {
            cache = XCache::default_cache();
            context->m_cache_stack.push(cache);
        }

        return cache;
    }

    static void cache_push(XCache* cache) {
        auto context = current_context();
        context->m_cache_stack.push(cache);
    }

    static XCache* cache_pop() {
        auto context = current_context();
        return context->m_cache_stack.pop();
    }

    static void traitable_proc_push(BTraitableProcessor* proc) {
        auto context = current_context();
        context->m_traitable_proc_stack.push(proc);
    }

    static BTraitableProcessor* traitable_proc_pop() {
        auto context = current_context();
        return context->m_traitable_proc_stack.pop();
    }

    static BTraitableProcessor* current_traitable_proc(bool create = true) {
        auto context = current_context();
        auto proc = context->m_traitable_proc_stack.top();
        if(!proc) {
            proc = BTraitableProcessor::create_default();
            context->m_traitable_proc_stack.push(proc);
        }

        return proc;
    }

};

