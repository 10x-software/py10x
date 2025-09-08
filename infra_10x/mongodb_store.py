from pymongo import MongoClient, ReturnDocument, errors
from pymongo.database import Database
from pymongo.collection import Collection

from infra_10x_i import MongoCollectionHelper

from core_10x.ts_store import TsCollection, TsStore, Iterable, f, standard_key
from core_10x.nucleus import Nucleus
from core_10x.global_cache import cache


class MongoCollection(TsCollection):
    s_id_tag = '_id'

    assert Nucleus.ID_TAG() == s_id_tag, f"Nucleus.ID_TAG() must be '{s_id_tag}'"

    def __init__(self, db, collection_name: str):
        self.coll: Collection = db[collection_name]

    def id_exists(self, id_value: str) -> bool:
        return self.coll.count_documents({self.s_id_tag: id_value}) > 0

    def find(self, query: f = None, _at_most: int = 0, _order: dict = None) -> Iterable:
        cursor = self.coll.find(query.prefix_notation()) if query else self.coll.find()
        if _order:
            cursor = cursor.sort(list(_order.items()))
        if _at_most:
            cursor = cursor.limit(_at_most)
        return cursor

    def count(self, query: f = None) -> int:
        return self.coll.count_documents(query.prefix_notation()) if query else self.coll.count_documents({})

    def save_new(self, serialized_traitable: dict) -> int:
        res = self.coll.insert_one(serialized_traitable)
        return 1 if res.acknowledged else 0

    def save(self, serialized_traitable: dict) -> int:
        rev_tag = Nucleus.REVISION_TAG()
        id_tag = self.s_id_tag

        revision = serialized_traitable.get(rev_tag, -1)
        assert revision >= 0, 'revision must be >= 0'

        if revision == 0:
            serialized_traitable[rev_tag] = 1
            return self.save_new(serialized_traitable)

        id_value = serialized_traitable.get(id_tag)

        filter = {}
        pipeline = []
        MongoCollectionHelper.prepare_filter_and_pipeline(serialized_traitable, filter, pipeline)
        #self.filter_and_pipeline(serialized_traitable, filter, pipeline)

        res = self.coll.update_one(filter, pipeline)
        if not res.acknowledged:
            return revision

        if not res.matched_count:  # -- e.g. restore from deleted
            raise AssertionError(f'{self.coll} {id_value} has been most probably inappropriately restored from deleted')

        if res.matched_count != 1:
            return revision

        return revision if res.modified_count != 1 else revision + 1

    @classmethod
    def filter_and_pipeline(cls, serialized_traitable, filter, pipeline):
        rev_tag = Nucleus.REVISION_TAG()
        id_tag = cls.s_id_tag
        for key in (rev_tag, id_tag):
            filter[key] = serialized_traitable.pop(key)

        rev_condition = {
            '$and': [ {'$eq': ['$' + name, {'$literal': value}] } for name, value in serialized_traitable.items() ]
        }

        update_revision = {
            '$cond': [
                rev_condition,  #-- if each field is equal to its prev value
                filter[rev_tag],       #       then, keep the revision as is
                filter[rev_tag] + 1    #       else, increment it
            ]
        }

        pipeline.append(
            {
                '$replaceRoot': {
                    'newRoot': {
                        id_tag:     filter[id_tag],
                        rev_tag:    update_revision,
                    }
                }
            }
        )

        pipeline.extend(
            {
                '$replaceWith': {
                    '$setField': dict(field = field, input = '$$ROOT', value = {'$literal': value})
                }
            }
            for field, value in serialized_traitable.items()
        )

    # #---- TODO: move to C++
    # def save(self, serialized_traitable: dict) -> int:
    #     """
    #     Updates (and inc _rev) only if at least one traits has been changed
    #     :returns new revision if successful, otherwise the old one
    #     """
    #
    #     rev_tag = Nucleus.REVISION_TAG
    #     id_tag = self.s_id_tag
    #
    #     revision = serialized_traitable.get(rev_tag, -1)
    #     assert revision >= 0, 'revision must be >= 0'
    #
    #     if revision == 0:
    #         return self.save_new(serialized_traitable)
    #
    #     id_value = serialized_traitable.get(id_tag)
    #     del serialized_traitable[id_tag]
    #     del serialized_traitable[rev_tag]
    #
    #     filter = {
    #         id_tag:     id_value,
    #         rev_tag:    revision,
    #     }
    #
    #     rev_condition = {
    #         '$and': [ {'$eq': ['$' + name, {'$literal': value}] } for name, value in serialized_traitable.items() ]
    #     }
    #
    #     update_revision = {
    #         '$cond': [
    #             rev_condition,  #-- if each field is equal to its prev value
    #             revision,       #       then, keep the revision as is
    #             revision + 1    #       else, increment it
    #         ]
    #     }
    #
    #     cmds = [
    #         {
    #             '$replaceRoot': {
    #                 'newRoot': {
    #                     id_tag:     id_value,
    #                     rev_tag:    update_revision,
    #                 }
    #             }
    #         }
    #     ]
    #
    #     cmds.extend(
    #         {
    #             '$replaceWith': {
    #                 '$setField': dict(field = field, input = '$$ROOT', value = {'$literal': value})
    #             }
    #         }
    #         for field, value in serialized_traitable.items()
    #     )
    #
    #     res = self.coll.update_one(filter, cmds)
    #     if not res.acknowledged:
    #         return revision
    #
    #     if not res.matched_count:  # -- e.g. restore from deleted
    #         raise AssertionError(f'{self.coll} {id_value} has been most probably inapropriately restored from deleted')
    #
    #     if res.matched_count != 1:
    #         return revision
    #
    #     return revision if res.modified_count != 1 else revision + 1


    def delete(self, id_value: str) -> bool:
        q = {self.s_id_tag: id_value}
        return self.coll.delete_one(q).acknowledged

    def create_index(self, name: str, trait_name: str, **index_args) -> str:
        index_info = self.coll.index_information()
        if name in index_info:
            return None

        return self.coll.create_index(trait_name, name = name, **index_args)

    def max(self, trait_name: str, filter: f = None) -> dict:
        if filter:
            cur = self.coll.find(filter.prefix_notation()).sort({trait_name: -1}).limit(1)
        else:
            cur = self.coll.find().sort({trait_name: -1}).limit(1)
        for data in cur:
            return data

        return None

    def min(self, trait_name: str, filter: f = None) -> dict:
        if filter:
            cur = self.coll.find(filter.prefix_notation()).sort({ trait_name: 1 }).limit(1)
        else:
            cur = self.coll.find().sort({ trait_name: 1 }).limit(1)
        for data in cur:
            return data

        return None

    def load(self, id_value: str) -> dict:
        for data in self.coll.find({self.s_id_tag: id_value}):
            return data

        return None


class MongoStore(TsStore, name = 'MONGO_DB'):
    ADMIN   = 'admin'

    s_instance_kwargs_map = dict(
        port    = ('port',                      27017),
        ssl     = ('ssl',                       False),
        sst     = ('serverSelectionTimeoutMS',  10000),
    )

    s_cached_connections = {}
    @classmethod
    def connect(cls, hostname: str, username: str, password: str, _cache = True, _throw = True, **kwargs) -> MongoClient:
        if _cache:
            connection_key = standard_key((hostname, username), kwargs)
            client = cls.s_cached_connections.get(connection_key)
            if client:
                return client

        client = MongoClient(hostname, username = username, password = password, **kwargs)
        try:
            client.server_info()
        except Exception:
            client.close()
            if _throw:
                raise
            return None

        if _cache:
            cls.s_cached_connections[connection_key] = client

        return client

    @classmethod
    def uncache_connection(cls, hostname: str, username: str, password: str, **kwargs):
        connection_key = standard_key((hostname, username), kwargs)
        client = cls.s_cached_connections.pop(connection_key, None)
        if client:
            client.close()

    @classmethod
    def new_instance(cls, hostname: str, dbname: str, username: str, password: str, **kwargs) -> TsStore:
        client = cls.connect(hostname, username, password, **kwargs)
        return cls(client, client[dbname], username)

    def __init__(self, client: MongoClient, db: Database, username: str):
        self.client = client
        self.db: Database = db
        self.username = username

    def collection_names(self, regexp: str = None) -> list:
        filter = dict(name = {'$regex': regexp}) if regexp else None
        return self.db.list_collection_names(filter = filter)

    def collection(self, collection_name: str) -> TsCollection:
        return MongoCollection(self.db, collection_name)

    def delete_collection(self, collection_name: str) -> bool:
        self.db.drop_collection(collection_name)
        return True

    @classmethod
    @cache
    def is_running_with_auth(cls, host_name: str) -> tuple:      #-- (is_running, with_auth)
        client = cls.connect(host_name, '', '', _cache = False, _throw = False)
        if not client:
            return (False, False)

        admin_db = client[cls.ADMIN]
        try:
            res = admin_db.command('getCmdLineOpts')
            auth = any(r == '--auth' for r in res['argv'][1:])
            return (True, auth)

        except errors.OperationFailure:     #-- auth is required
            return (True, True)

        finally:
            client.close()
