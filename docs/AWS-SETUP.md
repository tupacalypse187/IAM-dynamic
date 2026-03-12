# 🛠️ AWS Setup Guide for IAM-Dynamic

This guide walks you through configuring your AWS account for **IAM-Dynamic** using the automated setup script.

## 📋 Overview

The `setup-aws.sh` script automates the creation and configuration of AWS resources required for IAM-Dynamic to issue temporary credentials via AWS STS (Security Token Service).

### What Gets Created

| Resource | Description | Purpose |
|----------|-------------|---------|
| **IAM Role** | `AgentPOCSessionRole` (default) | The role that the application assumes to issue temporary credentials |
| **Trust Policy** | Auto-configured based on your identity | Allows your IAM user/role and app user to assume the role |
| **IAM User** (optional) | `iam-dynamic-app` (default) | Dedicated user with programmatic access for the application |
| **Access Keys** (optional) | Key pair for the IAM user | Credentials stored in `.env` for Docker deployments |
| **.env Configuration** | Updated with AWS values | Account ID, role name, credentials, region |

---

## 🎯 Prerequisites

Before running the script, ensure you have:

| Requirement | How to Check |
|-------------|--------------|
| **AWS CLI v2+** | `aws --version` |
| **AWS Credentials** | `aws sts get-caller-identity` |
| **IAM Permissions** | Ability to create roles, users, and policies |
| **Bash 4+** | `bash --version` |

### Installing AWS CLI

```bash
# macOS
brew install awscli

# Linux
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Windows (winget)
winget install Amazon.AWSCLI
```

### Configuring AWS Credentials

```bash
aws configure
# Enter your AWS Access Key ID
# Enter your Secret Access Key
# Enter default region (e.g., us-east-1)
# Enter default output format (json)
```

---

## 🚀 Usage

### Basic Setup (Creates IAM User)

```bash
./setup-aws.sh
```

This runs interactively and:
1. Creates the IAM role with trust policy
2. Creates an IAM user with access keys
3. Updates your `.env` file

### Skip User Creation (Use Existing Credentials)

```bash
./setup-aws.sh --skip-user
```

Use this if you want to use your current AWS credentials instead of creating a dedicated application user.

### Help

```bash
./setup-aws.sh --help
```

---

## 🎬 Example User Run

Here's what a typical interactive session looks like:

```bash
$ ./setup-aws.sh

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IAM-Dynamic AWS Setup
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ℹ This script will configure AWS resources for IAM-Dynamic
ℹ You will be prompted for configuration values with sensible defaults


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Checking AWS CLI
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✓ AWS CLI installed: aws-cli/2.22.34 Python/3.12.7 Darwin

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Verifying AWS Credentials
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✓ Authenticated as: arn:aws:iam::123456789012:user/alice
✓ Account ID: 123456789012
ℹ Default region: us-east-1


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Creating IAM Role
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ℹ Determining trust relationship principals...
ℹ Will add IAM user: alice

Role name [AgentPOCSessionRole]:

ℹ Trust policy will allow these AWS entities to assume the role:
  - alice
  - iam-dynamic-app

? Create role with this trust policy [Y/n]?


───────────────────────────────────────────────────────────────────
  AWS Credentials
───────────────────────────────────────────────────────────────────
  Access Key ID:     AKIAIOSFODNN7EXAMPLE
  Secret Access Key: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
───────────────────────────────────────────────────────────────────


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Updating .env File
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ℹ Backed up existing .env file
✓ Updated .env file with AWS configuration

ℹ AWS Configuration Summary:
  Account ID:     123456789012
  Role Name:      AgentPOCSessionRole
  Role ARN:       arn:aws:iam::123456789012:role/AgentPOCSessionRole
  Region:         us-east-1
  Access Key ID:  AKIAIOSFODNN7EXAMPLE
  Secret Key:     [set in .env]


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Setup Complete
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✓ AWS configuration completed successfully!

Created/Updated Resources:
  ├─ IAM Role: AgentPOCSessionRole
  ├─ IAM User: iam-dynamic-app
  └─ .env file updated

Next Steps:
  1. Review and update your .env file with AI provider credentials
  2. Configure authentication (optional): ./setup-auth.sh
  3. Start the application: ./start-dev.sh

ℹ For Docker deployment, the application will use credentials from .env
ℹ For local development, AWS credentials from your environment will be used

ℹ Verifying role trust relationship...
  Trusted principals:
    - alice
    - iam-dynamic-app

⚠ SECURITY REMINDER:
  • Store your AWS credentials securely
  • Never commit .env to version control
  • Rotate credentials regularly
  • Consider using AWS Secrets Manager in production

✓ Setup completed successfully!
```

---

## 🔧 What Gets Created

### IAM Role Trust Policy

The script creates a trust policy that allows:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "sts.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    },
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": ["your-iam-user", "iam-dynamic-app"]
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

### IAM Role Permissions

A base permissions policy is attached with access to common AWS services:

- S3 (`s3:*`)
- EC2 (`ec2:*`)
- Lambda (`lambda:*`)
- DynamoDB (`dynamodb:*`)
- RDS (`rds:*`)
- CloudWatch (`cloudwatch:*`, `logs:*`)
- Secrets Manager (`secretsmanager:*`)

> **Note:** The actual permissions issued to users are scoped by session policies generated by the AI, following the principle of least privilege.

---

## 📁 Updated .env Variables

The script adds these variables to your `.env` file:

```bash
# ============================================
# AWS Configuration
# ============================================
AWS_ACCOUNT_ID=123456789012
AWS_ROLE_NAME=AgentPOCSessionRole
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG...
AWS_DEFAULT_REGION=us-east-1
```

---

## 🛡️ Security Best Practices

### ✅ Do

| Practice | Why |
|----------|-----|
| Rotate credentials regularly | Minimize impact of compromised keys |
| Use dedicated IAM user | Isolate application access from personal access |
| Enable CloudTrail | Audit all assumed role activity |
| Set session duration limits | Reduce exposure window for temporary credentials |
| Store `.env` securely | Prevent accidental credential exposure |

### ❌ Don't

| Practice | Why |
|----------|-----|
| Commit `.env` to git | Exposes credentials in version control |
| Share access keys | Each identity should have unique credentials |
| Use root account | IAM users/roles provide better auditability |
| Grant excessive permissions | Session policies scope down permissions at runtime |

---

## 🔍 Troubleshooting

### AWS CLI Not Installed

```
✗ AWS CLI is not installed
ℹ To install AWS CLI, visit: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html
```

**Solution:** Install AWS CLI using the instructions in the Prerequisites section.

### Credentials Not Configured

```
✗ AWS credentials are not configured or invalid
ℹ Please run: aws configure
```

**Solution:** Run `aws configure` with valid IAM credentials.

### Insufficient Permissions

```
✗ Failed to create IAM role
```

**Solution:** Ensure your IAM user/role has these permissions:
- `iam:CreateRole`
- `iam:GetRole`
- `iam:UpdateAssumeRolePolicy`
- `iam:PutRolePolicy`
- `iam:CreateUser`
- `iam:CreateAccessKey`

### Role Already Exists

```
⚠ Role 'AgentPOCSessionRole' already exists
? Do you want to update the trust relationship and permissions [y/N]?
```

**Solution:** Choose `y` to update the existing role, or `n` to keep it unchanged.

---

## 🧪 Verification

After running the script, verify your setup:

### 1. Check the Role Exists

```bash
aws iam get-role --role-name AgentPOCSessionRole --query 'Role.Arn'
```

### 2. Verify Trust Policy

```bash
aws iam get-role --role-name AgentPOCSessionRole --query 'Role.AssumeRolePolicyDocument' --output json
```

### 3. Test Assume Role (Optional)

```bash
aws sts assume-role \
  --role-arn arn:aws:iam::123456789012:role/AgentPOCSessionRole \
  --role-session-name test-session \
  --duration-seconds 900
```

### 4. Check .env File

```bash
cat .env | grep AWS_
```

---

## 🔄 Cleanup

To remove resources created by this script:

```bash
# Delete access keys
aws iam list-access-keys --user-name iam-dynamic-app
aws iam delete-access-key --user-name iam-dynamic-app --access-key-id AKIA...

# Delete user
aws iam delete-user --user-name iam-dynamic-app

# Delete role policies
aws iam list-role-policies --role-name AgentPOCSessionRole
aws iam delete-role-policy --role-name AgentPOCSessionRole --policy-name IAMDynamicBasePermissions

# Delete role
aws iam delete-role --role-name AgentPOCSessionRole
```

---

## 📚 Related Documentation

- [Main README](../README.md) - Project overview
- [VPS Deployment Guide](./vps-setup-guide.md) - Production deployment
- [CLAUDE.md](../CLAUDE.md) - Developer documentation

---

## 🤝 Contributing

Found a bug or have a suggestion? Please open an issue on GitHub.

---

## 📄 License

MIT © 2025
