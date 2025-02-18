//
// Created by AMD on 5/21/2024.
//

#pragma once

#include <unordered_map>

#include <pybind11/pybind11.h>
#include <pybind11/pytypes.h>
#include <pybind11/functional.h>
#include <pybind11/stl.h>

namespace py = pybind11;

using EID = py::object;

template<>
struct std::equal_to<py::object> {
    bool operator() (const py::object& a, const py::object& b) const    { return a.equal(b); }
};

template<>
struct std::hash<py::object> {
    std::size_t operator() (py::object const& key) const noexcept   { return py::hash(key); }
};

