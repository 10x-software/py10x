//
// Created by AMD on 3/19/2024.
//
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

namespace py = pybind11;
using pybind11::literals::operator""_a;

#include "py_linkage.h"
#include "bnucleus.h"
#include "btrait.h"
#include "bflags.h"
#include "tid.h"
#include "bnode.h"
#include "btraitable_class.h"
#include "btraitable_ui_extension.h"
#include "btraitable.h"
#include "bprocess_context.h"
#include "xcache.h"
#include "os_user.h"

struct PyBTraitable : BTraitable {
        using BTraitable::BTraitable;

        void deserialize_traits(const py::dict& trait_values) override {
                PYBIND11_OVERRIDE(void, BTraitable, deserialize_traits, trait_values);
        }
};

PYBIND11_MODULE(core_10x_i, m)
{
    m.doc() = "10x kernel";

    //py::module_ cache_layer_m = m.def_submodule( "cache_layer", "cpp.cache_layer" );

    py::enum_<CORE_10X>(m, "CORE_10X")
            .value("PACKAGE_NAME",                      CORE_10X::PACKAGE_NAME)
            .value("XNONE_MODULE_NAME",                 CORE_10X::XNONE_MODULE_NAME)
            .value("XNONE_CLASS_NAME",                  CORE_10X::XNONE_CLASS_NAME)
            .value("RC_MODULE_NAME",                    CORE_10X::RC_MODULE_NAME)
            .value("RC_TRUE_NAME",                      CORE_10X::RC_TRUE_NAME)
            .value("NUCLEUS_MODULE_NAME",               CORE_10X::NUCLEUS_MODULE_NAME)
            .value("NUCLEUS_CLASS_NAME",                CORE_10X::NUCLEUS_CLASS_NAME)
            .value("ANONYMOUS_MODULE_NAME",             CORE_10X::ANONYMOUS_MODULE_NAME)
            .value("ANONYMOUS_CLASS_NAME",              CORE_10X::ANONYMOUS_CLASS_NAME)
            .value("TRAITABLE_ID_MODULE_NAME",          CORE_10X::TRAITABLE_ID_MODULE_NAME)
            .value("TRAITABLE_ID_CLASS_NAME",           CORE_10X::TRAITABLE_ID_CLASS_NAME)
            .value("TRAIT_METHOD_ERROR_MODULE_NAME",    CORE_10X::TRAIT_METHOD_ERROR_MODULE_NAME)
            .value("TRAIT_METHOD_ERROR_CLASS_NAME",     CORE_10X::TRAIT_METHOD_ERROR_CLASS_NAME)
            .value("PACKAGE_REFACTORING_MODULE_NAME",   CORE_10X::PACKAGE_REFACTORING_MODULE_NAME)
            .value("PACKAGE_REFACTORING_CLASS_NAME",    CORE_10X::PACKAGE_REFACTORING_CLASS_NAME)
            .value("PACKAGE_REFACTORING_FIND_CLASS",    CORE_10X::PACKAGE_REFACTORING_FIND_CLASS)
            .value("PACKAGE_REFACTORING_FIND_CLASS_ID", CORE_10X::PACKAGE_REFACTORING_FIND_CLASS_ID)
            .export_values()
            ;

    py::class_<PyLinkage>(m, "PyLinkage")
            .def_static("init",                         &PyLinkage::init)
            .def_static("clear",                        &PyLinkage::clear)
            ;

    py::class_<BNucleus>(m, "BNucleus")
            .def_static("TYPE_TAG",                     &BNucleus::TYPE_TAG)
            .def_static("CLASS_TAG",                    &BNucleus::CLASS_TAG)
            .def_static("REVISION_TAG",                 &BNucleus::REVISION_TAG)
            .def_static("OBJECT_TAG",                   &BNucleus::OBJECT_TAG)
            .def_static("COLLECTION_TAG",               &BNucleus::COLLECTION_TAG)
            .def_static("ID_TAG",                       &BNucleus::ID_TAG)
            .def_static("NX_RECORD_TAG",                &BNucleus::NX_RECORD_TAG)
            .def_static("TYPE_RECORD_TAG",              &BNucleus::TYPE_RECORD_TAG)
            .def_static("PICKLE_RECORD_TAG",            &BNucleus::PICKLE_RECORD_TAG)

            .def_static("serialize_any",                &BNucleus::serialize_any)
            .def_static("deserialize_any",              &BNucleus::deserialize_any)

            .def_static("serialize_type",               &BNucleus::serialize_type)
            .def_static("deserialize_type",             &BNucleus::deserialize_type)
            .def_static("serialize_complex",            &BNucleus::serialize_complex)
            .def_static("deserialize_complex",          &BNucleus::deserialize_complex)
            .def_static("serialize_date",               &BNucleus::serialize_date)
            .def_static("deserialize_date",             &BNucleus::deserialize_date)
            .def_static("serialize_list",               &BNucleus::serialize_list)
            .def_static("deserialize_list",             &BNucleus::deserialize_list)
            .def_static("serialize_dict",               &BNucleus::serialize_dict)
            .def_static("deserialize_dict",             &BNucleus::deserialize_dict)
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
            .def_property_readonly_static("HIDDEN",     [](const py::object&) { return BFlags(BTraitFlags::HIDDEN); })
            ;

    py::class_<BTrait>(m, "BTrait")
            .def(py::init<>())
            .def(py::init<const BTrait&>())
            .def("create_proc",                 &BTrait::create_proc)

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

            .def("set_name",                    &BTrait::set_name)
            .def("flags_on",                    py::overload_cast<uint64_t>(&BTrait::flags_on, py::const_))
            .def("flags_on",                    py::overload_cast<const BFlags&>(&BTrait::flags_on, py::const_))
            .def("set_flags",                   &BTrait::set_flags)
            .def("reset_flags",                 &BTrait::reset_flags)
            .def("modify_flags",                &BTrait::modify_flags)

            .def("set_f_get",                   &BTrait::set_f_get)
            .def("set_f_set",                   &BTrait::set_f_set)
            .def("set_f_verify",                &BTrait::set_f_verify)
            .def("set_f_from_str",              &BTrait::set_f_from_str)
            .def("set_f_from_any_xstr",         &BTrait::set_f_from_any_xstr)
            .def("set_f_is_acceptable_type",    &BTrait::set_f_is_acceptable_type)
            .def("set_f_to_str",                &BTrait::set_f_to_str)
            .def("set_f_serialize",             &BTrait::set_f_serialize)
            .def("set_f_deserialize",           &BTrait::set_f_deserialize)
            .def("set_f_to_id",                 &BTrait::set_f_to_id)
            .def("set_f_choices",               &BTrait::set_f_choices)
            .def("set_f_style_sheet",           &BTrait::set_f_style_sheet)
            .def("custom_f_get",                &BTrait::custom_f_get)
            .def("custom_f_verify",             &BTrait::custom_f_verify)
            .def("custom_f_from_str",           &BTrait::custom_f_from_str)
            .def("custom_f_from_any_xstr",      &BTrait::custom_f_from_any_xstr)
            .def("custom_f_to_str",             &BTrait::custom_f_to_str)
            .def("custom_f_serialize",          &BTrait::custom_f_serialize)
            .def("custom_f_to_id",              &BTrait::custom_f_to_id)
            .def("custom_f_choices",            &BTrait::custom_f_choices)
            ;

    py::class_<NODE_TYPE>(m, "NODE_TYPE")
            .def_readonly_static("BASIC",       &NODE_TYPE::BASIC)
            .def_readonly_static("TREE",        &NODE_TYPE::TREE)
            .def_readonly_static("BASIC_GRAPH", &NODE_TYPE::BASIC_GRAPH)
            .def_readonly_static("BASIC_GRAPH", &NODE_TYPE::UI)
            //.def_readonly_static("GRAPH",       &NODE_TYPE::GRAPH)
            ;

    py::class_<BasicNode>(m, "BasicNode")
            .def_static("create",               &BasicNode::create)
            .def("is_valid",                    &BasicNode::is_valid)
            .def("is_set",                      &BasicNode::is_set)
            .def("is_valid_and_not_set",        &BasicNode::is_valid_and_not_set)
            .def("make_valid",                  &BasicNode::make_valid)
            .def("make_invalid",                &BasicNode::make_invalid)
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

    py::class_<XCache>(m, "XCache")
            .def_static("clear", &XCache::clear)
//            .def(py::init<>())
//            .def("find_object_cache",           &XCache::find_object_cache)
//            .def("find_node",                   py::overload_cast<const TID&, BTrait*>(XCache::find_node))
//            .def("find_node",                   py::overload_cast<const TID&, BTrait*, const py::args&>(&XCache::find_node))
//            .def("default_node_type",           &XCache::default_node_type)
            ;

//    py::class_<SimpleCacheLayer, BCache>(m, "SimpleCacheLayer")
//            .def(py::init<>())
//            .def(py::init<BCache*>())
//            ;

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
            .def("load",                        &BTraitableClass::load)
            ;

    py::class_<BTraitable,PyBTraitable>(m, "BTraitable")
            .def(py::init<BTraitableClass*, const py::object&>())
            .def("initialize",                  &BTraitable::initialize)
            .def("share",                       &BTraitable::share,
                        "Share object",
                        "accept_existing"_a
                )
            .def("accept_existing",               &BTraitable::accept_existing)
            .def("id_exists",                   &BTraitable::id_exists)
            .def("id",                          &BTraitable::id)
            .def("id_value",                    &BTraitable::id_value)
            .def("xid",                         &BTraitable::tid, py::return_value_policy::reference)
            .def("from_any",                    &BTraitable::from_any)
            .def("value_to_str",                &BTraitable::value_to_str)
            .def("get_revision",                &BTraitable::get_revision)
            .def("set_revision",                &BTraitable::set_revision)
            .def("get_value",                   py::overload_cast<const py::str&>(&BTraitable::get_value))
            .def("get_value",                   py::overload_cast<const py::str&, const py::args&>(&BTraitable::get_value))
            .def("get_value",                   py::overload_cast<BTrait*>(&BTraitable::get_value))
            .def("get_value",                   py::overload_cast<BTrait*, const py::args&>(&BTraitable::get_value))
            .def("get_style_sheet",             &BTraitable::get_style_sheet)
            .def("get_choices",                 &BTraitable::get_choices)
            .def("set_value",                   py::overload_cast<const py::str&, const py::object&>(&BTraitable::set_value),
                        "Set trait value",
                        "trait_name"_a, "value"_a
                )
            .def("set_value",                   py::overload_cast<const py::str&, const py::object&, const py::args&>(&BTraitable::set_value),
                        "Set trait value with *args",
                        "trait_name"_a, "value"_a
                )
            .def("set_value",                   py::overload_cast<BTrait*, const py::object&>(&BTraitable::set_value),
                        "Set trait value",
                        "trait"_a, "value"_a
                )
            .def("set_value",                   py::overload_cast<BTrait*, const py::object&, const py::args&>(&BTraitable::set_value),
                        "Set trait value with *args",
                        "trait"_a, "value"_a
                )
            .def("is_valid",                    py::overload_cast<const py::str&>(&BTraitable::is_valid))
            .def("is_valid",                    py::overload_cast<BTrait*>(&BTraitable::is_valid))
            .def("invalidate_value",            py::overload_cast<const py::str&>(&BTraitable::invalidate_value))
            .def("invalidate_value",            py::overload_cast<const py::str&, const py::args&>(&BTraitable::invalidate_value))
            .def("invalidate_value",            py::overload_cast<BTrait*>(&BTraitable::invalidate_value))
            .def("invalidate_value",            py::overload_cast<BTrait*, const py::args&>(&BTraitable::invalidate_value))
            .def("raw_set_value",               py::overload_cast<const py::str&, const py::object&>(&BTraitable::raw_set_value))
            .def("raw_set_value",               py::overload_cast<const py::str&, const py::object&, const py::args&>(&BTraitable::raw_set_value))
            .def("raw_set_value",               py::overload_cast<BTrait*, const py::object&>(&BTraitable::raw_set_value))
            .def("raw_set_value",               py::overload_cast<BTrait*, const py::object&, const py::args&>(&BTraitable::raw_set_value))
            .def("_set_values",                 &BTraitable::set_values)
            .def("serialize_nx",                &BTraitable::serialize_nx)
            .def_static("deserialize_nx",       &BTraitable::deserialize_nx)
            .def("serialize_object",            &BTraitable::serialize_object)
            .def("deserialize_traits",          &BTraitable::deserialize_traits)
            .def_static("deserialize_object",   &BTraitable::deserialize_object,
                        "Deserialize object",
                        "bclass"_a, "collection_name"_a, "serialized_data"_a
                )
            .def("reload",                      &BTraitable::reload)
            .def("bui_class",                   &BTraitable::bui_class, py::return_value_policy::reference)
            ;

    py::class_<BTraitableProcessor>(m, "BTraitableProcessor")
            .def_readonly_static("PLAIN",       &BTraitableProcessor::PLAIN)
            .def_readonly_static("DEBUG",       &BTraitableProcessor::DEBUG)
            .def_readonly_static("CONVERT_VALUES",  &BTraitableProcessor::CONVERT_VALUES)
            .def_readonly_static("ON_GRAPH",    &BTraitableProcessor::ON_GRAPH)
            .def_static("create",               &BTraitableProcessor::create,
                        "Create a new BTraitableProcessor based on parameters",
                        "on_graph"_a, "convert_values"_a, "debug"_a, "use_parent_cache"_a, "use_default_cache"_a
                )
            .def_static("create_interactive",   &BTraitableProcessor::create_interactive)
            .def_static("change_mode",          &BTraitableProcessor::change_mode,
                        "Change the current BTraitableProcessor based on parameters",
                        "convert_values"_a, "debug"_a, "use_default_cache"_a
                )
            .def_static("current",              &BTraitableProcessor::current, py::return_value_policy::reference)
            .def("cache",                       &BTraitableProcessor::cache)
            .def("begin_using",                 &BTraitableProcessor::begin_using)
            .def("end_using",                   &BTraitableProcessor::end_using)
            .def("__enter__",                   &BTraitableProcessor::py_enter)
            .def("__exit__",                    &BTraitableProcessor::py_exit)
            .def("flags",                       &BTraitableProcessor::flags)
            .def("share_object",                &BTraitableProcessor::share_object)
            .def("export_nodes",                &BTraitableProcessor::export_nodes)
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
            .def("__deepcopy__",                &BFlags::copy, py::arg("memo"))
            .def_static("modified",             &BFlags::modify)
            .def_static("check",                &BFlags::check)
            ;

    py::class_<BUiClass>(m, "BUiClass")
            .def("create_ui_node",              &BUiClass::create_ui_node)
            .def("update_ui_node",              &BUiClass::update_ui_node)
            ;

    py::class_<OsUser>(m, "OsUser")
            .def_readonly_static("me",          &OsUser::me)
            .def("name",                        &OsUser::name)
            ;
}
