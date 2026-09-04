# Vault & Functional-Account Security — Design Document

Threat model for [`py10x-core`](../README.md)'s per-user credential vault. Complements
[`USER_ONBOARDING_AUTH.md`](USER_ONBOARDING_AUTH.md) (the procedure) and
[`SECURITY.md`](../SECURITY.md) (disclosure). Operator-facing sketch:
[`GETTING_STARTED.md` § Vault](../GETTING_STARTED.md#vault-and-credential-management).

## 1. What this is

A self-hosted, per-user asymmetric credential store. Each human
or functional account has an RSA-2048 keypair. The public key is stored in plain text.
The private key is wrapped with a key derived from a locally-held master password
(scrypt, then PKCS8 AES). There is no vault server: the application is the client, and the
master password is used only on the machine that holds it. Resource credentials
(database logins, API keys) are RSA-OAEP-SHA256-encrypted to that public key and stored
as `VaultResourceAccessor` rows.

This is not a general secrets-management platform (no dynamic/leased secrets, no
policy-as-code, no PKI issuance).

**Implementation in §3 is on by default** — no extra build, flag, or install step when
you use the vault CLIs.
**Operator mitigations in §3 are not** — they require IAM, network, MDM, or database
privilege configuration beyond that coded floor. **§5** is what is not in this release:
an org-defined password policy beyond the coded floor, master-password / keypair
rotation, and Mongo per-user accessor collections.

## 2. Assets, adversaries, assumptions, scope

**Assets.** Master password; wrapped private key and per-user salt; resource ciphertext;
plaintext metadata (`VaultUser.public_key`, `VaultResourceAccessor.login` / `resource_uri`
/ `username`); OS keyring cache; functional-account FIFO/manifest; history `_who`/`_at`.

**Adversaries.** Anyone who obtains a copy of the vault store (backup leak, stolen DB
credentials, insider); anyone with code execution on a developer's machine or a
functional-account container; anyone who can create DB roles matching a victim OS
user; a Mongo worker who can `INSERT` a `VaultUser` for another `user_id`; anyone
with `UPDATE` on live `VaultUser` / history rows.

**Assumptions.**
- Vault-DB logins are admin-issued, one per person or service, and **must equal**
  the OS `user_id` (`xx-user-init` refuses otherwise). Ordinary application
  logins cannot create DB roles (`CREATEROLE` or Mongo equivalent).
  ([`USER_ONBOARDING_AUTH.md` Part II step 2](USER_ONBOARDING_AUTH.md#step-2--issue-vault-credentials-to-the-user)).
- The vault is an authenticated store — MongoDB, PostgreSQL, or another backend that
  authenticates connections. DuckDB is in-memory and unauthenticated; it is a test
  store and cannot host a vault.
- OS login security (password or biometric, no auto-login, screen lock, full-disk
  encryption) is organizational endpoint policy.

**In scope.** The four threats in §3.

**Out of scope.** Hardening the vault store's database engine itself (Mongo/Postgres
network exposure, auth misconfiguration). A fully compromised host with root access
to a live, already-authenticated process (memory can always be read).

## 3. Threats and controls

Each subsection: **implementation** (on by default), **weaknesses**, **operator mitigations**
(not on by default).

### 3.1 Vault store exfiltration → offline brute-force

An attacker who obtains a copy of the vault store (backup leak, compromised DB
credentials, insider) recovers plaintext **entirely offline**.

**Implementation.** Writes wrap the RSA-2048 private key with a key derived from the
master password through scrypt (`n=2**17, r=8, p=1`, OWASP-minimum) and a random
16-byte per-user salt, then PKCS8 AES. `VaultUser.post_verify` refuses a save with an
encrypted key and an empty salt. Resource credentials are individually
RSA-OAEP-SHA256-encrypted to each user's public key.

**Weaknesses.**
- A strong KDF does not make a weak master password safe. Cost-per-guess is scrypt's
  work factor (commonly ~100ms–1s); a short or common password is still crackable
  offline, just slower. There is no device-local, never-transmitted second secret
  (1Password's Secret Key). Considered, not adopted: a new machine would need that
  value out of band, not just the password.
- Resource passwords are ciphertext, but `VaultResourceAccessor.login` /
  `resource_uri` / `username` and `VaultUser.public_key` are not. A stolen vault
  store therefore still shows which identities have credentials for which resources
  (URI and login), even when no password can be decrypted. That is this same
  exfiltration threat, not a separate category.

**Operator mitigations.**
- Define an organizational minimum master-password standard (length and/or entropy) at
  onboarding. The KDF only multiplies whatever entropy the password already has.
- Encrypt vault DB backups separately from the live database, and restrict who can
  create, access, or restore them.
- Restrict network access to the vault store to hosts and identities that need it.

### 3.2 Human/developer-machine compromise → keyring access

If an attacker can run code as the developer on a machine that already has vault
credentials in the OS keyring, they can decrypt every resource that identity can
access.

**Implementation.** Master password and vault credentials are cached in the OS keyring (macOS
Keychain, Windows Credential Manager, or a Linux Secret Service session). Identity is
kernel-verified: `cxx10x/core_10x/os_user.cpp` uses `getpwuid(geteuid())` on Unix and
`GetUserNameA` on Windows. `$USER`/`$LOGNAME` are not used.

Before writing a secret, `SecKeys` checks the active keyring backend against an
allowlist of OS-native backends, the in-memory functional-account backend, and
`keyring`'s `FailKeyring` (always raises; cannot silently store). `xx-user-init`
writes through this path, so an unrecognized backend such as `keyrings.alt`'s
plaintext-on-disk one is refused even if it won priority-based discovery.
`VaultUser.suspended` is checked at `sec_keys_get()`, `_user_init_new_machine`, and
`_require_vault_user` (`xx-user-save-credentials` and
`xx-admin-save-user-credentials`).

**Weaknesses.**
- Protection depends on the OS login. A weak login (no password, auto-login, no screen
  lock) degrades it regardless of which keyring is selected. The credential holder can
  also weaken keyring ACLs or export the secret with native OS tools — outside any
  write path this codebase controls.
- A process that has already authenticated keeps working until it exits. That is
  by design. Off-boarding therefore has to cover long-running processes that were
  already unlocked before `suspended` was set: they keep using in-memory credentials
  until restart. Revoking the vault-DB account stops new store connections.

**Operator mitigations.**
- Enforce OS login security as endpoint policy (MDM): full-disk encryption, a real
  password or biometric, no auto-login, screen lock.
- Off-board promptly ([`USER_ONBOARDING_AUTH.md` § Off-boarding](USER_ONBOARDING_AUTH.md#off-boarding)):
  set `VaultUser.suspended = True`, revoke the vault-DB account, and restart
  long-running processes. Revoking the DB account stops further vault access.
  `xx-user-status` shows what is cached on a given machine.

### 3.3 Functional-account container compromise → keyring access

If an attacker can run code inside a functional-account container that has already
loaded its keyring manifest, they can decrypt every resource that account can access.

**Implementation.** Identity is kernel-verified the same way. `docker/entrypoint.sh` renames the
placeholder OS account (`usermod -l`) and drops privileges (`gosu`) before any Python
runs, so `OsUser.me.name()` matches for both the long-running service and one-time
registration. Registration also requires a real OS identity whose name carries the
`xx-` prefix (`VaultUser.user_id_get` → `OsUser.me.name()`).

`FunctionalAccountKeyring` is in-memory-only and never falls through to an OS keychain
or on-disk store. Provisioning and the running service select it via
`PYTHON_KEYRING_BACKEND` (env survives `exec`; an in-process `set_keyring` does not).

`xx-functional-account-init` runs `xx-user-init --functional-account` inside a real
container and delivers the manifest to a host-side provisioning command over a
bind-mounted FIFO named for the account, not a plain file. `--command` typically
creates a namespace-scoped Kubernetes Secret or a Swarm secret (see
[`USER_ONBOARDING_AUTH.md`](USER_ONBOARDING_AUTH.md#functional-unattended-service-accounts)).
At runtime, impersonating a functional account requires both `FUNCTIONAL_ACCOUNT_ID`
(which sets the OS `user_id` the vault checks) and the provisioned manifest mounted
where `FunctionalAccountKeyring` reads it; either alone is insufficient.

**Weaknesses.**
- Provisioning delivers the manifest over a FIFO, not a file. A named pipe has no
  exclusive reader: a second opener on the same path shares the byte stream and can
  corrupt or intercept the manifest — e.g. two `xx-functional-account-init` runs for
  the same account in parallel, or another process as the same OS user (or root)
  opening the per-run path under the `0700` temp directory. Per-account filenames
  only prevent **cross-account** mix-ups, not that.
- Image resolution prefers the GHCR tag matching the installed `py10x-core` version;
  `--image-tag` is trusted as-is, with no digest pinning. `--image-tag` is only needed
  when that version has no matching published image (local unreleased build).

**Operator mitigations.**
- Treat Docker access and `xx-functional-account-init` as equivalent to holding the
  account's credentials.
- For production, use the `:prod` image tag.
- Deliver the manifest into a **namespace-scoped** Secret (Kubernetes) or a Swarm
  secret whose name is derived from the account id
  (`FunctionalAccountKeyring.secret_name`). In Kubernetes, restrict RBAC in that
  namespace so that creating or reading that Secret, and creating or mutating Pods
  that set `FUNCTIONAL_ACCOUNT_ID` and mount it, are limited to the same small set of
  identities. Log and review who deploys those workloads
  and who runs `xx-functional-account-init`.

### 3.4 Vault identity namesquatting → credential interception

An attacker creates a `VaultUser` for an identity they do not own — by minting a
vault-DB login (`CREATEROLE` or Mongo equivalent), or on Mongo by inserting a row
for another `user_id` while connected as their own worker. If an admin later
grants that identity resource access, the attacker decrypts it. Replacing
`VaultUser.public_key` intercepts later grants the same way.

**Implementation.** Registration identity is the kernel OS user (`VaultUser.user_id_get` →
`OsUser.me.name()`). The vault-DB login is admin-issued and must equal that OS
user (`login` and `store.auth_user()` both checked in `xx-user-init`); a matching
local OS account alone is not enough without those vault-DB credentials. The
`VaultUser` id is that name, so it is unique. `admin_save_user_credentials`
loads `VaultUser.existing_instance(user_id=issued_login)`.
`save_ra` encrypts to the live `user.public_key`. `xx-user-save-credentials`
writes only the caller's identity (history `_who`/`_at`).

After `xx-vault-setup-roles`, workers `INSERT`/`FIND` on `VaultUser` (not
`UPDATE`); vault admins may `UPDATE`. On `VaultResourceAccessor`, workers
`INSERT`/`UPDATE` their own rows; admins may grant for others. PostgreSQL RLS
confines worker writes to `_id = current_user` on `VaultUser` and
`username = current_user` on accessors. Mongo applies those privileges
collection-wide (no document-level grant).

**Weaknesses.**
- If ordinary connect access can also create DB roles, an attacker self-issues a
  login matching the victim OS user, creates that OS account locally, and
  registers.
- A login that can `UPDATE` `VaultUser` (stock Mongo `xxUser`, or setup-roles not
  run) can replace `public_key` and intercept later grants.
- On Mongo, a worker can `INSERT` a `VaultUser` for another `user_id` and
  `INSERT`/`UPDATE` any accessor. Operator: confirm `xx-user-status` before grant
  (below). Future: per-user collections (§5).

**Operator mitigations.**
- Issue each vault-DB account to exactly one person or service, named as their OS
  `user_id`, never shared. Hand credentials out of band to the verified owner
  ([`USER_ONBOARDING_AUTH.md` Part II step 2](USER_ONBOARDING_AUTH.md#step-2--issue-vault-credentials-to-the-user)).
- Restrict DB-level role creation to trusted database admins.
- Run `xx-vault-setup-roles` as a database superuser on the vault database
  ([`USER_ONBOARDING_AUTH.md` Part I](USER_ONBOARDING_AUTH.md#part-i--vault-deployment)).
  It creates the collections, `xxVaultWorker` / `xxVaultAdmin`, and the intended
  worker/admin privileges. Do not use stock `xxUser` (`anyResource` read/write) or
  `infra_10x.mongodb_utils.create_xx_user` on the vault. Issue `--vault-admin`
  during deployment (Part I); issue `--worker` per account during onboarding
  (Part II step 2).
- Before granting resource credentials on Mongo, confirm the user completed
  `xx-user-init` successfully — e.g. they email `xx-user-status` output out
  of band. That does not stop a worker from pre-registering another identity,
  but it ensures the admin does not grant until the real user holds the keys.
- Periodically audit `VaultUser` rows that have never been granted resource access
  against expected provisioning records.

## 4. Residual risk

This document is written for a new installation. Residuals would be weaknesses
in §3 that the operator mitigations do not cover; there are none. Out of scope
is in §2; features not built are in §5.

## 5. Not in this release

**Mongo per-user accessor collections.** Worker `INSERT`/`UPDATE` on
`VaultResourceAccessor` is collection-wide. A custom collection per user
would confine those writes without document-level grants.

**Password policy.** `VaultUtils.verify_new_password` is a fixed floor (8
characters, a letter, a capital letter, a digit) for the **master password**.
There is no org-configurable length/entropy standard, breach check, or rotation
cadence in the product for master passwords. Define that at onboarding; the KDF
only multiplies whatever entropy the password already has (§3.1).

**Vault-DB login passwords.** Issued by the superuser (`xx-vault-setup-roles
--worker` / `--vault-admin`); organizations should apply the same password
standard as for other database accounts. The product does not expire or rotate
them after `xx-user-init` — the same password remains valid until changed with
native DB tooling or another `xx-vault-setup-roles` run. **Operator mitigation:**
rotate or revoke via the database when policy requires; off-boarding already
revokes the vault-DB account ([`USER_ONBOARDING_AUTH.md` § Off-boarding](USER_ONBOARDING_AUTH.md#off-boarding)).

**Rotation (split `VaultUser` / `VaultSecret`).** Does not exist.
`VaultUtils.change_master_password` only writes the local keyring and is not
operator tooling. Split the row so workers never `UPDATE` `public_key`:

- **`VaultUser`** (insert-only for workers; admins may `UPDATE`): identity
  (`user_id` = OS user = vault-DB login), `public_key`. `save_ra` encrypts to
  this `public_key`.
- **`VaultSecret`** (insert+update): scrypt salt and PKCS8-AES wrap of the
  private key. Master-password rotation is an `UPDATE` of this row. Resource
  accessors stay valid (`public_key` unchanged). A stolen vault-DB login that
  can `UPDATE` any `VaultSecret` can lock another user out; it cannot intercept
  later grants. Postgres RLS (or keying the row by vault-DB login) should
  confine `UPDATE` to own row; Mongo has no document-level grant. Keying the
  secret by vault-DB login (which is the OS user) makes "own row" the document
  id for that login. Re-run `xx-vault-setup-roles` so workers get `UPDATE` on
  `VaultSecret` only, not on `VaultUser.public_key`.

RSA keypair rotation is a privileged API, not a worker `UPDATE` of `VaultUser`.
The client sends the new `public_key` and every resource accessor re-encrypted
to it, signed with the **current** private key. The endpoint verifies that
signature with the current `VaultUser.public_key`, then writes the new public
key, the new wrap on `VaultSecret`, and the new accessor ciphertexts. Catch-up
on other machines is local keyring state after the wrap changes.

A real mechanism still has to cover three things together: the same password
often shared across more than one vault instance; cadence that can differ by
policy; catch-up on a machine that was not the one that rotated.


