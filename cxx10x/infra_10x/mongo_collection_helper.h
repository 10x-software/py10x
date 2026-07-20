//
// Created by AMD on 2/9/2025.
//
#pragma once

#include "py_linkage.h"

class MongoCollectionHelper {
public:
    static void prepare_filter_and_pipeline(py::dict& serialized_traitable, py::dict& filter, py::list& pipeline);
};
