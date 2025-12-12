//
// Created by AMD on 5/20/2024.
//
#pragma once

#include "py_linkage.h"

class BRC {
//public:
//    int         m_rc;
//    py::list    m_payload;
//
//    BRC() : BRC(true)                                           {}
//    explicit BRC(bool rc) : m_rc(rc)                            {}  // for RC(True) or RC(False), the latter is used to capture a current exception
//    BRC(bool rc, const py::object& data) : BRC((int) rc, data)  {}
//    BRC(int rc, const py::object& data);
//    BRC(const BRC& brc) = default;
//
//    [[nodiscard]] bool          is_success() const      { return m_rc > 0; }
//    [[nodiscard]] bool          is_empty() const        { return m_payload.empty(); }
//    [[nodiscard]] const char*   nickname() const        { return is_success()? "'payload'" : "'errata'"; }
//
//    [[nodiscard]] py::object    payload() const;
//
//    BRC& add_str_error(const py::object& err);
//    BRC& add_rc(const BRC& other);
//    BRC& add_data(const py::object& data);
    py::object m_rc;

public:
    BRC() : BRC(PyLinkage::RC_TRUE().attr("new_rc")()) {}

    explicit BRC(py::object rc) : m_rc(rc) {}

    [[nodiscard]] explicit operator bool() const {
        return py::cast<bool>(m_rc);
    }

    [[nodiscard]] py::object payload() const {
        return m_rc.attr("data")();
    }

    [[nodiscard]] py::str error() const {
        return m_rc.attr("error")();
    }

    py::object operator () () {
        return m_rc;
    }

    // TODO: these are just virtual calls into python -- use pybind..
    [[nodiscard]] py::object add_error(const std::string& err) const {
        const auto py_f = m_rc.attr("add_error");
        return py_f(py::str(err));
    }

    [[nodiscard]] py::object add_error(const py::object& rc) const {
        const auto py_f = m_rc.attr("add_error");
        return py_f(rc);
    }

    py::object add_data(const py::object& data) {
        auto py_f = m_rc.attr("add_error");
        return py_f(data);
    }
};

