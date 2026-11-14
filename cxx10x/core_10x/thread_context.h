//
// Created by AMD on 11/1/2024.
//

#pragma once

#include <thread>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include "py_linkage.h"
#include "stackable_context.h"
#include "btraitable_processor.h"
#include "xcache.h"

class ThreadContext;

using TraitableProcessorStack  = StackableContext<BTraitableProcessor>;
using CacheStack               = StackableContext<XCache>;
using ContextByThread = std::unordered_map<std::thread::id, ThreadContext*>;

class ThreadContext {
public:
    struct Holding { BTraitable* holder; const BTrait* trait; };

private:
    std::thread::id             m_tid;
    TraitableProcessorStack     m_traitable_proc_stack;
    CacheStack                  m_cache_stack;
    unsigned                    m_flags = 0;
    std::unordered_set<TID>     m_serialization_memo;
    std::vector<Holding>        m_holding;          //-- who is being serialized or loaded right now, and which trait of it
    std::unordered_set<TID>     m_embedded_met;     //-- the embedded objects met in the current pass

public:

    ThreadContext() : m_tid(std::this_thread::get_id()) {}

    static PY10X_API ThreadContext &current_context(); // -- this should not be inlined for cross-dll sharing

    static void set_flags(const unsigned flags)     { current_context().m_flags = flags; }
    [[nodiscard]] static unsigned flags()           { return current_context().m_flags; }

    static std::unordered_set<TID> &serialization_memo() {
        return current_context().m_serialization_memo;
    }

    class SerializationScope {
        unsigned m_mode;
        unsigned m_original_flags;

    public:
        SerializationScope(const unsigned mode, const TID& tid)
            : m_mode(mode), m_original_flags(flags()) {
            if (m_mode) {
                set_flags(m_mode);
                serialization_memo().insert(tid.copy_valid());
            }
        }

        ~SerializationScope() {
            if (m_mode) {
                set_flags(m_original_flags);
                serialization_memo().clear();
            }
        }
    };

    class EmbedSerializationScope {
        const TID& m_tid;
        bool m_inserted = false;

    public:
        explicit EmbedSerializationScope(const TID& tid) : m_tid(tid) {
            if (!serialization_memo().insert(m_tid.copy_valid()).second)
                throw py::value_error(
                    py::str("{}/{} - circular embedded serialization")
                        .format(m_tid.cls()->name(), m_tid.id_value()));
            m_inserted = true;
        }

        ~EmbedSerializationScope() {
            if (m_inserted) serialization_memo().erase(m_tid);
        }
    };

    //-- one trait of one holder is being serialized or loaded: whatever is met inside sits there
    class HoldingScope {
    public:
        HoldingScope(BTraitable* holder, const BTrait* trait)   { current_context().m_holding.push_back({holder, trait}); }
        ~HoldingScope() {
            auto& context = current_context();
            context.m_holding.pop_back();
            if (context.m_holding.empty())
                context.m_embedded_met.clear();     //-- the pass is over
        }
        HoldingScope(const HoldingScope&) = delete;
        HoldingScope& operator=(const HoldingScope&) = delete;
    };

    static const Holding* holding() {
        const auto& holding = current_context().m_holding;
        return holding.empty() ? nullptr : &holding.back();
    }

    static bool met_before(const TID& tid)          { return !current_context().m_embedded_met.insert(tid.copy_valid()).second; }

    static XCache* current_cache() {
        auto &context = current_context();
        auto cache = context.m_cache_stack.top();
        if(!cache) {
            cache = XCache::default_cache();
            context.m_cache_stack.push(cache);
        }

        return cache;
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

