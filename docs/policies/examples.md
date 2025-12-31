# Policy examples

## Demo policy (publish market report)
`demos/e2e_publish_market_report/configs/policy.yaml`:
```yaml
policies:
  - id: allow-with-approval
    match: { server: "*", tool: "*", env: "*" }
    effect: allow
    reason: "Allowed but gated by risk"
    deny: "risk.mode == 'danger'"
    require_approval_if: "risk.mode in ['review']"

  - id: allow-default
    match: { server: "*", tool: "*", env: "*" }
    effect: allow
    reason: "Default allow"
```
This pairs with `risk.yaml` that marks EdgeOne publish tools as `review` and any HTML containing `<script` as `danger`.

## Environment-sensitive deploys
Only allow deploys in staging; block prod unless explicitly approved:
```yaml
- id: staging-deploy-allow
  match: { server: "deploy", tool: "*", env: "staging" }
  effect: allow
  reason: "Staging deploys are allowed"

- id: prod-deploy-approval
  match: { server: "deploy", tool: "*", env: "prod" }
  effect: allow
  reason: "Prod deploys require review"
  require_approval_if: "True"
```

## Argument-driven risk
Escalate when sensitive terms appear in arguments, then let policy gate by risk:
```yaml
# risk.yaml
  - name: secrets-in-args
    when:
      args:
        message:
          contains: "AWS_SECRET_ACCESS_KEY"
    set_mode: danger
    reason: "Possible credential exfiltration"
```
With the base policy template, any `danger` mode would be denied automatically.

## Testing policies
Create a policy test file:
```yaml
tests:
  - name: block-prod-delete
    server: "db"
    tool: "delete*"
    env: "prod"
    expect: deny
  - name: approve-staging-deploy
    server: "deploy"
    tool: "*"
    env: "staging"
    expect: allow
```
Run with `ctrl policy test <path> --policy <policy.yaml>` to prevent regressions as you tighten rules.
