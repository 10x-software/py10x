//
// Created by AMD on 2/24/2025.
//

#pragma once

#include "btraitable_processor.h"

class IdBuilder : public BTraitableProcessor {
protected:
    BTraitable*             m_obj;
    BTraitableProcessor*    m_parent_proc;

    void check_object(BTraitable* obj, BTrait* trait, const char* method);

public:
    static IdBuilder* create(BTraitable* obj, BTraitableProcessor* parent = nullptr);

    explicit IdBuilder(BTraitable* obj, BTraitableProcessor* parent);

    py::object  set_trait_value(BTraitable* obj, BTrait* trait, const py::object& value) final;
    py::object  set_trait_value(BTraitable* obj, BTrait* trait, const py::object& value, const py::args& args) final;

    void        invalidate_trait_value(BTraitable* obj, BTrait* trait) final;
    void        invalidate_trait_value(BTraitable* obj, BTrait* trait, const py::args& args) final;

    py::object  get_trait_value(BTraitable* obj, BTrait* trait) final;
    py::object  get_trait_value(BTraitable* obj, BTrait* trait, const py::args& args) final;

    py::object  get_choices(BTraitable*, BTrait*) final     { throw py::type_error(py::str("May not be called")); }
    py::object  get_style_sheet(BTraitable*, BTrait*) final { throw py::type_error(py::str("May not be called")); }

    py::object  adjust_set_value(BTraitable* obj, BTrait* trait, const py::object& value) override;
    py::object  raw_set_trait_value(BTraitable* obj, BTrait* trait, const py::object& value) final;
    py::object  raw_set_trait_value(BTraitable* obj, BTrait* trait, const py::object& value, const py::args& args) final;

};

class IdBuilderDebug : public IdBuilder {
public:
    IdBuilderDebug(BTraitable* obj, BTraitableProcessor* parent) : IdBuilder(obj, parent) {}

    py::object  adjust_set_value(BTraitable* obj, BTrait* trait, const py::object& value) final;
};

class IdBuilderConvertValues : public IdBuilder {
public:
    IdBuilderConvertValues(BTraitable* obj, BTraitableProcessor* parent) : IdBuilder(obj, parent) {}

    py::object  adjust_set_value(BTraitable* obj, BTrait* trait, const py::object& value) final;

};