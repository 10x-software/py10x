# Vault Deployment and User Onboarding

Two-part guide for password-protected resources on the platform:

- **[Part I — Vault deployment](#part-i--vault-deployment)** (once per vault database):
  a database superuser installs collections, worker/admin roles, and the first
  vault admin.
- **[Part II — Per-user onboarding](#part-ii--per-user-onboarding)** (repeat for
  each person): confirm OS login, superuser issues a worker login, vault admin
  sends credentials, the user self-registers, then resource credentials are stored.

See [`VAULT_SECURITY_DESIGN.md`](VAULT_SECURITY_DESIGN.md) for the threat model
and operator mitigations.

---

## Part I — Vault deployment

**Who:** database superuser (MongoDB/PostgreSQL admin).  
**When:** once per vault database, before anyone is onboarded.

Do not use stock `xxUser` or `infra_10x.mongodb_utils.create_xx_user` on the
vault — that role is `anyResource` read/write.

### Deploy the vault

Set the vault URI and connect as a superuser. The command creates the
`VaultUser` / `VaultResourceAccessor` collections (and history), installs
`xxVaultWorker` / `xxVaultAdmin`, and applies Postgres RLS or Mongo custom
roles as appropriate.

```bash
export XX_MAIN_VAULT_URI='mongodb://vault.example.com:27018/_vault_'
xx-vault-setup-roles
```

The command prompts for the superuser password.

### Create the first vault admin

Vault admins can suspend users and grant resource credentials for others
(`xx-admin-save-user-credentials`). Issue at least one admin login — typically
named as that person's OS user (`whoami`), same rule as workers:

```bash
xx-vault-setup-roles --vault-admin bob
```

The command prompts for the superuser password and a password for
`bob`. That person completes [Part II step 3](#step-3--user-self-registers)
themselves before managing credentials for others.

---

## Part II — Per-user onboarding

**Prerequisite:** [Part I](#part-i--vault-deployment) is complete and the
acting vault admin has their own `--vault-admin` login and has run
`xx-user-init`.

Four-step procedure for each new user:

1. **OS login**: user communicates their OS login to the superuser (or the
   admin already knows it from a directory).
2. **Issue credentials**: superuser creates the worker login with that exact
   string; vault admin transmits login + password out of band.
3. **User**: user self-registers on their own machine (`xx-user-init`), then
   confirms registration (`xx-user-status` to vault admin).
4. **Credentials**: user saves own secrets (`xx-user-save-credentials`), or a
   vault admin grants a secret they hold (`xx-admin-save-user-credentials`).

> **Enterprise deployments.** In larger organizations the vault admin or DBA
> already knows each person's login from Active Directory, LDAP, or similar —
> step 1 is unnecessary. Automating `xx-vault-setup-roles --worker` from a
> directory feed, or binding vault authentication directly to directory
> credentials, is possible but out of scope for this document.

### Information flow at a glance

```
Vault admin / superuser              User
───────────────────────              ────
  │                                    │
  │                                    │ (1) runs: xx-user-status
  │ ◀──── OS login (out-of-band) ──────│     (or admin reads directory)
  │                                    │
  │  (2)  vault login + password ────▶ │  (superuser --worker with exact
  │       (out-of-band)                │   OS login; admin sends password)
  │                                    │
  │                                    │ (3) runs: xx-user-init
  │                                    │     - enters vault credentials
  │                                    │     - chooses a master password
  │                                    │
  │ ◀──── (3b) xx-user-status output ──│  (confirms registration succeeded)
  │       (out-of-band)                │
  │                                    │
  │                                    │ (4) xx-user-save-credentials
  │                                    │     (own secrets / tokens)
  │  (4)  optional: vault admin        │
  │       xx-admin-save-user-credentials
  │       (secret the admin holds)     │
  │                                    │
```

### Step 1 — Confirm OS login

The vault-DB login must equal the user's **OS login** — the name returned by
the kernel (`VaultUser.myname()`), not `$USER` or `$LOGNAME`. It may contain
characters such as ``\`` or ``@`` (for example ``CORP\alice`` or
``alice@corp.example``). The superuser must create the account with that
exact string.

On the user's machine, before any vault account exists (``XX_MAIN_VAULT_URI``
may or may not be set yet — only section ``[0]`` is needed for step 1):

```bash
xx-user-status
```

Example (no local keyring yet; exit code 1 is expected):

```
[0] OS login (vault account name)
  OK  OS login = 'CORP\\alice'
      Use this exact string for the vault-DB login (--worker).
      Send it to your DBA / vault admin if they do not already know it

[1] Vault URI
  OK  mongodb://vault.example.com:27018/_vault_

[2] Master password (OS keyring)
FAIL  not found in OS keyring — this machine is not set up for vault access
      hint: run: xx-user-init --new-user  (first machine) or ...

[3] Vault login/password (OS keyring)
FAIL  not found in OS keyring — this machine is not set up for vault access
      hint: run: xx-user-init --new-user  (first machine) or ...
```

Send the ``[0]`` line to the DBA or vault admin out of band if they do not
already know it from your corporate directory.

In larger organizations the admin typically already has the login from
directory services — this step can be skipped.

### Step 2 — Issue vault credentials to the user

Each new person or [functional account](#functional-unattended-service-accounts)
needs a vault-DB login named as their OS user (`whoami` for humans; `xx-`
prefix for services).

1. **Superuser** runs (once per account), using the **exact** OS login from
   step 1 (quote for the shell when it contains special characters):

```bash
xx-vault-setup-roles --worker 'CORP\alice'
```

The command prompts for the superuser password and a password for
the new login. For other (non-vault) databases the user will access, use native
tooling (`MongodbAdmin` / `CREATE ROLE`).

In a small team the superuser and vault admin may be the same person; in larger
deployments the vault admin requests this step from the DBA.

2. **Vault admin** transmits that login and its password out of band
   (password manager share, signed message, in person, etc.).

`xx-user-init` refuses a vault login that does not match the OS user on the
machine where it runs.

### Step 3 — User self-registers

The user runs, on their own machine:

```bash
export XX_MAIN_VAULT_URI='mongodb://vault.example.com:27018/_vault_'
xx-user-init            # same as: xx-user-init --new-user
```

Prompts:

1. Vault login — must match section `[0]` of `xx-user-status` (kernel OS login,
   not `$USER`). The `xx-user-init` prompt defaults to that name and refuses a
   mismatch.
2. Vault password received in step 2.
3. A personal master password (≥ 8 characters; must include a letter, a
   capital letter, and a digit; entered twice to confirm).

What happens behind the scenes:

- An RSA key pair is generated. The private key is encrypted with the master
  password and stored in the vault; the public key is stored in plain text.
- The master password and the vault login/password are saved to the OS keyring
  — they never leave the user's machine.
- Access credentials for the vault server are registered automatically, so any
  other database on the same server is accessible without additional admin steps.

After this, email the vault admin the full output of ``xx-user-status`` (out of
band, same channel as step 2). That confirms registration succeeded on the
user's machine before the admin grants further resources in step 4.

Example after successful ``xx-user-init`` (vault host RA only; step 4 not done
yet):

```
[0] OS login (vault account name)
  OK  OS login = 'CORP\\alice'
      ...

[1] Vault URI
  OK  mongodb://vault.example.com:27018/_vault_

[2] Master password (OS keyring)
  OK  found in OS keyring

[3] Vault login/password (OS keyring)
  OK  login = 'CORP\\alice'

[4] Vault connection and user record
  OK  user_id = 'CORP\\alice'

[5] Resource accessors
  OK  TS_STORE  mongodb://vault.example.com:27018  (login: CORP\alice)

All checks passed.
```

### Same user, new machine

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

### Step 4 — Resource credentials (user or vault admin)

The user can store a password they received out of band (from a resource
admin who is not the vault admin) or a token they generated themselves:

```bash
xx-user-save-credentials
```

Prompts: resource type, URI, resource login, password. The row is always
for the calling OS / vault user (`VaultUser.myname()`). Re-running for the
same URI rotates the stored secret. The command verifies the credentials
against the live resource, then encrypts to the caller's public key.

A vault admin can still grant a secret they hold for someone else:

```bash
xx-admin-save-user-credentials
```

Run this only after the user has confirmed registration (typically by sending
``xx-user-status`` output out of band — see step 3).

Prompts: the vault login issued in step 2, then the same resource fields.
The admin never needs the user's master password.

Resources on the same server as the vault do not require this step; they are
automatically covered by the registration in step 3.

### Verifying

Run ``xx-user-status`` at any time to check the setup. After step 4, section
``[5]`` should list every registered resource (example below includes a
relational DB granted by the vault admin):

```
$ xx-user-status

[0] OS login (vault account name)
  OK  OS login = 'CORP\\alice'
      Use this exact string for the vault-DB login (--worker).
      Send it to your DBA / vault admin if they do not already know it

[1] Vault URI
  OK  mongodb://vault.example.com:27018/_vault_

[2] Master password (OS keyring)
  OK  found in OS keyring

[3] Vault login/password (OS keyring)
  OK  login = 'CORP\\alice'

[4] Vault connection and user record
  OK  user_id = 'CORP\\alice'

[5] Resource accessors
  OK  TS_STORE  mongodb://vault.example.com:27018  (login: CORP\alice)
  OK  REL_DB    postgresql://pg.example.com:5432/analytics  (login: CORP\alice)

All checks passed.
```

Each registered resource accessor is test-connected, so any access or
credential problem shows up in step 5 with the relevant error message.

Once steps 1–4 are complete, the user can also connect to any registered
resource without supplying passwords in code — the platform resolves
credentials from the vault automatically:

```python
# Any database on the vault server — no credentials needed in code
with Traitable.store_from_uri('mongodb://vault.example.com:27018/main') as s:
    ...

# A relational database registered by the admin in step 4
with RelDb.instance_from_uri('postgresql://pg.example.com:5432/analytics') as db:
    ...
```

### Off-boarding

1. Set `VaultUser.suspended = True` (enforced at `sec_keys_get()`, new-machine
   re-init, `xx-user-save-credentials`, and `xx-admin-save-user-credentials`).
2. Revoke their vault-DB account and any other database accounts. Restart
   long-running processes that were already authenticated; they keep working
   until they exit. Revoking the DB account stops new vault connections.
3. Optionally delete their vault rows.

### Functional (unattended service) accounts

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

Issue the vault-DB login via [Part II step 2](#step-2--issue-vault-credentials-to-the-user)
(`xx-vault-setup-roles --worker xx-myservice`) before registration.

#### One-time: register the account and capture its secrets

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

#### Docker Swarm: the `--command` above, then deploy

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

#### Kubernetes: swap the `--command`, then deploy

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

#### Subsequent restarts

`user_init` is a one-time step. On every later container start, the app's
first `keyring.get_password(...)` call resolves straight from the mounted
manifest — no need to re-run registration.
