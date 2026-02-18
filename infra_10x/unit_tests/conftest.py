from contextlib import nullcontext

import pytest

from infra_10x import MongoCollectionHelper
from infra_10x.mongodb_store import MongoStore
from infra_10x.testlib.mongo_collection_helper import MongoCollectionHelperStub

MONGO_URL = 'mongodb://localhost:27017/'
# Example with X509 auth (replace with your URI; do not commit real hostnames or paths):
# MONGO_URL="mongodb+srv://HOST/?authMechanism=MONGODB-X509&authSource=%24external&tls=true&tlsCertificateKeyFile=/path/to/client.pem"
TEST_DB = 'test_db'


@pytest.fixture(params=[True, False], ids=['cxx-helper', 'py-helper'])
def ts_instance(mocker,request):
    instance = MongoStore.instance(hostname=MONGO_URL, dbname=TEST_DB)
    instance.username = 'test_user'
    if not instance.supports_transactions():
        instance.transaction = lambda *args: nullcontext()
    if not request.param:
        # Intentionally materialize metaclass __annotations__ to simulate prior
        # access on pybind11_type and keep this path covered.
        _ = type(MongoCollectionHelper).__annotations__
        mock = mocker.patch('infra_10x.MongoCollectionHelper')
        mock.value = MongoCollectionHelperStub
    return instance
