# ModelRouter naming and project landscape

Checked on 2026-09-16. **ModelRouter is not a unique product name.** GitHub repository names are scoped to an owner, so the repository can still use `modelrouter`, but public search results already contain several unrelated projects with the same or a near-identical name.

| Project | Observed design | Main difference from this repository |
|---|---|---|
| [Scylla23/modelrouter](https://github.com/Scylla23/modelrouter) | Claude Code plugin that rewrites subagent delegation and learns from corrections | Exact public name and a close cost-saving concept, but tied to Claude Code hooks and Claude model tiers |
| [sunilgattupalle/model-router](https://github.com/sunilgattupalle/model-router) | Claude Code prompt hook, model switching, SQLite outcomes and feedback strategies | Reads prompt features and changes Claude settings; this Skill does neither automatically |
| [sybil-solutions/codex-shim Auto Router](https://github.com/sybil-solutions/codex-shim/blob/main/docs/AUTO_ROUTER.md) | Codex proxy/shim with a classifier call and per-task backend selection | Sits in the request path and routes the primary model; this Skill guides bounded delegation through host tools |
| [giovannimirarchi420/codex-smart-router](https://github.com/giovannimirarchi420/codex-smart-router) | Codex wrapper and local proxy with classifier backends, audit logs and a dashboard | Can send prompts to a classifier and reroute each turn; this Skill has no proxy or automatic prompt inspection |
| [capitalparser/codex-model-router](https://github.com/capitalparser/codex-model-router) | Codex Skill plus fixed custom agents for phase-aware GPT-5.6 delegation | Closest Skill packaging pattern; it pins a narrower agent/model setup while this project discovers host-supported model IDs and preserves an existing workflow |
| [Saadfk/codex-model-router](https://github.com/Saadfk/codex-model-router/blob/main/docs/codex_model_router.md) | Codex launcher and user hook with a classifier or heuristic path | Routes root tasks started through its launcher and can install a hook; this project does not intercept an already submitted prompt |
| [keithmackay/modelrouter](https://github.com/keithmackay/modelrouter) | Self-hosted OpenAI-compatible multi-provider gateway with credentials, budgets and upstream routing | Network service in the model data path; this project is a local instruction package and optional offline helpers |

The public display name is **ModelRouter for Codex**. The Skill invocation remains the shorter `$modelrouter`. This qualifier reduces confusion without changing the requested product name.

Namespace check on 2026-09-16: the unscoped npm registry returned `E404` for `modelrouter`, while PyPI already has a separate [`model-router`](https://pypi.org/project/model-router/) project. Registry status can change at any time; an unpublished name is not reserved.

Do not copy benchmark or savings claims from these projects. Their routing surfaces, model sets, billing paths and outcome definitions differ. ModelRouter reports savings only from its own matched, failure-inclusive observations with complete host telemetry.
