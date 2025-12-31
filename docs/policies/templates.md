# Policy and risk templates

Use these starter templates when standing up ctrl in a new environment.

## Base policy.yaml
```yaml
policies:
  # Block obviously dangerous actions first
  - id: deny-prod-delete
    match: { server: "*", tool: "*delete*", env: "prod" }
    effect: deny
    reason: "Delete tools are blocked in prod"

  # Allow everything else, but gate high risk for approval
  - id: allow-with-review
    match: { server: "*", tool: "*", env: "*" }
    effect: allow
    reason: "Allowed unless risk says otherwise"
    deny: "risk.mode == 'danger'"
    require_approval_if: "risk.mode in ['review']"
```

## Base risk.yaml
```yaml
risk:
  mode: modes

  modes:
    safe:   { score: 10 }
    review: { score: 50 }
    danger: { score: 90 }

  rules:
    # Lower risk for read-only servers
    - name: read-only
      when: { server: "docs", tool: "*" }
      set_mode: safe
      reason: "Read-only documentation server"

    # Raise risk for prod deploys
    - name: prod-deploy-review
      when: { server: "deploy", env: "prod" }
      set_mode: review
      reason: "Deploying to production"

    # Block obvious payloads
    - name: block-script
      when:
        tool: "*"
        args:
          html:
            contains: "<script"
      set_mode: danger
      reason: "HTML contains script tag"

  set_mode_by_score:
    danger: "score >= 70"
    review: "score >= 40"
    safe:   "score < 40"
```

## Prod deploy gating (policy)
```yaml
- id: prod-deploy-approval
  match: { server: "deploy", tool: "*", env: "prod" }
  effect: allow
  reason: "Prod deploys require human review"
  require_approval_if: "True"
```

## Lint and validate
- Structural validation: `ctrl validate-config --servers <servers.yaml> --policy <policy.yaml> --db ctrl.db`
- Policy lint: `ctrl policy lint --policy <policy.yaml>`
- Policy explain: `ctrl policy explain --server <name> --tool <tool> [--env dev]`
