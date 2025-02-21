//
// Created by AMD on 3/19/2024.
//
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

namespace py = pybind11;

#include "py_linkage.h"
#include "btrait.h"
#include "bflags.h"
#include "tid.h"
#include "bnode.h"
#include "bcache.h"
#include "btraitable_class.h"
#include "btraitable.h"
#include "bprocess_context.h"

PYBIND11_MODULE(core_10x_i, m)
{
    m.doc() = "10x kernel";

    //py::module_ cache_layer_m = m.def_submodule( "cache_layer", "cpp.cache_layer" );

    py::class_<PyLinkage>(m, "PyLinkage")
            .def_static("init",                         &PyLinkage::init)
            .def_static("redirect_stdout_to_python",    &PyLinkage::redirect_stdout_to_python)
            ;

    py::class_<BProcessContext>(m, "BProcessContext")
            .def_readonly_static("CACHE_ONLY",          &BProcessContext::CACHE_ONLY)
            .def_readonly_static("TP_TYPE",             &BProcessContext::TP_TYPE)
            .def_readonly_static("BPC",                 &BProcessContext::PC)
            .def("flags",                               &BProcessContext::flags)
            .def("flags_on",                            &BProcessContext::flags_on)
            .def("replace_flags",                       &BProcessContext::replace_flags)
            .def("set_flags",                           &BProcessContext::set_flags)
            .def("reset_flags",                         &BProcessContext::reset_flags)
            .def("set_reset_flags",                     &BProcessContext::set_reset_flags)
            .def("topic",                               &BProcessContext::topic)
            .def("set_topic",                           &BProcessContext::set_topic)
            ;

    py::class_<BTraitFlags>(m, "BTraitFlags")
            .def_property_readonly_static("RESERVED",   [](const py::object&) { return BFlags(BTraitFlags::RESERVED); })
            .def_property_readonly_static("ID",         [](const py::object&) { return BFlags(BTraitFlags::ID); })
            .def_property_readonly_static("HASH",       [](const py::object&) { return BFlags(BTraitFlags::HASH); })
            .def_property_readonly_static("READONLY",   [](const py::object&) { return BFlags(BTraitFlags::READONLY); })
            .def_property_readonly_static("NOT_EMPTY",  [](const py::object&) { return BFlags(BTraitFlags::NOT_EMPTY); })
            .def_property_readonly_static("RUNTIME",    [](const py::object&) { return BFlags(BTraitFlags::RUNTIME); })
            .def_property_readonly_static("EMBEDDED",   [](const py::object&) { return BFlags(BTraitFlags::EMBEDDED); })
            .def_property_readonly_static("EVAL_ONCE",  [](const py::object&) { return BFlags(BTraitFlags::EVAL_ONCE); })
            .def_property_readonly_static("EXPENSIVE",  [](const py::object&) { return BFlags(BTraitFlags::EXPENSIVE); })
            ;

    py::class_<BTrait>(m, "BTrait")
            .def(py::init<>())
            .def(py::init<const BTrait&>())

            .def_readwrite("name",              &BTrait::m_name)
            .def_readwrite("flags",             &BTrait::m_flags)
            .def_readwrite("data_type",         &BTrait::m_datatype)
            .def_readwrite("default",           &BTrait::m_default)

            .def_readonly("f_get",              &BTrait::f_get)
            .def_readonly("f_set",              &BTrait::f_set)
            .def_readonly("f_verify",           &BTrait::f_verify)
            .def_readonly("f_from_str",         &BTrait::f_from_str)
            .def_readonly("f_from_any_xstr",    &BTrait::f_from_any_xstr)
            .def_readonly("f_to_str",           &BTrait::f_to_str)
            .def_readonly("f_serialize",        &BTrait::f_serialize)
            .def_readonly("f_deserialize",      &BTrait::f_deserialize)
            .def_readonly("f_to_id",            &BTrait::f_to_id)
            //.def_readonly("f_acceptable_type", &BTrait::f_is_acceptable_type)

            .def("flags_on",                    py::overload_cast<unsigned>(&BTrait::flags_on, py::const_))
            .def("flags_on",                    py::overload_cast<const BFlags&>(&BTrait::flags_on, py::const_))

            .def("set_f_get",                   &BTrait::set_f_get)
            .def("set_f_set",                   &BTrait::set_f_set)
            .def("set_f_verify",                &BTrait::set_f_verify)
            .def("set_f_from_str",              &BTrait::set_f_from_str)
            .def("set_f_from_any_xstr",         &BTrait::set_f_from_any_xstr)
            .def("set_f_to_str",                &BTrait::set_f_to_str)
            .def("set_f_serialize",             &BTrait::set_f_serialize)
            .def("set_f_deserialize",           &BTrait::set_f_deserialize)
            .def("set_f_to_id",                 &BTrait::set_f_to_id)
            ;

    py::class_<NODE_TYPE>(m, "NODE_TYPE")
            .def_readonly_static("BASIC",       &NODE_TYPE::BASIC)
            .def_readonly_static("TREE",        &NODE_TYPE::TREE)
            .def_readonly_static("BASIC_GRAPH", &NODE_TYPE::BASIC_GRAPH)
            .def_readonly_static("GRAPH",       &NODE_TYPE::GRAPH)
            ;

    py::class_<BasicNode>(m, "BasicNode")
            .def_static("create",               &BasicNode::create)
            .def("is_valid",                    &BasicNode::is_valid)
            .def("is_set",                      &BasicNode::is_set)
            .def("is_valid_and_not_set",        &BasicNode::is_valid_and_not_set)
            .def("value",                       &BasicNode::value)
            .def("parents",                     &BasicNode::parents)
            .def("children",                    &BasicNode::children)
            .def("assign",                      &BasicNode::assign)
            .def("set",                         &BasicNode::set)
            .def("invalidate",                  &BasicNode::invalidate)
            .def("add_child",                   &BasicNode::add_child)
            .def("add_parent",                  &BasicNode::add_parent)
            .def("children",                    &BasicNode::children)
            .def("parents",                     &BasicNode::parents)
            ;

    py::class_<ObjectCache>(m, "ObjectCache")
            .def("find_node",                   py::overload_cast<BTrait*>(&ObjectCache::find_node, py::const_))
            .def("find_node",                   py::overload_cast<BTrait*, const py::args&>(&ObjectCache::find_node, py::const_))
            ;

    py::class_<BCache>(m, "BCache")
            .def(py::init<>())
            .def(py::init<BCache*>())
            .def("find_object_cache",           &BCache::find_object_cache)
            .def("find_node",                   py::overload_cast<const TID&, BTrait*>(&BCache::find_node))
            .def("find_node",                   py::overload_cast<const TID&, BTrait*, const py::args&>(&BCache::find_node))
            ;

    py::class_<TID>(m, "TID")
            .def("class_name",                  [](TID* tid) { return tid->cls()->name(); } )
            .def("id",                          &TID::id)
            ;

    py::class_<BTraitableClass>(m, "BTraitableClass")
            .def(py::init<const py::object&>())
            .def("name",                        &BTraitableClass::name)
            .def("trait_dir",                   &BTraitableClass::trait_dir)
            .def("is_storable",                 &BTraitableClass::is_storable)
            .def("is_id_endogenous",            &BTraitableClass::is_id_endogenous)
            .def("find_trait",                  &BTraitableClass::find_trait)
            .def("deserialize",                 &BTraitableClass::deserialize)
            .def("deserialize_object",          &BTraitableClass::deserialize_object)
            .def("load",                        &BTraitableClass::load)
            ;

    py::class_<BTraitable>(m, "BTraitable")
            .def(py::init<const py::object&>())
            .def("set_id",                      &BTraitable::set_id)
            .def("initialize",                  &BTraitable::initialize)
            .def("id",                          &BTraitable::id)
            .def("xid",                         &BTraitable::tid)
            .def("from_any",                    &BTraitable::from_any)
            .def("get_value",                   py::overload_cast<BTrait*>(&BTraitable::get_value))
            .def("get_value",                   py::overload_cast<BTrait*, const py::args&>(&BTraitable::get_value))
            .def("set_value",                   py::overload_cast<BTrait*, const py::object&>(&BTraitable::set_value))
            .def("set_value",                   py::overload_cast<BTrait*, const py::object&, const py::args&>(&BTraitable::set_value))
            .def("invalidate_value",            py::overload_cast<BTrait*>(&BTraitable::invalidate_value))
            .def("invalidate_value",            py::overload_cast<BTrait*, const py::args&>(&BTraitable::invalidate_value))
            .def("set_values",                  &BTraitable::set_values)
            .def("serialize",                   &BTraitable::serialize)
            .def("reload",                      &BTraitable::reload)
            ;

    py::class_<BTraitableProcessor>(m, "TP")
            .def_readonly_static("PLAIN",           &BTraitableProcessor::PLAIN)
            .def_readonly_static("DEBUG",           &BTraitableProcessor::DEBUG)
            .def_readonly_static("CONVERT_VALUES",  &BTraitableProcessor::CONVERT_VALUES)
            .def_readonly_static("ON_GRAPH",        &BTraitableProcessor::ON_GRAPH)
            //.def("__enter__",                       &BTraitableProcessor::begin_using)
            //.def("__exit__",                        &BTraitableProcessor::stop_using)
            ;

    py::class_<BFlags>(m, "BFlags")
            .def(py::init<>())
            .def(py::init<unsigned>())
            .def(py::init<const BFlags&>())
            .def("value",                       &BFlags::value)
            .def("on",                          &BFlags::on)
            .def("off",                         &BFlags::off)
            .def("on_off",                      &BFlags::on_off)
            .def("set",                         &BFlags::set)
            .def("reset",                       &BFlags::reset)
            .def("set_reset",                   &BFlags::set_reset)
            .def("next",                        &BFlags::next)
            .def("__repr__",                    &BFlags::repr)
            .def("__or__",                      &BFlags::add)
            .def("__add__",                     &BFlags::add)
            .def("__sub__",                     &BFlags::sub)
            .def_static("modified",             &BFlags::modify)
            .def_static("check",                &BFlags::check)
            ;

}
