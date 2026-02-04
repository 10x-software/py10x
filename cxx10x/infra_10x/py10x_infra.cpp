//
// Created by IAP on 2/7/2025.
//
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

//#include "mongo_db_driver.h"
#include "mongo_collection_helper.h"

namespace py = pybind11;

PYBIND11_MODULE(py10x_infra, m)
{
    m.doc() = "10x infra";

//    py::class_<MongoDbDriver>(m, "MongoDbDriver")
//           .def_static("client", &MongoDbDriver::connect, py::return_value_policy::take_ownership)  // Ensures Python owns the returned client
//           .def_static("collection", &MongoDbDriver::collection, py::return_value_policy::take_ownership, py::keep_alive<1, 0>())  // This alone is NOT enough
//           .def_static("save_via_update_one", &MongoDbDriver::save_via_update_one);
//            ;
//    py::class_<mongocxx::v_noabi::client>(m, "mongocxx_client")
//           .def("uri", &mongocxx::client::uri)
//           ;
//    py::class_<mongocxx::v_noabi::collection>(m, "mongocxx_collection")
//           .def("name", &mongocxx::v_noabi::collection::name)
//           ;

    py::class_<MongoCollectionHelper>(m, "MongoCollectionHelper")
            .def_static("prepare_filter_and_pipeline",  &MongoCollectionHelper::prepare_filter_and_pipeline)
            ;
}
