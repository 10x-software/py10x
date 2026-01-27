import keyring

from core_10x.ts_store import TsStore

db1 = TsStore.instance_from_uri('mongodb://localhost:27017/mkt_data')
print(db1.collection_names())

user = 'admin'
db2 = TsStore.instance_from_uri(f'mongodb://{user}:{keyring.get_password("mongodb_local", user)}@localhost:27018/test')
print(db2.collection_names())
