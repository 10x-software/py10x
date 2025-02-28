//
// Created by AMD on 2/24/2025.
//

#include "id_builder.h"
#include "thread_context.h"
#include "btraitable.h"

class IdBuilderCache : public BCache {
    ObjectCache*    m_oc;
public:
    explicit IdBuilderCache(BTraitable* obj) {
        m_oc = obj->id_cache();
    }

    [[nodiscard]]ObjectCache*   find_object_cache(const TID& tid) const final      { return m_oc; }
    ObjectCache*                find_or_create_object_cache(const TID& tid) final  { return m_oc; }
};

IdBuilder* IdBuilder::create(BTraitable *obj, BTraitableProcessor *parent) {
    if (!parent)
        parent = ThreadContext::current_traitable_proc();

    auto flags = parent->flags() & ~ON_GRAPH;
    switch(flags) {
        case PLAIN:                 return new IdBuilder(obj, parent);
        case DEBUG:                 return new IdBuilderNoConvertDebug(obj, parent);
        case CONVERT_VALUES:        return new IdBuilderConvertNoDebug(obj, parent);
        case CONVERT_VALUES|DEBUG:  return new IdBuilderConvertDebug(obj, parent);

        default:
            assert(false);
            return nullptr;
    }
}

IdBuilder::IdBuilder(BTraitable *obj, BTraitableProcessor *parent) : m_obj(obj), m_parent_proc(parent) {
    use_own_cache(new IdBuilderCache(obj));
}

void IdBuilder::check_object(BTraitable *obj, BTrait* trait, const char* method) {
    if (obj != m_obj)   // not my object!
        throw py::type_error(py::str("While constructing {} - trying to {} trait {} on a different object")
        .format(m_obj->class_name(), method, trait->name()));
}

py::object IdBuilder::set_trait_value(BTraitable* obj, BTrait* trait, const py::object& value) {
    check_object(obj, trait, "set");
    return BTraitableProcessor::set_trait_value(obj, trait, value);
}

py::object IdBuilder::set_trait_value(BTraitable* obj, BTrait* trait, const py::object& value, const py::args& args) {
    check_object(obj, trait, "set");
    return BTraitableProcessor::set_trait_value(obj, trait, value, args);
}

void IdBuilder::invalidate_trait_value(BTraitable* obj, BTrait* trait) {
    check_object(obj, trait, "invalidate");
    throw py::type_error(py::str("invalidating value is not allowed while constructing an object: {}.{}")
    .format(m_obj->class_name()));
}

void IdBuilder::invalidate_trait_value(BTraitable* obj, BTrait* trait, const py::args& args) {
    invalidate_trait_value(obj, trait);
}

py::object IdBuilder::get_trait_value(BTraitable* obj, BTrait* trait) {
    if (obj != m_obj) {  // not my object, use the parent proc
        BTraitableProcessor::Use use(m_parent_proc);
        return m_parent_proc->get_trait_value(obj, trait);
    }

    return trait->proc()->get_value_off_graph(this, obj, trait);
}

py::object IdBuilder::get_trait_value(BTraitable* obj, BTrait* trait, const py::args& args) {
    if (obj != m_obj) {  // not my object, use the parent proc
        BTraitableProcessor::Use use(m_parent_proc);
        return m_parent_proc->get_trait_value(obj, trait, args);
    }

    return trait->proc()->get_value_off_graph(this, obj, trait, args);
}

py::object IdBuilder::adjust_set_value(BTraitable* obj, BTrait* trait, const py::object& value) {
    return value;
}

py::object IdBuilder::raw_set_trait_value(BTraitable* obj, BTrait* trait, const py::object& value) {
    check_object(obj, trait, "raw_set");
    if (!trait->flags_on(BTraitFlags::ID))  // only ID traits may be raw set (calling setters are allowed for all traits)
        throw py::type_error(py::str("{}.{} - only ID traits may be raw_set while constructing an object")
        .format(obj->class_name(), trait->name()));

    return trait->proc()->raw_set_value_off_graph(this, obj, trait, value);
}

py::object IdBuilder::raw_set_trait_value(BTraitable* obj, BTrait* trait, const py::object& value, const py::args& args) {
    check_object(obj, trait, "raw_set");
    if (!trait->flags_on(BTraitFlags::ID))  // only ID traits may be raw set (calling setters are allowed for all traits)
        throw py::type_error(py::str("{}.{} - only ID traits may be raw_set while constructing an object")
        .format(obj->class_name(), trait->name()));

    throw py::type_error(py::str("{}.{} - setting ID trait with args is not allowed").format(obj->class_name(), trait->name()));
}

py::object IdBuilderNoConvertDebug::adjust_set_value(BTraitable* obj, BTrait* trait, const py::object& value) {
    check_value(obj, trait, value);
    return value;
}

py::object IdBuilderConvertNoDebug::adjust_set_value(BTraitable* obj, BTrait* trait, const py::object& value) {
    return obj->from_any(trait, value);
}

py::object IdBuilderConvertDebug::adjust_set_value(BTraitable* obj, BTrait* trait, const py::object& value) {
    auto converted_value = obj->from_any(trait, value);
    check_value(obj, trait, converted_value);
    return converted_value;
}

