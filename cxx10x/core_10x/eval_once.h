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

    void reset() const {
        m_value.reset();
    }
};

#define eval_once(X, T, method)      EvalOnce<T, X> m_##method = EvalOnce<T, X>([](X* self) { return self->method##_get(); }); \
    public: T method() { return m_##method.get(this); }

#define eval_once_const(X, T, method)   EvalOnce<T, const X> m_##method = EvalOnce<T, const X>([](const X* self) { return self->method##_get(); }); \
    public: T method() const { return m_##method.get(this); }

//-- NOTE: you must define a member function: 'method'_get() const which returns py::object* - newly allocated
#define py_object_eval_once(method) \
    mutable std::unique_ptr<py::object> m_##method = nullptr; \
    public: const py::object& method() { \
        if (!m_##method) m_##method = std::make_unique<py::object>(method##_get()); \
        return *m_##method;

