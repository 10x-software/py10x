import pytest
from core_10x.testlib.ts_tests import TestTSStore, ts_setup  # noqa: F401
from infra_10x.mongodb_store import MongoStore

MONGO_URL = 'mongodb://localhost:27017/'
# MONGO_URL="mongodb+srv://dev.qbultu3.ts_storedb.net/?authMechanism=MONGODB-X509&authSource=%24external&tls=true&tlsCertificateKeyFile=%2FUsers%2Fiap%2FDownloads%2FX509-cert-590074097809994161.pem"
TEST_DB = 'test_db'


@pytest.fixture(scope='module')
def ts_instance():
    instance = MongoStore.instance(hostname=MONGO_URL, dbname=TEST_DB)
    instance.username = 'test_user'
    return instance
