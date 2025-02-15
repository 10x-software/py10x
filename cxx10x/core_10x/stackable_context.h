//
// Created by AMD on 11/1/2024.
//

#pragma once

#include <deque>
#include <cassert>

template <typename Stackable>
class StackableContext {
    using Stack = std::deque<Stackable*>;
    Stack   m_stack;

public:
    void push(Stackable* stackable) {
        if (stackable)
            m_stack.push_back(stackable);
    }

    Stackable* pop() {
        if (m_stack.empty())
            return nullptr;

        auto top = m_stack.back();
        m_stack.pop_back();
        return top;
    }

    Stackable* top() const {
        return m_stack.empty()? nullptr : m_stack.back();
    }

    class Use {
        StackableContext&   m_context;
        Stackable*          m_stackable;
        bool                m_keep;
    public:
        Use(StackableContext& context, Stackable* stackable, bool keep = false) : m_context(context), m_keep(keep), m_stackable(stackable) {
            context.push(stackable);
        }

        ~Use() {
            if (m_stackable) {
                auto top = m_context.pop();
                assert(top == m_stackable);
                if (!m_keep)
                    delete top;
            }
        }
    };

};