import re
import secrets
import string
import subprocess
from getpass import getpass

import keyring
import requests
from core_10x.attic.backbone import AUTO_PASSWORD_LENGTH, USER_ROLE
from core_10x.global_cache import cache
from core_10x.rc import RC

from infra_10x.mongodb_admin import MongodbAdmin
from infra_10x.mongodb_store import MongoStore


@cache
def create_xx_role(admin: MongodbAdmin):
    admin.db.command(
        'updateRole' if admin.role_exists('xxUser') else 'createRole',
        'xxUser',
        privileges=[
            {
                'resource': {'anyResource': True},
                'actions': USER_ROLE.WORKER.value,
            }
        ],
        roles=[],
    )


def create_xx_user(admin: MongodbAdmin, xx_user: str, new_password: str) -> None:
    password = keyring.get_password('xxuser', xx_user) or new_password
    admin.update_user(xx_user, password, 'xxUser', keep_current_roles=False)
    if password == new_password:
        keyring.set_password('xxuser', xx_user, password)


def create_xx_admin(admin: MongodbAdmin, xx_admin: str, new_password: str) -> None:
    if xx_admin == admin.username:
        raise ValueError('cannot create self!')
    password = keyring.get_password('xxadmin', xx_admin) or new_password
    admin.update_user(xx_admin, password, 'userAdminAnyDatabase', 'readWriteAnyDatabase')
    if password == new_password:
        keyring.set_password('xxadmin', xx_admin, password)


def get_xx_admin(user: str):
    return f'{user}-admin'


@cache
def git_user():
    return requests.get('https://api.github.com/user', headers={'Authorization': f'token {git_token()}'}).json()['login'] or input('Username:')


@cache
def git_token():
    return subprocess.getoutput("git credential fill <<< 'protocol=https\nhost=github.com\n' | grep password | cut -d= -f2") or input('Token:')


@cache
def all_git_users():
    git_org = re.search(r'github\.com[/:]([\w\-\.]+)/', subprocess.check_output(['git', 'remote', 'get-url', 'origin'], text=True).strip()).group(1)
    return [
        user['login']
        for user in requests.get(f'https://api.github.com/orgs/{git_org}/members', headers={'Authorization': f'token {git_token()}'}).json()
    ]


def generate_password():
    return ''.join(secrets.choice(string.ascii_letters + string.digits + '!@#$%^&*') for _ in range(AUTO_PASSWORD_LENGTH))


def create_users(hostname):
    admin = MongodbAdmin(hostname=hostname, **get_credentials('xxadmin', hostname))
    create_xx_role(admin)
    for xx_user in all_git_users():
        xx_admin = get_xx_admin(xx_user)
        if xx_admin != admin.username:  # -- do not break current working account!
            create_xx_admin(admin, xx_admin, generate_password())
        create_xx_user(admin, xx_user, generate_password())


def clear_vault():
    for xx_user in all_git_users():
        if keyring.get_password('xxuser', xx_user):
            keyring.delete_password('xxuser', xx_user)
        if xx_user != git_user():  # -- do not break own admin account!
            xx_admin = get_xx_admin(xx_user)
            if keyring.get_password('xxadmin', xx_admin):
                keyring.delete_password('xxadmin', xx_admin)


def drop_users(hostname):
    admin = MongodbAdmin(hostname=hostname, **get_credentials('xxadmin', hostname))
    for xx_user in all_git_users():
        xx_admin = get_xx_admin(xx_user)
        if xx_admin != admin.username:  # -- do not break current working account!
            admin.delete_user(xx_admin)
        admin.delete_user(xx_user)


def get_credentials(service, hostname):
    if hostname == 'localhost':
        return dict(username='', password='')
    username = git_user()
    if service == 'xxadmin':
        username = get_xx_admin(username)
    password = keyring.get_password(service, username)
    if not password:
        password = getpass(f"{username}'s password for `{service}`:")
        keyring.set_password(service, username, password)
    return dict(username=username, password=password)


def copy_db(from_host: str, to_host: str, dbname: str, overwrite=False) -> RC:
    from_store = MongoStore.instance(hostname=from_host, dbname=dbname, **get_credentials('xxuser', from_host))
    to_store = MongoStore.instance(hostname=to_host, dbname=dbname, **get_credentials('xxuser', to_host))
    return from_store.copy_to(to_store, overwrite=overwrite)


if __name__ == '__main__':
    host = 'mongo10x.eastus2.cloudapp.azure.com'
    # drop_users(host)
    # clear_vault()
    # create_users(host)

    copy_db(from_host='localhost', to_host=host, dbname='mkt_data', overwrite=False).throw()
