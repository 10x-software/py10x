import re
import secrets
import string
import subprocess
from getpass import getpass

import keyring
import requests
from core_10x.global_cache import cache
from core_10x.rc import RC
from core_10x.ts_store import TsCollection, TsDuplicateKeyError, TsStore

from infra_10x.mongodb_store import MongoStore


@cache
def create_xx_role(store):
    db = store.client.admin
    if db.command('rolesInfo', 'xxUser')['roles']:
        db.command('dropRole', 'xxUser')
    db.command(
        'createRole',
        'xxUser',
        privileges=[
            {
                'resource': {'anyResource': True},
                'actions': [
                    'find',
                    'insert',
                    'update',
                    'remove',  # read/write
                    'createIndex',
                    'createCollection',  # index + collection create
                    'dropCollection',
                ],
            }
        ],
        roles=[],
    )


def drop_xx_user(store: MongoStore, username: str) -> None:
    db = store.client['admin']
    if db.command('usersInfo', username)['users']:
        db.command('dropUser', username)


def create_xx_user(store: MongoStore, username: str, password: str) -> None:
    create_xx_role(store)
    drop_xx_user(store, username)
    store.client['admin'].command('createUser', username, pwd=password, roles=['xxUser'])
    keyring.set_password('xxuser', username, password)


def create_xx_admin(store: MongoStore, username: str, password: str) -> None:
    username = f'{username}-admin'
    if username == store.auth_user():
        raise ValueError('cannot create self!')
    drop_xx_user(store, username)
    store.client['admin'].command('createUser', username, pwd=password, roles=['userAdminAnyDatabase', 'userAdminAnyDatabase'])
    keyring.set_password('xxadmin', username, password)


def copy_collection(from_coll: TsCollection, to_coll: TsCollection, overwrite=False) -> RC:
    rc = RC(True)
    for doc in from_coll.find():
        try:
            if not to_coll.save_new(doc, overwrite=overwrite):
                rc.add_error(f'Failed to save {doc.get[to_coll.s_id_tag]}')
        except TsDuplicateKeyError:
            if overwrite:
                raise  # -- we do not expect an exception in case of overwrite, so raise
    return rc


def copy_store(from_store: TsStore, to_store: TsStore, overwrite=False) -> RC:
    rc = RC(True)
    for collection_name in from_store.collection_names():
        from_coll = from_store.collection(collection_name)
        to_coll = to_store.collection(collection_name)
        rc += copy_collection(from_coll, to_coll, overwrite=overwrite)
    return rc


def infer_username():
    return requests.get('https://api.github.com/user', headers={'Authorization': f'token {get_git_token()}'}).json()['login']


@cache
def get_git_token():
    return subprocess.getoutput("git credential fill <<< 'protocol=https\nhost=github.com\n' | grep password | cut -d= -f2")


@cache
def get_git_org():
    return re.search(r'github\.com[/:]([\w\-\.]+)/', subprocess.check_output(['git', 'remote', 'get-url', 'origin'], text=True).strip()).group(1)


@cache
def all_git_users():
    return [
        user['login']
        for user in requests.get(f'https://api.github.com/orgs/{get_git_org()}/members', headers={'Authorization': f'token {get_git_token()}'}).json()
    ]


def get_credentials(service, hostname):
    if hostname == 'localhost':
        return '', ''
    username = infer_username() or input('Username:')
    if service == 'xxadmin':
        username = f'{username}-admin'
    password = keyring.get_password(service, username)
    if not password:
        password = getpass(f"{username}'s password for `{service}`:")
        keyring.set_password(service, username, password)
    return username, password


def tsstore(hostname: str, dbname: str, store_cls: type[TsStore]) -> TsStore:
    username, password = get_credentials('xxadmin' if dbname == 'admin' else 'xxuser', hostname)
    return store_cls.instance(hostname=hostname, dbname=dbname, username=username, password=password)


def copy_db(from_host: str, to_host: str, dbname: str, store_cls: type[TsStore], overwrite=False) -> RC:
    return copy_store(tsstore(from_host, dbname, store_cls), tsstore(to_host, dbname, store_cls), overwrite=overwrite)


def new_password():
    return ''.join(secrets.choice(string.ascii_letters + string.digits + '!@#$%^&*') for _ in range(32))


def create_users():
    store: MongoStore = tsstore(host, 'admin', MongoStore)
    for user in all_git_users():
        drop_xx_user(store, f'{user}_admin')
        if user != infer_username():
            create_xx_admin(store, user, new_password())
        create_xx_user(store, user, new_password())


if __name__ == '__main__':
    host = 'mongo10x.eastus2.cloudapp.azure.com'
    # create_users()

    copy_db(from_host='localhost', to_host=host, dbname='mkt_data', store_cls=MongoStore, overwrite=True).throw()
