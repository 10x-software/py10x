//
// Created by AMD on 2/9/2025.
//

#include "mongo_collection_helper.h"

void MongoCollectionHelper::prepare_filter_and_pipeline(py::dict& serialized_traitable, py::dict& filter, py::list& pipeline) {
    auto rev_tag = NUCLEUS_REV_TAG;
    auto id_tag = "_id";

    auto revision = serialized_traitable.attr("pop")(rev_tag);
    auto rev = revision.cast<int>();
    if (rev <= 0)
        throw py::value_error(py::str("Revision must be >= 1: {}; serialized traitable:\n").format(revision, serialized_traitable));

    auto id_value = serialized_traitable.attr("pop")(id_tag);

    filter[id_tag] = id_value;
    filter[rev_tag] = revision;

    py::list rev_parts;
    for (auto item : serialized_traitable) {
        py::dict lit_val;           lit_val["$literal"] = item.second;
        py::list named_lit_val;     named_lit_val.append(py::str("$") + item.first);
                                    named_lit_val.append(lit_val);
        py::dict eq_ed;             eq_ed["$eq"] = named_lit_val;
        rev_parts.append(eq_ed);
    }
    py::dict rev_condition;         rev_condition["$and"] = rev_parts;

    py::list conditions;
    conditions.append(rev_condition);
    conditions.append(revision);
    conditions.append(py::int_(rev + 1));

    py::dict update_revision;
    update_revision["$cond"] = conditions;

    py::dict new_root_items;
    new_root_items[id_tag] = id_value;
    new_root_items[rev_tag] = update_revision;

    py::dict new_root;
    new_root["newRoot"] = new_root_items;

    py::dict replace_root;
    replace_root["$replaceRoot"] = new_root;

    pipeline.append(replace_root);

    for (auto item : serialized_traitable) {
        py::dict set_field_items;
        set_field_items["field"] = item.first;
        set_field_items["input"] = py::str("$$ROOT");
        py::dict value;
        value["$literal"] = item.second;
        set_field_items["value"] = value;

        py::dict set_field;
        set_field["$setField"] = set_field_items;

        py::dict replace_with;
        replace_with["$replaceWith"] = set_field;

        pipeline.append(replace_with);
    }
}