from pymongo import MongoClient, errors
from pymongo.database import Database

from infra_10x.mongodb_store import MongoStore

class MongodbAdmin:
    def __init__(self, hostname: str, username: str, password: str):
        self.client = MongoStore.connect(hostname=hostname, username=username, password=password, _cache = False)
        self.db = self.client[MongoStore.ADMIN]
        self.hostname = hostname
        self.username = username

    def user_exists(self, username: str) -> bool:
        res = self.db.command('usersInfo', {'user': username, 'db': MongoStore.ADMIN})
        return bool(res.get('users'))

    def update_user(self, username: str, password: str, *role_names, keep_current_roles = True):
        create = not self.user_exists(username)
        if create:
            if not password:
                raise RuntimeError(f'User {username} does not exist and requires a non-empty password')

            cmd = dict(createUser = username, pwd = password, roles = [*role_names])

        else:
            if not role_names and keep_current_roles:
                role_names = self.user_role_names(username)

            cmd = dict(updateUser = username)
            if role_names:
                cmd.update(roles = [*role_names])
            if password:
                cmd.update(pwd = password)

        self.db.command(cmd)

    def change_own_password(self, password: str):
        self.db.command(dict(updateUser = self.username, pwd = password))
        self.client = MongoStore.connect(hostname=self.hostname, username=self.username, password=password, _cache = False)
        self.db = self.client[MongoStore.ADMIN]

        # # Discover which user/db you're authenticated as (handy to avoid hardcoding)
        # status = client.admin.command("connectionStatus", showPrivileges = False)
        # auth = status[ "authInfo" ][ "authenticatedUsers" ]
        # if not auth:
        #     raise RuntimeError("Not authenticated. Connect with your current username/password first.")
        #
        # username = auth[0]['user']
        # user_db = auth[0]['db']
        #
        # # Change your password (roles remain unchanged because we don't pass 'roles')
        # client[user_db].command("updateUser", username, pwd = "<NEW_STRONG_PASSWORD>")
        #
        # # Reconnect with the new password (recommended)
        # client = MongoClient(f"mongodb://{username}:<NEW_STRONG_PASSWORD>@localhost:27017/?authSource={user_db}")
        # client.admin.command("ping")
        # print("Password changed and re-authenticated successfully.")

    def update_role(self, role_name: str, **permissions_per_db):
        """
        :param role_name: e.g., 'VISITOR'
        :param permissions_per_db: a dict: each key is either a db name or db_name/collection_name, value is PERMISSION, e.g.
                { 'catalog': PERMISSION.READ_ONLY, 'logs/errors': PERMISSION.READ_WRITE }
        :return:
        """
        privileges = [
            dict(
                resource    = dict(db = resource_parts[0], collection = resource_parts[1] if len(resource_parts) == 2 else ''),
                actions     = permission
            ) for db_name, permission in permissions_per_db.items() if(resource_parts := db_name.split('/'))
        ]
        method = 'createRole' if not self.role_exists(role_name) else 'updateRole'
        self.db.command(method, role_name, privileges = privileges, roles = [])

    def all_user_names(self) -> list:
        listing = self.db.command('usersInfo')
        return [doc['user'] for doc in listing['users']] if listing['ok'] else []

    def all_role_names(self) -> list:
        listing = self.db.command('rolesInfo')
        return [doc['role'] for doc in listing['roles']] if listing['ok'] else []

    def role_exists(self, role_name: str) -> bool:
        res = self.db.command('rolesInfo', dict(role = role_name, db = MongoStore.ADMIN))
        return bool(res['roles'])

    def user_role_names(self, username: str ) -> list:
        res = self.db.command(dict(usersInfo = username))
        if not res:
            return []

        return [r['role'] for r in res['users'][0]['roles']]

    def delete_all_roles(self):
        db = self.db
        for role_name in self.all_role_names():
            db.command('dropRole', role_name)

    def delete_role(self, role_name: str):
        if self.role_exists(role_name):
            self.db.command('dropRole', role_name)

    def delete_all_users(self):
        db = self.db
        me = self.username
        for username in self.all_user_names():
            if username != me:
                db.command('dropUser', username)

    def delete_user(self, username: str):
        me = self.username
        if me != username:
            if self.user_exists(username):
                self.db.command('dropUser', username)


