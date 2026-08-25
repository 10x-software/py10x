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
xx-user-init            # same as: xx-user-init --new-user
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

## Same user, new machine

The `VaultUser` row and encrypted private key live in the shared vault; the
master password and vault login/password live only in each machine's OS
keyring. On a second machine, do **not** re-run first-time registration
(`--new-user` will refuse once the vault row exists). Instead:

```bash
export XX_MAIN_VAULT_URI='mongodb://vault.example.com:27018/_vault_'
xx-user-init --new-machine
```

Prompts:

1. Vault login and password (same credentials as on the first machine).
2. The **existing** master password (the one that encrypts the vault private
   key) — entered once; it is verified by decrypting that key.

This writes the master password and vault login/password into the local OS
keyring only. It does not rotate keys or rewrite the `VaultUser` row. Other
machines keep working with the same master password.

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

## Functional (unattended service) accounts

A functional account is the same `VaultUser` registration as above, run
non-interactively for a service instead of a person. Two things are
different from the human flow:

- **OS identity is not something you set up.** The `py10x-core` Docker image
  (`docker/Dockerfile`, `docker/entrypoint.sh`) ships a disposable placeholder
  OS account that gets renamed to `FUNCTIONAL_ACCOUNT_ID` at container start
  (`usermod -l`) — there is no OS account to create ahead of time. Pick a
  `user_id` starting with the `xx-` prefix (`EnvVars.functional_account_prefix`),
  e.g. `xx-myservice`; `VaultUser.is_functional_account` uses that prefix to
  distinguish it from a human login. The same rename applies to one-time
  registration (below), not just the running service.
- **The two secrets never live in a file on disk.**
  `core_10x.functional_account_keyring.FunctionalAccountKeyring` is
  deliberately in-memory-only — it reads a JSON manifest once (from
  `XX_SECRETS_DIR/keyring.json`, default `/var/run/secrets/xx-vault`) and
  never writes anything back, so the mounted secret remains the only durable
  copy. That's on purpose: it lets the manifest be delivered by a real secret
  store (Docker Swarm secret, Kubernetes Secret) that is itself tmpfs-backed
  in the container, so the master password is never written to a persistent
  disk anywhere in the pipeline.

### One-time: register the account and capture its secrets

A functional account is registered and delivered in one step, via
`xx-functional-account-init` (`core_10x/apps/functional_account_init.py`): it
runs `xx-user-init --functional-account` inside a disposable container, then
feeds the resulting manifest into `--command`, whatever creates the secret
in your target secret store. Registration prompts for the vault login and
password (same prompts the interactive flow uses — never a CLI arg or env
var, and never printed anywhere), generates a random master password
(nobody ever types a functional account's master password back in), and
delivers the manifest to `--command` over a transient named pipe, not a file
sitting readable on disk.

Image, vault URI, and Docker network mode are all auto-resolved — nothing to
plumb by hand for the common case:

```bash
xx-functional-account-init \
  --functional-account-id xx-myservice \
  --command "docker secret create {secret_name} -"
# you will be prompted to enter the vault account and password
```

`XX_MAIN_VAULT_URI` must already be set in your shell (same as any other
`xx-*` command) — it's forwarded into the container automatically, along
with `--network host` when the vault host is a loopback address. The account
id must carry the `xx-` prefix (`EnvVars.functional_account_prefix`) —
`xx-functional-account-init` refuses to run otherwise. If the
currently-installed `py10x-core` version has no matching published image
(e.g. a local, unreleased dev build), pass `--image-tag dev|pre|prod|<tag>`
explicitly; otherwise the image matching your installed version is found and
used automatically.

`--command` is required — there is no fallback that prints the manifest. Its
`{secret_name}` placeholder is substituted (`shlex.quote`d, so it can't
splinter into extra tokens even for an unusual account id) with a name
derived from the account id (`FunctionalAccountKeyring.secret_name`), e.g.
`xx-myservice-vault-keyring` — not something you type, so the name used to
create the secret always matches what your deployment manifest should
reference.

### Docker Swarm: the `--command` above, then deploy

That's the complete Swarm case already, above (`docker secret create
{secret_name} -`, run once — a single-node `docker swarm init` is enough, no
multi-host cluster required). Secret *names* share one cluster-wide namespace
(unlike Kubernetes Secret objects, which are namespaced), which is exactly
why the account id needs to be in the name — `target=` below decouples that
name from the filename the container actually sees. Then deploy the service
that consumes it — this part still runs as a real container, with a real
account rename via `docker/entrypoint.sh`:

```bash
docker service create \
  --name py10x-myservice \
  --secret source=xx-myservice-vault-keyring,target=keyring.json \
  -e FUNCTIONAL_ACCOUNT_ID=xx-myservice \
  -e XX_MAIN_VAULT_URI=postgresql://vault-host:5432/vaultdb \
  -e XX_SECRETS_DIR=/run/secrets \
  --network host \
  ghcr.io/10x-software/py10x-core:<version> \
  python3 your_app_entrypoint.py
```

`docker secret create ... -` reads the manifest from stdin — it's stored
encrypted in Swarm's raft log and mounted, per `target=`, as a tmpfs file at
`/run/secrets/keyring.json` *before* the container's entrypoint runs, so
there's no race with `FunctionalAccountKeyring`'s lazy first read.

### Kubernetes: swap the `--command`, then deploy

Same pattern, different `--command`, run with whatever `kubectl`/kubeconfig
you already have on your machine — same `xx-functional-account-init` step as above:
```
--command 'kubectl create secret generic {secret_name} --from-file=keyring.json=/dev/stdin'
```

A `Secret` mounted as a volume is tmpfs-backed by kubelet and, like Swarm,
mounted before any container in the pod starts — this is the deployment
target `XX_SECRETS_DIR`'s default (`/var/run/secrets/xx-vault`) was shaped
to match, so no override is needed:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: xx-myservice
spec:
  replicas: 1
  selector:
    matchLabels: {app: xx-myservice}
  template:
    metadata:
      labels: {app: xx-myservice}
    spec:
      securityContext:
        fsGroup: 10001   # matches the image's pinned appuser gid -- so it can read the vault-secret
      containers:
        - name: xx-myservice
          image: ghcr.io/10x-software/py10x-core:<version>
          command: ["python3", "your_app_entrypoint.py"]
          env:
            - name: FUNCTIONAL_ACCOUNT_ID
              value: xx-myservice
            - name: XX_MAIN_VAULT_URI
              value: postgresql://vault-host:5432/vaultdb
          volumeMounts:
            - name: vault-secret
              mountPath: /var/run/secrets/xx-vault
              readOnly: true
      volumes:
        - name: vault-secret
          secret:
            secretName: xx-myservice-vault-keyring
            defaultMode: 0440
```

### Subsequent restarts

`user_init` is a one-time step. On every later container start, the app's
first `keyring.get_password(...)` call resolves straight from the mounted
manifest — no need to re-run registration.

## Developer references

- `core_10x/vault_utils.py` — `VaultUtils.user_init`,
  `VaultUtils.admin_save_user_credentials`
- `core_10x/traitable.py` — `VaultUser`, `VaultResourceAccessor`
- `core_10x/apps/user_init.py`, `core_10x/apps/user_status.py`,
  `core_10x/apps/admin_save_user_credentials.py`
  — entry-point wrappers (`xx-user-init`, `xx-user-status`,
  `xx-admin-save-user-credentials`)
- `core_10x/sec_keys.py` — OS-keyring and RSA key handling
- `core_10x/unit_tests/test_user_onboarding.py` — end-to-end test (human flow)
- `infra_10x/mongodb_admin.py`, `infra_10x/mongodb_utils.py` — Mongo
  account/role helpers used in step 1
- `core_10x/functional_account_keyring.py` — `FunctionalAccountKeyring`,
  the in-memory-only `keyring` backend for functional accounts, and
  `FunctionalAccountKeyring.secret_name` (the naming convention)
- `core_10x/apps/user_init.py` — `UserInitCli`'s `--functional-account`
  / `--output-file` mode (non-interactive registration + manifest delivery)
- `core_10x/apps/functional_account_init.py` — `FunctionalAccountInitCli`
  (`xx-functional-account-init`), the automated Docker-wrapped provisioning
  command: runs registration inside a real container and pipes the manifest
  to a provisioning command outside it
- `docker/Dockerfile`, `docker/entrypoint.sh` — the container's OS-account
  rename (pinned `10001:10001` uid/gid) + keyring wiring
- `core_10x/unit_tests/test_functional_account_vault.py` — end-to-end test
  (functional-account flow, against a real authenticated Postgres)
- [`VAULT_SECURITY_DESIGN.md`](VAULT_SECURITY_DESIGN.md) — the security design behind this
  document's procedures: threat model, tradeoffs, comparisons to existing systems, deployment
  recommendations, and outstanding hardening items
