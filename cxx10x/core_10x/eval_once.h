//
// Created by AMD on 1/20/2025.
//

#pragma once

#include <functional>
#include <optional>

template <typename T, typename X>
class EvalOnce {
    mutable std::optional<T>    m_value;
    std::function<T(X*)>        m_method;

public:
    explicit EvalOnce(std::function<T(X*)> method) : m_value(std::nullopt), m_method(std::move(method))   {}

    T get(X* obj) const {
        if (!m_value.has_value())
            m_value = m_method(obj);
        return m_value.value();
    }

    void reset() {
        m_value.reset();
    }
};

#define eval_once(X, T, method)      EvalOnce<T, X> m_##method = EvalOnce<T, X>([](X* self) { return self->method##_get(); }); \
    public: T method() { return m_##method.get(this); }
