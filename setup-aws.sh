#!/bin/bash
# =============================================================================
# IAM-Dynamic AWS Setup Script
# =============================================================================
# This script configures the AWS account with the necessary IAM role and
# trust relationship for the IAM-Dynamic application.
#
# It will:
#   1. Verify AWS CLI is installed and configured
#   2. Detect or prompt for AWS account ID
#   3. Create an IAM role with trust relationship
#   4. Optionally create an IAM user with programmatic access
#   5. Update the .env file with AWS configuration
#
# Usage: ./setup-aws.sh [--skip-user]
#   --skip-user: Skip IAM user creation (use existing credentials)
# =============================================================================

set -euo pipefail

# =============================================================================
# SCRIPT CONFIGURATION
# =============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"
ENV_EXAMPLE="${SCRIPT_DIR}/.env.example"
DEFAULT_ROLE_NAME="AgentPOCSessionRole"
DEFAULT_USER_NAME="iam-dynamic-app"
DEFAULT_REGION="us-east-1"

# Color codes for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# =============================================================================
# CLEANUP HANDLERS
# =============================================================================

cleanup() {
    local exit_code=$?
    if [[ $exit_code -ne 0 ]]; then
        echo -e "\n${RED}✗ Script exited with error code ${exit_code}${NC}"
        echo -e "${YELLOW}Please review the error messages above and try again.${NC}"
    fi
}

# Trap EXIT for cleanup, ERR for errors, and INT for Ctrl-C
trap cleanup EXIT
trap 'echo -e "\n${YELLOW}Script interrupted by user${NC}"; exit 130' INT
trap 'echo -e "\n${RED}✗ Command failed: $BASH_COMMAND${NC}"; exit 1' ERR

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

print_header() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# Prompt user with default value
prompt_with_default() {
    local prompt="$1"
    local default_value="$2"
    local result

    if [[ -n "${3:-}" ]]; then
        # Hidden input (password)
        read -s -p "$(echo -e "${BLUE}${prompt} [${YELLOW}${default_value}${BLUE}]: ${NC}")" result
        echo
    else
        read -p "$(echo -e "${BLUE}${prompt} [${YELLOW}${default_value}${BLUE}]: ${NC}")" result
    fi

    echo "${result:-$default_value}"
}

# Confirm yes/no
confirm() {
    local prompt="$1"
    local default="${2:-n}"
    local response

    if [[ "$default" == "y" ]]; then
        prompt="${prompt} [Y/n]"
    else
        prompt="${prompt} [y/N]"
    fi

    read -p "$(echo -e "${YELLOW}${prompt}? ${NC}")" response
    response="${response:-$default}"

    [[ "$response" =~ ^[Yy]$ ]]
}

# Check if command exists
command_exists() {
    command -v "$1" &>/dev/null
}

# =============================================================================
# AWS VERIFICATION
# =============================================================================

check_aws_cli() {
    print_header "Checking AWS CLI"

    if ! command_exists aws; then
        print_error "AWS CLI is not installed"
        print_info "To install AWS CLI, visit: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
        exit 1
    fi

    local aws_version
    aws_version=$(aws --version 2>&1 | head -n1)
    print_success "AWS CLI installed: ${aws_version}"
}

check_aws_credentials() {
    print_header "Verifying AWS Credentials"

    if ! aws sts get-caller-identity &>/dev/null; then
        print_error "AWS credentials are not configured or invalid"
        print_info "Please run: aws configure"
        exit 1
    fi

    local identity
    identity=$(aws sts get-caller-identity --output json 2>/dev/null)

    AWS_ACCOUNT_ID=$(echo "$identity" | jq -r '.Account')
    AWS_ARN=$(echo "$identity" | jq -r '.Arn')
    AWS_USER_ID=$(echo "$identity" | jq -r '.UserId')

    print_success "Authenticated as: ${AWS_ARN}"
    print_success "Account ID: ${AWS_ACCOUNT_ID}"

    # Get current region
    AWS_REGION=$(aws configure get region 2>/dev/null || echo "$DEFAULT_REGION")
    print_info "Default region: ${AWS_REGION}"
}

get_caller_identity_type() {
    local arn="$1"
    if [[ "$arn" =~ :user/ ]]; then
        echo "user"
    elif [[ "$arn" =~ :role/ ]]; then
        echo "role"
    elif [[ "$arn" =~ :assumed-role/ ]]; then
        echo "assumed-role"
    else
        echo "unknown"
    fi
}

# =============================================================================
# IAM ROLE CREATION
# =============================================================================

get_role_principals() {
    local caller_type="$1"
    local caller_arn="$2"
    local principals="[]"

    print_info "Determining trust relationship principals..."

    case "$caller_type" in
        user)
            # User can create credentials or use a profile
            local username
            username=$(basename "$caller_arn")
            principals=$(jq -n --arg user "$username" '[$user]')
            print_info "Will add IAM user: ${username}"
            ;;
        role)
            # Using a role - extract the role name
            local role_name
            role_name=$(basename "$caller_arn")
            principals=$(jq -n --arg role "$role_name" '[$role]')
            print_info "Will add IAM role: ${role_name}"
            ;;
        assumed-role)
            # We're already assuming a role - use the role name
            local role_name
            role_name=$(echo "$caller_arn" | sed 's/:assumed-role\//:role\//' | cut -d'/' -f2)
            principals=$(jq -n --arg role "$role_name" '[$role]')
            print_info "Will add IAM role: ${role_name}"
            ;;
        *)
            print_warning "Unknown caller type: ${caller_type}"
            print_warning "You will need to manually configure the trust policy"
            ;;
    esac

    echo "$principals"
}

create_iam_role() {
    print_header "Creating IAM Role"

    ROLE_NAME=$(prompt_with_default "Role name" "$DEFAULT_ROLE_NAME")

    # Check if role already exists
    if aws iam get-role --role-name "$ROLE_NAME" &>/dev/null; then
        print_warning "Role '${ROLE_NAME}' already exists"
        if confirm "Do you want to update the trust relationship and permissions" "n"; then
            print_info "Updating existing role..."
        else
            print_info "Keeping existing role as-is"
            # Get current role to show the user
            local current_role
            current_role=$(aws iam get-role --role-name "$ROLE_NAME" --query 'Role.Arn' --output text 2>/dev/null)
            print_success "Using existing role: ${current_role}"
            return 0
        fi
    fi

    # Build trust policy
    local caller_type
    caller_type=$(get_caller_identity_type "$AWS_ARN")

    local principals
    principals=$(get_role_principals "$caller_type" "$AWS_ARN")

    # Additional principals - for app user that will be created
    local additional_principals="[]"
    if [[ "$SKIP_USER" != "true" ]]; then
        additional_principals=$(jq -n --arg user "$DEFAULT_USER_NAME" '[$user]')
    fi

    # Combine principals
    local all_principals
    all_principals=$(echo "$principals" "$additional_principals" | jq -s 'add | unique')

    # Create trust policy
    local trust_policy
    trust_policy=$(jq -n \
        --argjson aws_principals "$all_principals" \
        '{
            Version: "2012-10-17",
            Statement: [
                {
                    Effect: "Allow",
                    Principal: {Service: "sts.amazonaws.com"},
                    Action: "sts:AssumeRole"
                },
                {
                    Effect: "Allow",
                    Principal: {AWS: $aws_principals},
                    Action: "sts:AssumeRole"
                }
            ]
        }')

    print_info "Trust policy will allow these AWS entities to assume the role:"
    echo "$all_principals" | jq -r '.[]' | while read -r principal; do
        echo "  - ${principal}"
    done

    echo
    if ! confirm "Create role with this trust policy" "y"; then
        print_error "Aborted by user"
        exit 1
    fi

    # Create or update the role
    if aws iam get-role --role-name "$ROLE_NAME" &>/dev/null; then
        # Update existing role
        aws iam update-assume-role-policy \
            --role-name "$ROLE_NAME" \
            --policy-document "$trust_policy" &>/dev/null
        print_success "Updated trust policy for role '${ROLE_NAME}'"
    else
        # Create new role
        if ! aws iam create-role \
            --role-name "$ROLE_NAME" \
            --assume-role-policy-document "$trust_policy" \
            --description "IAM-Dynamic JIT access role" \
            --max-session-duration 43200 \
            --output text \
            --query 'Role.Arn' 2>/dev/null; then
            print_error "Failed to create IAM role"
            exit 1
        fi
        print_success "Created IAM role: ${ROLE_NAME}"
    fi

    # Attach a basic permissions policy
    # This is a placeholder - the actual permissions come from session policies
    local basic_policy
    basic_policy=$(jq -n '{
        Version: "2012-10-17",
        Statement: [
            {
                Effect: "Allow",
                Action: [
                    "s3:*",
                    "ec2:*",
                    "lambda:*",
                    "dynamodb:*",
                    "rds:*",
                    "cloudwatch:*",
                    "logs:*",
                    "iam:ListRoles",
                    "iam:GetRole",
                    "secretsmanager:*"
                ],
                Resource: "*"
            }
        ]
    }')

    print_info "Attaching basic permissions policy to role..."
    if aws iam put-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-name "IAMDynamicBasePermissions" \
        --policy-document "$basic_policy" &>/dev/null; then
        print_success "Attached base permissions policy"
    else
        print_warning "Failed to attach base policy (you may need to add permissions manually)"
    fi

    print_success "Role ARN: arn:aws:iam::${AWS_ACCOUNT_ID}:role/${ROLE_NAME}"
}

# =============================================================================
# IAM USER CREATION
# =============================================================================

create_iam_user() {
    print_header "Creating IAM User for Application"

    if [[ "$SKIP_USER" == "true" ]]; then
        print_info "Skipping IAM user creation (--skip-user flag)"
        print_info "Using existing AWS credentials from your environment"
        CREATE_USER=false
        return 0
    fi

    if ! confirm "Create IAM user for application credentials" "y"; then
        CREATE_USER=false
        print_info "Skipping IAM user creation"
        print_info "You will use your current AWS credentials"
        return 0
    fi

    CREATE_USER=true
    USER_NAME=$(prompt_with_default "User name" "$DEFAULT_USER_NAME")

    # Check if user exists
    if aws iam get-user --user-name "$USER_NAME" &>/dev/null; then
        print_warning "User '${USER_NAME}' already exists"
        if confirm "Do you want to create new access keys for this user" "n"; then
            print_info "Creating new access keys..."
        else
            print_info "Skipping user creation - user already exists"
            CREATE_USER=false
            return 0
        fi
    else
        # Create user
        print_info "Creating IAM user: ${USER_NAME}"
        if ! aws iam create-user --user-name "$USER_NAME" &>/dev/null; then
            print_error "Failed to create IAM user"
            exit 1
        fi
        print_success "Created IAM user: ${USER_NAME}"
    fi

    # Add user to the role's trust policy
    print_info "Adding user to role trust policy..."
    local current_policy
    current_policy=$(aws iam get-role --role-name "$ROLE_NAME" --query 'Role.AssumeRolePolicyDocument' --output json 2>/dev/null)

    local updated_policy
    updated_policy=$(echo "$current_policy" | jq \
        --arg user "$USER_NAME" \
        '.Statement += [{
            Effect: "Allow",
            Principal: {AWS: $user},
            Action: "sts:AssumeRole"
        }] | .Statement |= unique_by(.Principal // empty)')

    aws iam update-assume-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-document "$updated_policy" &>/dev/null

    print_success "Added ${USER_NAME} to role trust relationship"

    # Create access keys
    print_info "Creating access keys..."
    local keys
    keys=$(aws iam create-access-key --user-name "$USER_NAME" --output json 2>/dev/null)

    if [[ -z "$keys" ]]; then
        print_error "Failed to create access keys"
        exit 1
    fi

    AWS_ACCESS_KEY_ID=$(echo "$keys" | jq -r '.AccessKey.AccessKeyId')
    AWS_SECRET_ACCESS_KEY=$(echo "$keys" | jq -r '.AccessKey.SecretAccessKey')

    print_success "Created access keys"
    print_warning "IMPORTANT: Save these credentials securely!"
    print_warning "You won't be able to retrieve the secret key again!"

    echo
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${YELLOW}  AWS Credentials${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "  Access Key ID:     ${GREEN}${AWS_ACCESS_KEY_ID}${NC}"
    echo -e "  Secret Access Key: ${GREEN}${AWS_SECRET_ACCESS_KEY}${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo
}

# =============================================================================
# .ENV FILE UPDATE
# =============================================================================

update_env_file() {
    print_header "Updating .env File"

    # Create .env if it doesn't exist
    if [[ ! -f "$ENV_FILE" ]]; then
        if [[ -f "$ENV_EXAMPLE" ]]; then
            cp "$ENV_EXAMPLE" "$ENV_FILE"
            print_info "Created .env from .env.example"
        else
            touch "$ENV_FILE"
            print_info "Created new .env file"
        fi
    fi

    # Backup existing .env
    if [[ -f "$ENV_FILE" ]]; then
        cp "$ENV_FILE" "${ENV_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
        print_info "Backed up existing .env file"
    fi

    # Update AWS configuration in .env
    local temp_env
    temp_env=$(mktemp)

    # Check if AWS variables already exist
    local has_account_id has_role_name has_access_key has_secret_key has_region
    has_account_id=$(grep -c "^AWS_ACCOUNT_ID=" "$ENV_FILE" 2>/dev/null || echo 0)
    has_role_name=$(grep -c "^AWS_ROLE_NAME=" "$ENV_FILE" 2>/dev/null || echo 0)
    has_access_key=$(grep -c "^AWS_ACCESS_KEY_ID=" "$ENV_FILE" 2>/dev/null || echo 0)
    has_secret_key=$(grep -c "^AWS_SECRET_ACCESS_KEY=" "$ENV_FILE" 2>/dev/null || echo 0)
    has_region=$(grep -c "^AWS_DEFAULT_REGION=" "$ENV_FILE" 2>/dev/null || echo 0)

    # Copy existing content and update/add AWS variables
    awk -v account_id="$AWS_ACCOUNT_ID" \
        -v role_name="$ROLE_NAME" \
        -v access_key="${AWS_ACCESS_KEY_ID:-}" \
        -v secret_key="${AWS_SECRET_ACCESS_KEY:-}" \
        -v region="$AWS_REGION" \
        -v has_acc="$has_account_id" \
        -v has_role="$has_role_name" \
        -v has_key="$has_access_key" \
        -v has_secret="$has_secret_key" \
        -v has_reg="$has_region" '
        BEGIN { skip_acc=0; skip_role=0; skip_key=0; skip_secret=0; skip_reg=0 }
        /^AWS_ACCOUNT_ID=/ { if (has_acc) { print "AWS_ACCOUNT_ID=" account_id; skip_acc=1; next } }
        /^AWS_ROLE_NAME=/ { if (has_role) { print "AWS_ROLE_NAME=" role_name; skip_role=1; next } }
        /^AWS_ACCESS_KEY_ID=/ { if (has_key && access_key != "") { print "AWS_ACCESS_KEY_ID=" access_key; skip_key=1; next } }
        /^AWS_SECRET_ACCESS_KEY=/ { if (has_secret && secret_key != "") { print "AWS_SECRET_ACCESS_KEY=" secret_key; skip_secret=1; next } }
        /^AWS_DEFAULT_REGION=/ { if (has_reg) { print "AWS_DEFAULT_REGION=" region; skip_reg=1; next } }
        { print }
        END {
            print ""
            print "# ==========================================="
            print "# AWS Configuration"
            print "# ==========================================="
            if (!skip_acc) print "AWS_ACCOUNT_ID=" account_id
            if (!skip_role) print "AWS_ROLE_NAME=" role_name
            if (access_key != "" && !skip_key) print "AWS_ACCESS_KEY_ID=" access_key
            if (secret_key != "" && !skip_secret) print "AWS_SECRET_ACCESS_KEY=" secret_key
            if (!skip_reg) print "AWS_DEFAULT_REGION=" region
        }
    ' "$ENV_FILE" > "$temp_env"

    mv "$temp_env" "$ENV_FILE"
    chmod 600 "$ENV_FILE"

    print_success "Updated .env file with AWS configuration"

    echo
    print_info "AWS Configuration Summary:"
    echo "  Account ID:     ${AWS_ACCOUNT_ID}"
    echo "  Role Name:      ${ROLE_NAME}"
    echo "  Role ARN:       arn:aws:iam::${AWS_ACCOUNT_ID}:role/${ROLE_NAME}"
    echo "  Region:         ${AWS_REGION}"
    if [[ "$CREATE_USER" == "true" ]]; then
        echo "  Access Key ID:  ${AWS_ACCESS_KEY_ID}"
        echo "  Secret Key:     ${SECRET_KEY_MASK:-[set in .env]}"
    fi
    echo
}

# =============================================================================
# SUMMARY
# =============================================================================

print_summary() {
    print_header "Setup Complete"

    echo -e "${GREEN}AWS configuration completed successfully!${NC}\n"

    echo "Created/Updated Resources:"
    echo "  ├─ IAM Role: ${ROLE_NAME}"
    if [[ "$CREATE_USER" == "true" ]]; then
        echo "  ├─ IAM User: ${USER_NAME}"
    else
        echo "  ├─ IAM User: [using existing credentials]"
    fi
    echo "  └─ .env file updated"
    echo

    echo "Next Steps:"
    echo "  1. Review and update your .env file with AI provider credentials"
    echo "  2. Configure authentication (optional): ./setup-auth.sh"
    echo "  3. Start the application: ./start-dev.sh"
    echo

    print_info "For Docker deployment, the application will use credentials from .env"
    print_info "For local development, AWS credentials from your environment will be used"
    echo

    # Verify role trust relationship
    print_info "Verifying role trust relationship..."
    local trust_policy
    trust_policy=$(aws iam get-role --role-name "$ROLE_NAME" --query 'Role.AssumeRolePolicyDocument' --output json 2>/dev/null)
    if [[ -n "$trust_policy" ]]; then
        echo "  Trusted principals:"
        echo "$trust_policy" | jq -r '.Statement[]? | select(.Principal.AWS != null) | .Principal.AWS | "    - \(.)"' 2>/dev/null || echo "    - sts.amazonaws.com (service)"
    fi
    echo

    # Security reminder
    if [[ "$CREATE_USER" == "true" ]]; then
        print_warning "SECURITY REMINDER:"
        echo "  • Store your AWS credentials securely"
        echo "  • Never commit .env to version control"
        echo "  • Rotate credentials regularly"
        echo "  • Consider using AWS Secrets Manager in production"
        echo
    fi
}

# =============================================================================
# MAIN
# =============================================================================

main() {
    print_header "IAM-Dynamic AWS Setup"

    # Parse command line arguments
    SKIP_USER=false
    for arg in "$@"; do
        case $arg in
            --skip-user)
                SKIP_USER=true
                shift
                ;;
            -h|--help)
                echo "Usage: $0 [--skip-user]"
                echo ""
                echo "Options:"
                echo "  --skip-user    Skip IAM user creation (use existing credentials)"
                echo "  -h, --help     Show this help message"
                exit 0
                ;;
        esac
    done

    print_info "This script will configure AWS resources for IAM-Dynamic"
    print_info "You will be prompted for configuration values with sensible defaults"
    echo

    # Run setup steps
    check_aws_cli
    check_aws_credentials
    create_iam_role
    create_iam_user
    update_env_file
    print_summary

    print_success "Setup completed successfully!"
    exit 0
}

# Run main function
main "$@"
