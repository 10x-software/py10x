//
// Created by AMD on 2/4/2025.
//

#include <bsoncxx/builder/basic/document.hpp>

#include "mongo_db_driver.h"

MongoDbDriver MongoDbDriver::Mongo;

using namespace mongocxx;
using namespace bsoncxx::types;
using namespace bsoncxx::builder::basic;

//==== Supported types: bool, int, float, str, datetime, tuple, list, dict
document dict_to_bson_doc(const py::dict& data);   // fwd-decl

bson_value::value to_bson(const py::handle& handle) {
    auto value = py::reinterpret_borrow<py::object>(handle);

    if (py::isinstance<py::bool_>(value))
        return {value.cast<bool>()};

    if (py::isinstance<py::int_>(value))
        return {static_cast<int64_t>(value.cast<int>())};

    if (py::isinstance<py::float_>(value))
        return {value.cast<double>()};

    if (py::isinstance<py::str>(value))
        return {value.cast<std::string>()};

    if (PyLinkage::is_instance(value, "datetime", "datetime")) {
        try {
            auto timestamp = value.attr("timestamp")().cast<double>();  // get seconds
            auto millis = static_cast<int64_t>(timestamp * 1000);              // convert to milliseconds
            return {b_date{std::chrono::milliseconds(millis)}};

        } catch (const py::cast_error&) {
            throw py::value_error(py::str("Conversion to BSON failed for datetime = {}").format(value));
        }
    }

    if (py::isinstance<py::list>(value) || py::isinstance<py::tuple>(value)) {
        bsoncxx::builder::basic::array bson_array;
        //for (const auto& item : value.cast<py::list>()) {
        for (const auto& item : value)
            bson_array.append(to_bson(item));

        return {bson_array.extract()};
    }

    if (py::isinstance<py::dict>(value)) {
        auto bson_doc = dict_to_bson_doc(value.cast<py::dict>());
        return {bson_doc.extract()};
    }

    throw py::value_error(py::str("Conversion to BSON: unsupported type {}").format(value));
}

document dict_to_bson_doc(const py::dict& data) {
    bsoncxx::builder::basic::document bson_doc;
    for (auto item : data) {
        auto sub_key = item.first.cast<std::string>();
        bson_doc.append(kvp(sub_key, to_bson(item.second)));
    }
    return bson_doc;
}

int MongoDbDriver::save_via_update_one(mongocxx::collection& coll, py::dict& serialized_data) {
    if (!serialized_data.contains(ID_TAG) || !serialized_data.contains(REV_TAG))
        throw py::value_error(
                py::str("Missing required fields: '{}' or '{}' in '{}'").format(ID_TAG, REV_TAG, serialized_data));

    //-- Extract `_id` and `_rev`
    auto doc_id = serialized_data[ID_TAG].cast<std::string>();
    auto cur_revision = serialized_data[REV_TAG].cast<int>();
    if (cur_revision < 0)
        throw py::value_error(py::str("{} = {}, but must be >= 0\n{}").format(REV_TAG, cur_revision, serialized_data));

    if (cur_revision == 0) {    // new object
        serialized_data[REV_TAG] = 1;
        auto bson_doc = dict_to_bson_doc(serialized_data);
        auto res = coll.insert_one(bson_doc.view());
        return res ? 1 : -1;
    }

    //---- This is an existing object - update it

    PyDict_DelItemString(serialized_data.ptr(), ID_TAG);        // get rid of _id
    PyDict_DelItemString(serialized_data.ptr(), REV_TAG);       // and _rev
    auto the_doc = dict_to_bson_doc(serialized_data);

    auto filter = make_document(
        kvp(ID_TAG, doc_id),
        kvp(REV_TAG, cur_revision)
    );

    //-- build a _rev condition

    bsoncxx::builder::basic::array conditions;
    for (auto doc_elem : the_doc.extract().view()) {
        auto name = doc_elem.key();
        auto value = doc_elem.get_value();
        conditions.append(
            make_document(kvp("$eq", make_array("$" + std::string(name), make_document(kvp("$literal", value)))))
        );
    }
    auto rev_condition = make_document(kvp("$and", conditions));

    auto update_revision = make_document(
        kvp(
            "$cond",
            make_array(
                rev_condition,      // if each field is equal to is prev value
                cur_revision,       //      then, keep the revision as is
                cur_revision+1      //      else, increment it
            )
        )
    );

   //-- build cmds

    pipeline cmds;
    cmds.add_fields(
        make_document(kvp("$replaceRoot", make_document(kvp("newRoot", make_document(kvp(ID_TAG, doc_id), kvp(REV_TAG, update_revision))))))
    );
    for (auto doc_elem : the_doc.extract().view()) {
        auto name = doc_elem.key();
        auto value = doc_elem.get_value();
        cmds.add_fields(
            make_document(
                kvp("$replaceWith",
                    make_document(
                        kvp("$setField",
                            make_document(
                                kvp("field", name),
                                kvp("input", "$$ROOT"),
                                kvp("value", make_document(kvp("$literal", value)))
                            )
                        )
                    )
                )
            )
        );
    }

    //auto update_doc = make_document(kvp("$set", ))
    auto res = coll.update_one(filter.view(), cmds);
    if (!res)
        return -1;

    if (res->matched_count() == 0) {    //-- e.g., restore from deleted
        the_doc.append(kvp(ID_TAG, doc_id));
        the_doc.append(kvp(REV_TAG, cur_revision));

        auto res2 = coll.insert_one(the_doc.view());
        return res2 ? cur_revision : -1;
    }

    if (res->matched_count() != 1)
        return -1;

    return res->modified_count() != 1 ? cur_revision : cur_revision+1;
}

