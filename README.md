# Infoblox Intelligent CIDR Allocation (AAP-ready)

Self-service, **alignment-aware** CIDR allocation from an Infoblox parent
container — driven by a one-form survey in **Ansible Automation Platform**
(not bare `ansible-core`).

> *"Give me a /22 from 10.217.0.0/16"* → the role queries Infoblox for
> already-allocated children of that container, picks the **next aligned**
> /22 that doesn't overlap anything, and reserves it in Infoblox with one
> API call.

Supports both Infoblox platforms via two custom AAP credential types:

| Platform              | Collection                     | AAP Credential Type                        |
|-----------------------|--------------------------------|--------------------------------------------|
| On-prem NIOS Grid     | `infoblox.nios_modules`        | `aap_config/credential_type_nios.yml`        |
| Cloud / Universal DDI | `infoblox.universal_ddi`       | `aap_config/credential_type_universal_ddi.yml` |

## Why "alignment-aware"?

A subnet has to start on an address divisible by its size. Asking for a
**/22** (1024 addresses) inside `10.217.0.0/16` means the answer must
start at `10.217.0.0`, `10.217.4.0`, `10.217.8.0`, …, never at
`10.217.1.0`. The role:

1. Lists every existing child of the parent container in Infoblox.
2. Generates every *aligned* candidate of the requested size inside the
   parent.
3. Removes candidates that overlap anything occupied.
4. Picks one according to the chosen **allocation policy** (`first-fit`
   or `last-fit`).
5. Reserves it via the appropriate certified collection.

The selection logic lives in a single Python filter plugin —
[`roles/infoblox_cidr_allocate/filter_plugins/cidr_allocation.py`](roles/infoblox_cidr_allocate/filter_plugins/cidr_allocation.py)
— with unit tests under
[`roles/infoblox_cidr_allocate/tests/`](roles/infoblox_cidr_allocate/tests/test_alignment.py).

## Repository layout

```
.
├── README.md                                ← you are here
├── ansible.cfg                              ← galaxy server list + roles_path
├── collections/requirements.yml             ← certified collections
├── inventory/hosts.yml                      ← localhost (role drives APIs)
├── playbooks/allocate_cidr.yml              ← AAP job-template entrypoint
├── execution-environment/                   ← EE definition for ansible-builder
├── aap_config/                              ← AAP Config-as-Code
│   ├── README.md                            ← CaC usage + secret-store explanation
│   ├── configure_aap.yml                    ← provisions every AAP object
│   ├── credential_type_nios.yml             ← custom credential type (NIOS)
│   ├── credential_type_universal_ddi.yml    ← custom credential type (UDDI)
│   ├── survey.yml                           ← "give me a /22 from …" survey
│   └── group_vars/all/                      ← aap.yml + objects.yml
└── roles/
    └── infoblox_cidr_allocate/              ← the role doing the work
        ├── defaults/main.yml
        ├── meta/main.yml
        ├── tasks/
        │   ├── main.yml                     ← orchestrator (query → compute → reserve)
        │   ├── discover_nios.yml            ← list children via nios_lookup
        │   ├── discover_universal_ddi.yml   ← list children via ipam_*_info
        │   ├── reserve_nios.yml             ← nios_network state=present
        │   └── reserve_universal_ddi.yml    ← ipam_subnet / ipam_address_block
        ├── filter_plugins/
        │   └── cidr_allocation.py           ← alignment-aware selection (5–10 LoC TODO)
        ├── templates/summary.j2             ← post-run report
        └── tests/test_alignment.py          ← unit tests for the filter
```

## Survey

When the operator launches **"Allocate Infoblox CIDR"** in AAP, the
survey collects:

| Variable                  | Required | Example         | Notes                                              |
|---------------------------|----------|-----------------|----------------------------------------------------|
| `cidr_parent`             | yes      | `10.217.0.0/16` | parent container                                   |
| `cidr_prefix`             | yes      | `22`            | desired prefix length, must be > parent prefix     |
| `cidr_comment`            | no       | `Cluster A`     | free text recorded on the new Infoblox object      |
| `cidr_dry_run`            | yes      | `false`         | compute + display, don't reserve                   |
| `cidr_allocation_policy`  | yes      | `first-fit`     | `first-fit` (low end) or `last-fit` (high end)     |
| `cidr_network_view`       | NIOS     | `default`       | NIOS network view                                  |
| `cidr_ip_space`           | UDDI     | `Production`    | name of the UDDI IP Space                          |
| `cidr_object_type`        | UDDI     | `subnet`        | `subnet` or `address_block`                        |

The survey schema is checked into Git at
[`aap_config/survey.yml`](aap_config/survey.yml) and attached to the JT
by Config-as-Code — no clicking around required.

## Bootstrapping AAP

Two paths — pick one:

### Option A: Config-as-Code (recommended)

Provisions every AAP object — Org, EE, Project, Inventory, both custom
credential types, the survey, and the job template — in one idempotent
playbook run. Secret values stay in AAP's own encrypted credential
store; this repo never sees them.
See [`aap_config/README.md`](aap_config/README.md) for the full guide.

```sh
ansible-galaxy collection install -r collections/requirements.yml
export CONTROLLER_HOST=https://aap.example.com
export CONTROLLER_OAUTH_TOKEN=********
$EDITOR aap_config/group_vars/all/objects.yml   # set EE image + Git URL
ansible-playbook aap_config/configure_aap.yml
```

Then, **once**, create your Infoblox credentials in the AAP UI
(*Resources → Credentials → Add* → pick "Infoblox NIOS Grid" or
"Infoblox Universal DDI"). The JT prompts the operator to pick one at
launch.

You also need to **build the EE** from
`execution-environment/execution-environment.yml`
(`ansible-builder build -t infoblox-cidr-ee:latest …`) and push it to a
registry AAP can pull from — CaC then registers it.

### Option B: Click-ops in the UI

1. Add this repo as a Project (Source Control → Git → this repo URL).
2. Build/import the EE, push to your registry, register it in AAP.
3. Import both credential types under *Administration → Credential
   Types → Import* using the two YAML files in `aap_config/`.
4. Create credentials of those types — one per Infoblox endpoint.
5. Create a job template pointing at `playbooks/allocate_cidr.yml`, use
   the EE, prompt for / attach one Infoblox credential, and **paste the
   survey from `aap_config/survey.yml`**.

## Running locally (smoke test only)

```sh
# install certified collections from public Galaxy (see ansible.cfg
# for how to point this at console.redhat.com instead)
ansible-galaxy collection install -r collections/requirements.yml

# dry run — prints what it WOULD do without calling Infoblox
ansible-playbook playbooks/allocate_cidr.yml \
  -e infoblox_platform=nios \
  -e cidr_parent=10.217.0.0/16 \
  -e cidr_prefix=22 \
  -e cidr_dry_run=true
```

## How the dual-mode dispatch works

1. The operator attaches **one** of the two custom credential types to
   the JT in AAP.
2. The credential type sets `infoblox_platform` to `nios` or
   `universal_ddi` via `injectors.extra_vars`.
3. The role's `tasks/main.yml` does
   `include_tasks: "discover_{{ infoblox_platform }}.yml"` and
   `include_tasks: "reserve_{{ infoblox_platform }}.yml"`, so the right
   backend runs with no UI prompting.
4. The Python filter is platform-agnostic — same algorithm regardless
   of where the parent lives.

## Testing the alignment filter

```sh
python -m pytest roles/infoblox_cidr_allocate/tests/test_alignment.py -v
```

The tests describe the contract — they intentionally fail until the
`TODO` in `find_next_aligned_block` is implemented.

## Status

- [x] Repo skeleton, ansible.cfg, requirements, EE, inventory
- [x] Both AAP credential types
- [x] AAP Config-as-Code with survey attached
- [x] NIOS: discover via `nios_lookup`, reserve via `nios_network`
- [x] UDDI: discover via `ipam_*_info`, reserve via `ipam_subnet` / `ipam_address_block`
- [x] Filter plugin scaffold + unit tests
- [ ] `find_next_aligned_block` body — see [the TODO](roles/infoblox_cidr_allocate/filter_plugins/cidr_allocation.py)
