//
// Created by AMD on 3/12/2025.
//
#pragma once

#include <string>
#include <stdexcept>

#include "py_linkage.h"

class OsUser {
    std::string     m_name;

    static bool get_user_name(std::string& user_name);

public:
    static OsUser me;

    const std::string& name() {
        if (m_name.empty())
            if (!get_user_name(m_name))
                throw py::value_error("Failed to get OS user name");
        return m_name;
    }
};

