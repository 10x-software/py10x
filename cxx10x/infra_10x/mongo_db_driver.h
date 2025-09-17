//
// Created by AMD on 2/4/2025.
//
#pragma once

#include <mongocxx/client.hpp>
#include <mongocxx/instance.hpp>

#include "py_linkage.h"

class MongoDbDriver {
    mongocxx::instance  m_instance{};

public:
    inline static const char    ID_TAG[]      = "_id";
    inline static const char    REV_TAG[]     = "_rev";

    static MongoDbDriver Mongo;

    static mongocxx::client *connect(const std::string& host_name = "localhost") {
        return new mongocxx::client{mongocxx::uri{std::string("mongodb://") + host_name + ":27017"}};
    }

    static mongocxx::collection *collection(const mongocxx::client& client, const std::string& db_name, const std::string& coll_name) {
        mongocxx::database db = client[db_name];
        return new mongocxx::collection( db[coll_name] );
    }

    static int save_via_update_one(mongocxx::collection& coll, py::dict& serialized_data);
};

//bsoncxx::document::value doc = bsoncxx::builder::basic::make_document(
//        bsoncxx::builder::basic::kvp("name", "Alice"),
//        bsoncxx::builder::basic::kvp("age", 30),
//        bsoncxx::builder::basic::kvp("city", "New York")
//);
//
//coll.insert_one(doc.view());
//std::cout << "Inserted a document!" << std::endl;
//
//// Find a document
//auto maybe_result = coll.find_one(bsoncxx::builder::basic::make_document(
//        bsoncxx::builder::basic::kvp("name", "Alice")
//));
//
//if (maybe_result) {
//std::cout << "Found document: " << bsoncxx::to_json(maybe_result->view()) << std::endl;
//} else {
//std::cout << "No document found!" << std::endl;
//}
//
//return 0;