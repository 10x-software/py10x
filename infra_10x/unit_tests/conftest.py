import pytest
from infra_10x.mongodb_store import MongoStore

MONGO_URL = 'mongodb://localhost:27017/'
# MONGO_URL="mongodb+srv://HOST/?authMechanism=MONGODB-X509&authSource=%24external&tls=true&tlsCertificateKeyFile=/path/to/client.pem"
TEST_DB = 'test_db'


@pytest.fixture(scope='module')
def ts_instance():
    instance = MongoStore.instance(hostname=MONGO_URL, dbname=TEST_DB)
    instance.username = 'test_user'
    return instance