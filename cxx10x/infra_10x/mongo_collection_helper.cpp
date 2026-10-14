//
// Created by AMD on 2/9/2025.
//

#include "mongo_collection_helper.h"

namespace {

struct Keys {
    PyObject* rev_tag;       // borrowed/immortal interned
    PyObject* id_tag;
    PyObject* literal;
    PyObject* eq;
    PyObject* and_;
    PyObject* cond;
    PyObject* new_root;
    PyObject* replace_root;
    PyObject* field;
    PyObject* input;
    PyObject* value;
    PyObject* set_field;
    PyObject* replace_with;
    PyObject* root;
    PyObject* dollar;

    Keys()
        : rev_tag(nullptr),
          id_tag(nullptr),
          literal(intern("$literal")),
          eq(intern("$eq")),
          and_(intern("$and")),
          cond(intern("$cond")),
          new_root(intern("newRoot")),
          replace_root(intern("$replaceRoot")),
          field(intern("field")),
          input(intern("input")),
          value(intern("value")),
          set_field(intern("$setField")),
          replace_with(intern("$replaceWith")),
          root(intern("$$ROOT")),
          dollar(intern("$")) {
        // Same Nucleus class PyLinkage caches after core_10x init. Resolved via
        // Python import so py10x_infra stays link-independent of py10x_kernel.
        py::object nucleus = py::module_::import("core_10x.nucleus").attr("Nucleus");
        rev_tag = intern_obj(nucleus.attr("REVISION_TAG")());
        id_tag = intern_obj(nucleus.attr("ID_TAG")());
    }

private:
    static PyObject* intern(const char* s) {
        PyObject* o = PyUnicode_InternFromString(s);
        if (!o)
            throw py::error_already_set();
        return o;  // intentionally leaked / immortal for process lifetime
    }

    static PyObject* intern_obj(const py::handle& tag) {
        PyObject* o = tag.ptr();
        Py_INCREF(o);
        PyUnicode_InternInPlace(&o);
        return o;  // keep the strong ref forever
    }
};

const Keys& keys() {
    static const Keys k;
    return k;
}

py::handle h(PyObject* o) { return py::handle(o); }

py::object dict_pop(py::dict& d, PyObject* key) {
    PyObject* val = PyDict_GetItemWithError(d.ptr(), key);  // borrowed
    if (!val) {
        if (PyErr_Occurred())
            throw py::error_already_set();
        throw py::key_error(py::str(h(key)));
    }
    Py_INCREF(val);
    if (PyDict_DelItem(d.ptr(), key) < 0) {
        Py_DECREF(val);
        throw py::error_already_set();
    }
    return py::reinterpret_steal<py::object>(val);
}

}  // namespace

void MongoCollectionHelper::prepare_filter_and_pipeline(py::dict& serialized_traitable, py::dict& filter, py::list& pipeline) {
    const Keys& k = keys();

    py::object revision = dict_pop(serialized_traitable, k.rev_tag);
    py::object id_value = dict_pop(serialized_traitable, k.id_tag);
    filter[h(k.id_tag)] = id_value;
    filter[h(k.rev_tag)] = revision;

    const int rev = revision.cast<int>();
    if (rev <= 0)
        throw py::value_error(
            py::str("Revision must be >= 1: {}; serialized traitable:\n{}")
                .format(revision, serialized_traitable));

    py::list rev_parts;
    py::list field_stages;

    for (auto [key, val] : serialized_traitable) {
        py::dict lit_val;
        lit_val[h(k.literal)] = val;

        PyObject* field_ref = PyUnicode_Concat(k.dollar, key.ptr());
        if (!field_ref)
            throw py::error_already_set();
        auto field_path = py::reinterpret_steal<py::object>(field_ref);

        py::list named_lit_val;
        named_lit_val.append(field_path);
        named_lit_val.append(lit_val);

        py::dict eq_ed;
        eq_ed[h(k.eq)] = named_lit_val;
        rev_parts.append(eq_ed);

        py::dict value;
        value[h(k.literal)] = val;

        py::dict set_field_items;
        set_field_items[h(k.field)] = key;
        set_field_items[h(k.input)] = h(k.root);
        set_field_items[h(k.value)] = value;

        py::dict set_field;
        set_field[h(k.set_field)] = set_field_items;

        py::dict replace_with;
        replace_with[h(k.replace_with)] = set_field;
        field_stages.append(replace_with);
    }

    py::dict rev_condition;
    rev_condition[h(k.and_)] = rev_parts;

    py::list conditions;
    conditions.append(rev_condition);
    conditions.append(revision);
    conditions.append(py::int_(rev + 1));

    py::dict update_revision;
    update_revision[h(k.cond)] = conditions;

    py::dict new_root_items;
    new_root_items[h(k.id_tag)] = id_value;
    new_root_items[h(k.rev_tag)] = update_revision;

    py::dict new_root;
    new_root[h(k.new_root)] = new_root_items;

    py::dict replace_root;
    replace_root[h(k.replace_root)] = new_root;
    pipeline.append(replace_root);

    if (PyList_SetSlice(pipeline.ptr(),
                        PyList_GET_SIZE(pipeline.ptr()),
                        PyList_GET_SIZE(pipeline.ptr()),
                        field_stages.ptr()) != 0)
        throw py::error_already_set();
}
