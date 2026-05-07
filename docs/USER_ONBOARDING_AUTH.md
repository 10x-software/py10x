# Onboarding a New User onto Authenticated Stores

Three-step procedure for granting a new user access to password-protected
resources managed by the platform:

1. **Admin → User**: admin creates a vault account for the user and passes the
   credentials out of band.
2. **User**: user self-registers on their own machine.
3. **Admin → Vault**: admin saves access credentials for any additional
   protected resources the user needs.

> **Admin bootstrap (one-time).**  Before managing credentials for others, an
> admin must themselves complete step 2 using a vault account pre-allocated by
> a sysadmin.  The very first admin in a fresh deployment follows the same
> process; the sysadmin creates the initial vault DB account using native
> MongoDB admin access.

## Information flow at a glance

```
Admin                                User
─────                                ────
  │                                    │
  │  (1)  vault login + password ────▶ │
  │       (out-of-band)                │
  │                                    │ (2) runs: xx-user-init
  │                                    │     - enters vault credentials
  │                                    │     - chooses a master password
  │                                    │
  │ ◀──── (3a) "my OS user name" ───── │
  │                                    │
  │  (3b) for each additional          │
  │       protected resource:          │
  │       runs xx-admin-save-user-credentials
  │                                    │
```

The only thing the user has to tell the admin is their **OS user name** (= the
name shown by `whoami`). Everything else is handled automatically.

## Step 1 — Admin creates a vault account for the new user

Using native MongoDB admin access (or the `MongodbAdmin` helper in `infra_10x`
for Mongo deployments), the admin creates a database account on the vault server
and, if needed, on any other Mongo servers the user will access.

For relational databases, use the native tooling for that database (e.g.
`CREATE ROLE … WITH LOGIN PASSWORD '…'` in PostgreSQL).

The admin transmits the **vault login** and **temporary password** to the user
out of band (password manager share, signed message, in person, etc.).

## Step 2 — User self-registers

The user runs, on their own machine:

```bash
export XX_MAIN_VAULT_URI='mongodb://vault.example.com:27018/_vault_'
xx-user-init
```

Prompts:

1. Vault login (defaults to the OS user name — press Enter to accept).
2. Temporary vault password received in step 1.
3. A personal master password (≥ 8 characters; must include a letter, a
   capital letter, and a digit; entered twice to confirm).

What happens behind the scenes:

- An RSA key pair is generated. The private key is encrypted with the master
  password and stored in the vault; the public key is stored in plain text.
- The master password and the vault login/password are saved to the OS keyring
  — they never leave the user's machine.
- Access credentials for the vault server are registered automatically, so any
  other database on the same server is accessible without additional admin steps.

After this, the user tells the admin their **OS user name** (output of
`whoami`). That is the only information that needs to flow back.

## Step 3 — Admin grants access to additional resources

For each additional protected resource (a different Mongo host, a relational
database, etc.), the admin runs on their own machine:

```bash
xx-admin-save-user-credentials
```

Prompts: user's OS user name, resource type, URI, login, password.

The command verifies the credentials against the live resource, then stores them
in the vault encrypted with the user's public key. **The admin never needs the
user's master password** — it stays on the user's machine only.

Resources on the same server as the vault do not require this step; they are
automatically covered by the registration in step 2.

## Verifying

Run `xx-user-status` at any time to check the setup:

```
$ xx-user-status

[1] Vault URI
  OK  mongodb://vault.example.com:27018/_vault_

[2] Master password (OS keyring)
  OK  found in OS keyring

[3] Vault login/password (OS keyring)
  OK  login = 'alice'

[4] Vault connection and user record
  OK  VaultUser found (user_id = 'alice')

[5] Resource accessors
  OK  TS_STORE  mongodb://vault.example.com:27018  (login: alice)
  OK  REL_DB    postgresql://pg.example.com:5432/analytics  (login: alice)

All checks passed.
```

Each registered resource accessor is test-connected, so any access or
credential problem shows up in step 5 with the relevant error message.

Once steps 1–3 are complete, the user can also connect to any registered
resource without supplying passwords in code — the platform resolves
credentials from the vault automatically:

```python
# Any database on the vault server — no credentials needed in code
with Traitable.store_from_uri('mongodb://vault.example.com:27018/main') as s:
    ...

# A relational database registered by the admin in step 3
with RelDb.instance_from_uri('postgresql://pg.example.com:5432/analytics') as db:
    ...
```

## Off-boarding

To revoke a user's access, remove or suspend their vault DB account (and any
other database accounts) using the respective database admin tooling. Their
entries in the vault can also be deleted directly.

## Developer references

- `core_10x/vault_utils.py` — `VaultUtils.user_init`,
  `VaultUtils.admin_save_user_credentials`
- `core_10x/traitable.py` — `VaultUser`, `VaultResourceAccessor`
- `core_10x/apps/user_init.py`, `core_10x/apps/user_status.py`,
  `core_10x/apps/admin_save_user_credentials.py`
  — entry-point wrappers (`xx-user-init`, `xx-user-status`,
  `xx-admin-save-user-credentials`)
- `core_10x/sec_keys.py` — OS-keyring and RSA key handling
- `core_10x/unit_tests/test_user_onboarding.py` — end-to-end test
- `infra_10x/mongodb_admin.py`, `infra_10x/mongodb_utils.py` — Mongo
  account/role helpers used in step 1
