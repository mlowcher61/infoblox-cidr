# AAP Config-as-Code

This directory provisions every **non-secret** AAP object the Infoblox
Intelligent CIDR Allocation solution needs: **organization, execution
environment, project, inventory (plus localhost), both custom credential
types, and the survey-driven job template** — using the **`ansible.platform`**
collection that ships with AAP 2.5+.

Credential **instances** (the secret-bearing objects) are deliberately
out of scope. AAP itself encrypts and stores those — see [Where do the
secrets go?](#where-do-the-secrets-go) below.

## Quick start

```sh
# 1. Install collections (pulls in ansible.platform).
ansible-galaxy collection install -r ../collections/requirements.yml

# 2. Point at the controller.
export CONTROLLER_HOST=https://aap.example.com
export CONTROLLER_OAUTH_TOKEN=********           # or USERNAME/PASSWORD

# 3. Edit object names, EE image, and Git URL.
$EDITOR aap_config/group_vars/all/objects.yml

# 4. Apply.
ansible-playbook aap_config/configure_aap.yml

# 5. (One-time, manual) Create Infoblox credentials in the AAP UI.
#    Resources → Credentials → Add → choose
#       "Infoblox NIOS Grid"   or   "Infoblox Universal DDI"
#    Fill in the host / user / password / API key. AAP encrypts the
#    values; nobody reads them from disk again.

# 6. Launch the "Allocate Infoblox CIDR" job template — the survey
#    prompts the operator for parent CIDR, prefix length, etc.
```

## What this creates

| AAP object | Source of truth |
|---|---|
| Organization | `group_vars/all/objects.yml` → `aap_organization` |
| Execution Environment | `group_vars/all/objects.yml` → `aap_execution_environment` |
| Project (this repo) | `group_vars/all/objects.yml` → `aap_project` |
| Inventory + localhost | `group_vars/all/objects.yml` → `aap_inventory` |
| Credential Type — NIOS | `aap_config/credential_type_nios.yml` (loaded at runtime) |
| Credential Type — UDDI | `aap_config/credential_type_universal_ddi.yml` (loaded at runtime) |
| Job Template | `group_vars/all/objects.yml` → `aap_job_template` |
| Survey | `aap_config/survey.yml` (loaded at runtime, attached to the JT) |

## Where do the secrets go?

**Into AAP, not into Git.** Each credential type defines an `injectors:`
block that maps user-typed fields to the env vars the Infoblox
collections read at runtime:

```
Admin in AAP UI ──▶ creates credential of type "Infoblox NIOS Grid"
                    fills in host / user / password
                    AAP encrypts inputs in its DB
                          │
Operator launches JT ─────┘
       │
       └─▶ AAP injects env vars into the EE container
                          │
                          └─▶ infoblox.nios_modules / infoblox.universal_ddi
                              pick them up automatically
```

Benefits:

- **No vault password to manage.**
- **No secret material in this Git repo.** Ever.
- **Per-environment credentials are trivial** (create `NIOS-dev`,
  `NIOS-prod`, etc.; operator picks at launch).
- **RBAC is AAP's** — who can use which endpoint is governed by AAP
  credential ownership/permissions.

## Idempotency

Every task uses `state: present`, and the `ansible.platform` modules
upsert by name — re-running the playbook converges to the declared state.

## Layout

```
aap_config/
├── README.md                          ← you are here
├── configure_aap.yml                  ← entrypoint playbook
├── credential_type_nios.yml           ← schema for NIOS credentials
├── credential_type_universal_ddi.yml  ← schema for UDDI credentials
├── survey.yml                         ← survey schema attached to the JT
└── group_vars/all/
    ├── aap.yml                        ← controller endpoint + auth (env-driven)
    └── objects.yml                    ← Org, EE, Project, Inventory, JT
```
