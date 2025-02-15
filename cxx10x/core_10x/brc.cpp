//
// Created by AMD on 5/20/2024.
//

#include "brc.h"


BRC::BRC(int rc, const py::object& data) : m_rc(rc) {
    if (!data.is_none())
        m_payload.append(data);
}

BRC& BRC::add_str_error(const py::object& err) {
    if (is_success())
        m_rc = 0;

    m_payload.append(err);
    return *this;
}

BRC& BRC::add_rc(const BRC& other) {
    if (!other.is_empty()) {
        auto success = is_success();
        auto other_success = other.is_success();
        if (success != other_success && !is_empty())
            throw py::value_error(py::str("May not add {} to an {}").format(other.nickname(), nickname()));

        if (success)
            m_rc = 0;

        for (const auto &item: other.m_payload)
            m_payload.append(item);
    }

    return *this;
}

BRC& BRC::add_data(const py::object& data) {
    if (!is_success())
        throw py::value_error(py::str("May not add_data() to an 'error' RC"));

    m_payload.append(data);
    return *this;
}

//-- NOTE: if a payload has only one element, it returns just it; otherwise the entire list is returned
py::object BRC::payload() const {
    return len(m_payload) == 1? m_payload[0] : m_payload;
}