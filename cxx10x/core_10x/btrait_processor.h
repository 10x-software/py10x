//
// Created by AMD on 2/22/2025.
//

#pragma once

#include "py_linkage.h"

class BasicNode;
class BTrait;
class BTraitableProcessor;

using PyBoundMethod = std::function<py::object()>;

class BTraitProcessor {
public:

    static py::object get_node_value_on_graph(BTraitableProcessor* proc, BasicNode* node, const PyBoundMethod& f);

    //---- Getting trait value

    virtual py::object  get_value_off_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait);
    virtual py::object  get_value_off_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait, const py::args& args);

    virtual py::object  get_value_on_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait);
    virtual py::object  get_value_on_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait, const py::args& args);

    py::object get_choices_off_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait);
    py::object get_choices_on_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait);

    //---- Invalidating trait value

    virtual void invalidate_value_off_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait);
    virtual void invalidate_value_off_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait, const py::args& args);

    virtual void invalidate_value_on_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait);
    virtual void invalidate_value_on_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait, const py::args& args);

    //---- Setting (raw) trait value

    virtual py::object raw_set_value_off_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait, const py::object& value);
    virtual py::object raw_set_value_off_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait, const py::object& value, const py::args& args );

    virtual py::object raw_set_value_on_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait, const py::object& value);
    virtual py::object raw_set_value_on_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait, const py::object& value, const py::args& args);

};

class EvalOnceProc : public BTraitProcessor {
    static py::object dont_touch_me(BTraitable* obj, BTrait* trait);

public:

    py::object get_value_off_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait) final;
    py::object get_value_off_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait, const py::args& args) final;

    py::object get_value_on_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait) final {
        return get_value_off_graph(proc, obj, trait);
    }

    py::object get_value_on_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait, const py::args& args) final {
        return get_value_off_graph(proc, obj, trait, args);
    }

    void invalidate_value_off_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait) final {
        dont_touch_me(obj, trait);
    }

    void invalidate_value_off_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait, const py::args& args) final {
        dont_touch_me(obj, trait);
    }

    py::object raw_set_value_off_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait, const py::object& value) final {
        return dont_touch_me(obj, trait);
    }

    py::object raw_set_value_off_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait, const py::object& value, const py::args& args ) final {
        return dont_touch_me(obj, trait);
    }

    py::object raw_set_value_on_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait, const py::object& value) final {
        return dont_touch_me(obj, trait);
    }

    py::object raw_set_value_on_graph(BTraitableProcessor* proc, BTraitable* obj, BTrait* trait, const py::object& value, const py::args& args) final {
        return dont_touch_me(obj, trait);
    }

};
