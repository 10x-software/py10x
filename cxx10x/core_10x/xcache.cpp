//
// Created by AMD on 3/7/2025.
//

#include "xcache.h"

#include <algorithm>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include "btraitable.h"

XCache* XCache::s_default = new XCache();
std::uint64_t XCache::s_next_generation = 0;

XCache::XCache(XCache* parent)
    : m_parent(parent)
    , m_generation(++s_next_generation)
{}

XCache *XCache::find_origin_cache(const TID &tid) {
    auto parent = this;
    while(parent) {
        if (parent->find_object_cache(tid))
            return parent;
        parent = parent->m_parent;
    }
    return nullptr;
}

bool XCache::is_descendent_of_origin(const BTraitable* obj) const {
    for (auto parent = this; parent; parent = parent->m_parent)
        if (obj->origin_cache_is(parent))
            return true;
    return false;
}

py::set XCache::object_ids_by_class(const BTraitableClass* cls) const {
    auto it = m_ids_by_class.find(cls);
    py::set result;
    if (it != m_ids_by_class.end())
        result = it->second;

    if (m_parent) {
        auto p_result = m_parent->object_ids_by_class(cls);
        result.attr("update")(p_result);
    }
    return result;
}

ObjectCache * XCache::find_or_create_object_cache(BTraitable *obj) {
    if (!is_descendent_of_origin(obj))
        throw obj->runtime_error("not usable - origin cache is not reachable");

    obj->lazy_load_if_needed();

    return _find_or_create_object_cache(obj->tid());
}

BasicNode* XCache::find_or_create_node(BTraitable *obj, const BTrait* trait, int node_type, const bool import_from_parents) {
    const auto oc = find_or_create_object_cache(obj);
    auto node = oc->find_node(trait);
    if (!node) {
        node = trait->create_node(node_type);
        oc->insert_node(trait, node);

        if (!import_from_parents)
            return node;

        const auto parent_node = find_set_or_invalid_node_in_parents(obj->tid(), trait);
        if (!parent_node || !parent_node->is_valid())
            return node;

        node->set_imported(trait->shallow_copy(parent_node->value()));     //-- this cache's own object, not the parent's
    }
    return node;
}

BasicNode* XCache::find_or_create_node(BTraitable *obj, const BTrait* trait, int node_type, const py::args& args, const bool import_from_parents) {
    const auto oc = find_or_create_object_cache(obj);
    auto node = oc->find_node(trait, args);
    if (!node) {
        node = trait->create_node(node_type);
        oc->insert_node(trait, node, args);

        if (!import_from_parents)
            return node;

        const auto parent_node = find_set_or_invalid_node_in_parents(obj->tid(), trait, args);
        if (!parent_node || !parent_node->is_valid())
            return node;

        node->set_imported(trait->shallow_copy(parent_node->value()));     //-- this cache's own object, not the parent's
    }
    return node;
}

void XCache::_export_invalidation(const TID &tid, ObjectCache* dst_oc, const BTrait* trait) const{
    auto dst_node = dst_oc->find_node(trait);

    if (!dst_node) {
        auto parent_node = m_parent->find_set_or_invalid_node_in_parents(tid, trait);
        if (parent_node && parent_node->is_valid())
            dst_node = dst_oc->find_or_create_node(trait, m_parent->default_node_type());
    }

    if (!dst_node)
        return;

    dst_node->invalidate();
    dst_node->set_invalidated(true);
}


void XCache::_export_invalidation(const TID &tid, ObjectCache* dst_oc, const BTrait* trait, const py::args& args) const {
    auto dst_node = dst_oc->find_node(trait, args);

    if (!dst_node) {
        auto parent_node = m_parent->find_set_or_invalid_node_in_parents(tid, trait, args);
        if (parent_node && parent_node->is_valid())
            dst_node = dst_oc->find_or_create_node(trait, m_parent->default_node_type(), args);
    }

    if (!dst_node)
        return;

    dst_node->invalidate();
    dst_node->set_invalidated(true);
}

void XCache::export_nodes() const {
    if (!m_parent)
        throw py::value_error("Cannot export_nodes from a root cache (no parent)");

    auto dst_node_type = m_parent->default_node_type();
    for (const auto& oc_item : m_data) {
        const auto& tid = oc_item.first;
        auto oc = oc_item.second;

        auto dst_oc = m_parent->_find_or_create_object_cache(tid);
        //-- argsless nodes
        for (auto item : oc->argless_nodes()) {
            auto const trait = item.first;
            auto const node = item.second;
            if (node->node_type() != NODE_TYPE::BASIC_GRAPH)
                continue;

            if (node->is_set())
                dst_oc->find_or_create_node(trait, dst_node_type)->set(node->value());
            else if (node->is_invalidated())
                _export_invalidation(tid, dst_oc, trait);
        }

        //-- nodes with args
        for (auto item : oc->nodes_with_args()) {
            auto trait = item.first;
            for (const auto& i: *item.second) {
                auto args = i.first;
                auto node = i.second;
                if (node->node_type() != NODE_TYPE::BASIC_GRAPH)
                    continue;

                if (node->is_set())
                    dst_oc->find_or_create_node(trait, dst_node_type, args)->set(node->value());
                else if (node->is_invalidated())
                    _export_invalidation(tid, dst_oc, trait, args);
            }
        }
    }
}

//----
//  For a given obj and trait (e.g., for portfolio.price node), find dependencies on all the instances of
//  subclasses of each target class in inputs_spec, for that class's given trait names (e.g.,
//  {MktQuotable: ('quote',), ...}). Walks m_ids_by_class exactly once, checking every cached class against
//  every inputs_spec entry -- cheaper than walking the (potentially large) cache once per entry.
//  Returns: { cls: { id: [(trait, value), ...], ... }, ... }
//----
py::dict XCache::find_dependencies(BTraitable* obj, const BTrait* trait, const py::dict& inputs_spec) const {
    py::dict results;
    if (default_node_type() < NODE_TYPE::BASIC_GRAPH)
        return results;

    if (inputs_spec.empty())
        return results;

    auto parent_node = find_node(obj->tid(), trait);
    if (!parent_node)
        return results;

    auto results_get = results.attr("get");
    for (const auto& [cls, ids] : m_ids_by_class) {
        auto py_cls = cls->py_class();

        std::vector<BTrait*> traits;
        for (const auto& [target_class, trait_names] : inputs_spec) {
            if (!PyLinkage::issubclass(py_cls, py::reinterpret_borrow<py::object>(target_class)))
                continue;
            for (auto name : trait_names) {
                auto t = cls->find_trait(name.cast<py::object>());
                if (t && std::find(traits.begin(), traits.end(), t) == traits.end())
                    traits.push_back(t);
            }
        }
        if (traits.empty())
            continue;

        for (const auto& id : ids) {
            auto child_id = id.cast<py::object>();
            auto tid = TID(cls, child_id);
            auto oc = find_object_cache(tid);
            assert(oc);
            for (auto t : traits) {
                auto node = (BasicGraphNode*)oc->find_node(t);
                if (node and node->is_successor_of(parent_node)) {
                    auto objs_by_cls = results_get(py_cls);
                    if (objs_by_cls.is_none()) {
                        objs_by_cls = py::dict();
                        results[py_cls] = objs_by_cls;
                    }
                    py::object t_list = objs_by_cls.attr("get")(child_id);
                    if (t_list.is_none()) {
                        t_list = py::list();
                        objs_by_cls[child_id] = t_list;
                    }
                    t_list.attr("append")(py::make_tuple(t, node->value()));
                }
            }
        }
    }

    return results;
}

namespace {
    using TIDs = std::unordered_set<TID>;

    //-- a number, a string or a date can never be, or hold, an object: only these trait data types are worth a look
    bool may_hold_object(const py::object& data_type, const PyTypeObject* traitable_type) {
        const auto p = data_type.ptr();
        if (!PyType_Check(p) || p == reinterpret_cast<PyObject*>(&PyBaseObject_Type))
            return true;    //-- untyped: anything may be in there

        const auto type = reinterpret_cast<PyTypeObject*>(p);
        for (const auto holder : { traitable_type, const_cast<const PyTypeObject*>(&PyList_Type), const_cast<const PyTypeObject*>(&PyTuple_Type),
                                   const_cast<const PyTypeObject*>(&PyDict_Type), const_cast<const PyTypeObject*>(&PySet_Type), const_cast<const PyTypeObject*>(&PyFrozenSet_Type) })
            if (PyType_IsSubtype(type, const_cast<PyTypeObject*>(holder)))
                return true;
        return false;
    }

    //-- is one of the wanted objects this value, or an item of it? (a few levels deep, which also stops a container that holds itself)
    bool holds(PyObject* value, const TIDs& wanted, PyTypeObject* traitable_type, const int depth = 0) {
        const auto type = Py_TYPE(value);
        if (type == &PyFloat_Type || type == &PyLong_Type || type == &PyUnicode_Type || type == &PyBool_Type || value == Py_None)
            return false;   //-- the bulk of what a big list holds: no further checks

        if (PyObject_TypeCheck(value, traitable_type)) {
            const auto& tid = py::handle(value).cast<const BTraitable*>()->tid();
            return tid.is_valid() && wanted.contains(tid);
        }
        if (depth > 3)
            return false;

        if (PyList_Check(value)) {
            for (Py_ssize_t i = 0, n = PyList_GET_SIZE(value); i < n; ++i)
                if (holds(PyList_GET_ITEM(value, i), wanted, traitable_type, depth + 1))
                    return true;
        } else if (PyTuple_Check(value)) {
            for (Py_ssize_t i = 0, n = PyTuple_GET_SIZE(value); i < n; ++i)
                if (holds(PyTuple_GET_ITEM(value, i), wanted, traitable_type, depth + 1))
                    return true;
        } else if (PyDict_Check(value)) {
            PyObject* item;
            for (Py_ssize_t pos = 0; PyDict_Next(value, &pos, nullptr, &item); )
                if (holds(item, wanted, traitable_type, depth + 1))
                    return true;
        } else if (PyAnySet_Check(value)) {
            for (const auto& item : py::handle(value))
                if (holds(item.ptr(), wanted, traitable_type, depth + 1))
                    return true;
        }
        return false;
    }
}

py::list XCache::find_holders(const py::list& objs) const {
    TIDs wanted, found;
    for (const auto& obj : objs)
        if (const auto& tid = obj.cast<const BTraitable*>()->tid(); tid.is_valid())
            wanted.insert(tid.copy_valid());

    const auto traitable_type = reinterpret_cast<PyTypeObject*>(py::type::of<BTraitable>().ptr());
    std::unordered_map<const BTraitableClass*, std::vector<const BTrait*>> traits_by_class;    //-- per class: its stored traits that may hold an object
    const auto traits_of = [&](const BTraitableClass* cls) -> const std::vector<const BTrait*>& {
        auto [it, is_new] = traits_by_class.try_emplace(cls);
        if (is_new)
            for (const auto& trait_handle : cls->trait_dir() | std::views::values)
                if (const auto trait = trait_handle.cast<const BTrait*>(); !trait->flags_on(BTraitFlags::RUNTIME) && may_hold_object(trait->data_type(), traitable_type))
                    it->second.push_back(trait);
        return it->second;
    };

    for (bool more = !wanted.empty(); more; ) {     //-- again whenever an embedded holder joins the wanted: it has holders of its own
        more = false;
        for (const auto& [tid, oc] : m_data) {
            if (wanted.contains(tid) || found.contains(tid))
                continue;

            for (const auto trait : traits_of(tid.cls())) {
                const auto node = oc->find_node(trait);
                if (!node || !holds(node->value().ptr(), wanted, traitable_type))
                    continue;

                if (tid.cls()->is_embeddable()) {
                    wanted.insert(tid.copy_valid());
                    more = true;
                } else
                    found.insert(tid.copy_valid());
                break;
            }
        }
    }

    py::list result;
    for (const auto& tid : found)
        result.append(tid.cls()->py_class()(py::arg("_id") = tid.id()));
    return result;
}
