# IAM Base Roles — review & apply guide

> ⛔ **STOP — owner approval required.** Nothing in this directory is applied
> automatically. The template below only *proposes* roles; creating IAM
> roles and trust relationships in your AWS account happens only when you
> explicitly say to execute it. CI never touches AWS.

## What this is

[`iam-base-roles.yml`](./iam-base-roles.yml) (CloudFormation) proposes six
session **base roles** in your account. The backend assumes one per request —
matched to the task class — and intersects it with the AI-generated session
policy, so issued credentials are always *base ∩ refinement* (a mismatch
fails closed at STS time, never open).

| Role | Base for | Never auto-selected? |
|---|---|---|
| `ReadOnly` | Read-only tasks (all Get/List/Describe) | auto-selected for read-only policies |
| `Auditor` | Security audits (`SecurityAudit` managed set) | manual assignment (v1) |
| `Developer` | General build/deploy (no IAM/Orgs surfaces) | default for non-read-only |
| `Support` | Incident triage (logs, metrics, reboot) | manual assignment (v1) |
| `DataAnalyst` | Analytics reads (S3/Athena/Glue) | manual assignment (v1) |
| `Admin` | Break-glass (mirrors the current POC role, 1h max) | **never** auto-selected |

Trust is restricted to exactly the `DeployerPrincipalArn` you pass (the
identity the backend runs as) — no account-wide trust.

## Review first (no AWS calls that change anything)

```bash
# 1. Validate the template syntax
aws cloudformation validate-template \
  --template-body file://aws/iam-base-roles.yml

# 2. Preview the change set (dev names shown; use Environment=prod for prod)
aws cloudformation create-change-set \
  --stack-name iam-dynamic-base-roles-dev \
  --template-body file://aws/iam-base-roles.yml \
  --parameters ParameterKey=Environment,ParameterValue=dev \
               ParameterKey=DeployerPrincipalArn,ParameterValue=arn:aws:iam::123456789012:user/YOUR-DEPLOYER \
  --change-set-name preview-1 \
  --capabilities CAPABILITY_NAMED_IAM

aws cloudformation describe-change-set \
  --stack-name iam-dynamic-base-roles-dev \
  --change-set-name preview-1
```

## Apply (only with explicit owner approval)

```bash
aws cloudformation deploy \
  --stack-name iam-dynamic-base-roles-dev \
  --template-body file://aws/iam-base-roles.yml \
  --parameter-overrides Environment=dev \
    DeployerPrincipalArn=arn:aws:iam::123456789012:user/YOUR-DEPLOYER \
  --capabilities CAPABILITY_NAMED_IAM
```

## Wire the ARNs into the app (B4)

Copy the six output ARNs into `.env` (never commit). Until these are set,
the backend keeps today's single-role behavior unchanged:

```bash
AWS_BASE_ROLE_READONLY=arn:aws:iam::123456789012:role/iam-dynamic-dev-ReadOnly
AWS_BASE_ROLE_AUDITOR=arn:aws:iam::123456789012:role/iam-dynamic-dev-Auditor
AWS_BASE_ROLE_DEVELOPER=arn:aws:iam::123456789012:role/iam-dynamic-dev-Developer
AWS_BASE_ROLE_SUPPORT=arn:aws:iam::123456789012:role/iam-dynamic-dev-Support
AWS_BASE_ROLE_ANALYST=arn:aws:iam::123456789012:role/iam-dynamic-dev-DataAnalyst
AWS_BASE_ROLE_ADMIN=arn:aws:iam::123456789012:role/iam-dynamic-dev-Admin
```

Then sanity-check the intersection before any session uses it:

```bash
aws iam simulate-principal-policy \
  --policy-source-arn <ReadOnlyRoleArn> \
  --action-names s3:GetObject s3:PutObject
# expect GetObject allowed, PutObject denied
```
