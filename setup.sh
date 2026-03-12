#!/bin/bash
# =============================================================================
# IAM-Dynamic Master Setup Script
# =============================================================================
# Interactive first-time setup for IAM-Dynamic
#
# This script orchestrates the complete setup process:
#   1. Checks prerequisites
#   2. Runs AWS setup (role, user, credentials)
#   3. Runs Auth setup (password, JWT, LLM provider)
#   4. Validates configuration
#   5. Offers to start the application
#
# Usage:
#   ./setup.sh          # Interactive setup
#   ./setup.sh --quick  # Quick setup with defaults
#   ./setup.sh --ci     # CI/CD friendly (no prompts)
#   ./setup.sh --skip-aws  # Skip AWS setup
#   ./setup.sh --skip-auth # Skip auth setup
# =============================================================================

set -euo pipefail

# =============================================================================
# SCRIPT CONFIGURATION
# =============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Color codes
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly CYAN='\033[0;36m'
readonly MAGENTA='\033[0;35m'
readonly BOLD='\033[1m'
readonly NC='\033[0m' # No Color

# Flags
QUICK_MODE=false
CI_MODE=false
SKIP_AWS=false
SKIP_AUTH=false
START_APP=false

# =============================================================================
# CLEANUP HANDLERS
# =============================================================================

cleanup() {
    local exit_code=$?
    if [[ $exit_code -ne 0 ]]; then
        echo -e "\n${RED}✗ Setup failed with exit code ${exit_code}${NC}"
        echo -e "${YELLOW}Please review the error messages above.${NC}"
    fi
}

trap cleanup EXIT
trap 'echo -e "\n${YELLOW}Setup interrupted by user${NC}"; exit 130' INT

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

print_header() {
    echo -e "\n${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  ${BOLD}$1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
}

print_step() {
    echo -e "\n${BLUE}▶ $1${NC}"
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

confirm() {
    local prompt="$1"
    local default="${2:-n}"

    if [[ "$CI_MODE" == "true" ]]; then
        # In CI mode, default to yes for confirmations
        return 0
    fi

    if [[ "$QUICK_MODE" == "true" ]]; then
        # In quick mode, default to yes
        return 0
    fi

    local response
    if [[ "$default" == "y" ]]; then
        prompt="${prompt} [Y/n]"
    else
        prompt="${prompt} [y/N]"
    fi

    read -rp "$(echo -e "${YELLOW}${prompt}? ${NC}")" response
    response="${response:-$default}"

    [[ "$response" =~ ^[Yy]$ ]]
}

# =============================================================================
# PREREQUISITE CHECKS
# =============================================================================

check_command() {
    local cmd="$1"
    local name="${2:-$cmd}"
    local install_hint="${3:-}"

    if command -v "$cmd" &>/dev/null; then
        print_success "$name is installed"
        return 0
    else
        print_error "$name is not installed"
        if [[ -n "$install_hint" ]]; then
            echo -e "  ${YELLOW}Install: $install_hint${NC}"
        fi
        return 1
    fi
}

check_prerequisites() {
    print_header "Checking Prerequisites"

    local missing=0

    # Required commands
    check_command "python3" "Python 3" "brew install python3 / apt install python3" || missing=$((missing + 1))
    check_command "node" "Node.js" "brew install node / apt install nodejs" || missing=$((missing + 1))
    check_command "npm" "npm" "Comes with Node.js" || missing=$((missing + 1))

    # Optional but recommended
    echo
    print_info "Optional (but recommended):"
    if ! check_command "docker" "Docker" "https://docs.docker.com/desktop/install/"; then
        print_warning "Docker is recommended for containerized deployment"
    fi
    if ! check_command "aws" "AWS CLI" "brew install awscli / apt install awscli"; then
        if [[ "$SKIP_AWS" != "true" ]]; then
            print_warning "AWS CLI is required for AWS setup. Use --skip-aws to skip."
            missing=$((missing + 1))
        fi
    fi

    if [[ $missing -gt 0 ]]; then
        echo -e "\n${RED}Missing $missing required prerequisite(s). Please install them and run again.${NC}"
        exit 1
    fi

    echo
    print_success "All prerequisites met!"
}

# =============================================================================
# SETUP SCRIPT HELPERS
# =============================================================================

run_aws_setup() {
    if [[ "$SKIP_AWS" == "true" ]]; then
        print_info "Skipping AWS setup (--skip-aws flag)"
        return 0
    fi

    print_step "Running AWS Setup"

    local aws_script="${SCRIPT_DIR}/setup-aws.sh"
    if [[ ! -f "$aws_script" ]]; then
        print_error "setup-aws.sh not found in ${SCRIPT_DIR}"
        return 1
    fi

    if [[ "$CI_MODE" == "true" ]]; then
        bash "$aws_script" --skip-user </dev/null
    elif [[ "$QUICK_MODE" == "true" ]]; then
        # In quick mode, use defaults (press Enter through prompts)
        yes "" | bash "$aws_script" 2>/dev/null || bash "$aws_script"
    else
        bash "$aws_script"
    fi

    print_success "AWS setup complete"
}

run_auth_setup() {
    if [[ "$SKIP_AUTH" == "true" ]]; then
        print_info "Skipping Auth setup (--skip-auth flag)"
        return 0
    fi

    print_step "Running Auth & LLM Provider Setup"

    local auth_script="${SCRIPT_DIR}/setup-auth.sh"
    if [[ ! -f "$auth_script" ]]; then
        print_error "setup-auth.sh not found in ${SCRIPT_DIR}"
        return 1
    fi

    local mode="dev"
    if confirm "Configure for production deployment (Caddy HTTPS, Turnstile)?" "n"; then
        mode="prod"
    fi

    if [[ "$CI_MODE" == "true" ]]; then
        bash "$auth_script" "--${mode}" </dev/null
    elif [[ "$QUICK_MODE" == "true" ]]; then
        # Provide defaults for quick mode
        echo -e "1\n" | bash "$auth_script" "--${mode}" 2>/dev/null || bash "$auth_script" "--${mode}"
    else
        bash "$auth_script" "--${mode}"
    fi

    print_success "Auth setup complete"
}

# =============================================================================
# CONFIGURATION VALIDATION
# =============================================================================

validate_env_file() {
    print_step "Validating Configuration"

    local env_file="${SCRIPT_DIR}/.env"
    if [[ ! -f "$env_file" ]]; then
        print_error ".env file not found!"
        print_info "Run setup scripts first to create .env"
        return 1
    fi

    # Source the env file to check variables
    # Note: This is a simple check, not a full validation
    local missing_vars=()
    local warnings=()

    # Check required variables
    grep -q "^LLM_PROVIDER=" "$env_file" 2>/dev/null || missing_vars+=("LLM_PROVIDER")

    # Check provider-specific variables
    local provider
    provider=$(grep "^LLM_PROVIDER=" "$env_file" 2>/dev/null | cut -d'=' -f2)
    case "$provider" in
        gemini)
            grep -q "^GOOGLE_API_KEY=" "$env_file" 2>/dev/null || warnings+=("GOOGLE_API_KEY (Gemini provider selected)")
            ;;
        openai)
            grep -q "^OPENAI_API_KEY=" "$env_file" 2>/dev/null || warnings+=("OPENAI_API_KEY (OpenAI provider selected)")
            ;;
        anthropic|claude)
            grep -q "^ANTHROPIC_API_KEY=" "$env_file" 2>/dev/null || warnings+=("ANTHROPIC_API_KEY (Anthropic provider selected)")
            ;;
        zhipu|glm)
            grep -q "^ZAI_API_KEY=" "$env_file" 2>/dev/null || warnings+=("ZAI_API_KEY (Zhipu provider selected)")
            ;;
    esac

    # Check AWS variables
    if ! grep -q "^AWS_ACCOUNT_ID=" "$env_file" 2>/dev/null; then
        if [[ "$SKIP_AWS" != "true" ]]; then
            missing_vars+=("AWS_ACCOUNT_ID")
        fi
    fi

    # Check auth variables (optional but good for production)
    if ! grep -q "^AUTH_PASSWORD_HASH=" "$env_file" 2>/dev/null; then
        warnings+=("AUTH_PASSWORD_HASH (authentication disabled - OK for dev)")
    fi

    # Report results
    if [[ ${#missing_vars[@]} -gt 0 ]]; then
        print_error "Missing required variables:"
        for var in "${missing_vars[@]}"; do
            echo "  - ${RED}$var${NC}"
        done
        return 1
    fi

    if [[ ${#warnings[@]} -gt 0 ]]; then
        print_warning "Notes:"
        for warning in "${warnings[@]}"; do
            echo "  - $warning"
        done
    fi

    print_success "Configuration validated!"
    return 0
}

# =============================================================================
# APPLICATION STARTUP
# =============================================================================

offer_app_startup() {
    print_step "Application Startup"

    echo "Choose how to start the application:"
    echo "  1) Docker Compose (recommended for testing)"
    echo "  2) Development mode (backend + frontend separately)"
    echo "  3) Skip (I'll start it manually)"
    echo

    if [[ "$CI_MODE" == "true" ]]; then
        print_info "CI mode: Skipping startup prompt"
        return 0
    fi

    local choice
    read -rp "Select option [1-3]: " choice
    choice="${choice:-3}"

    case "$choice" in
        1|docker)
            print_info "Starting with Docker Compose..."
            if command -v docker-compose &>/dev/null; then
                docker-compose up --build
            elif docker compose version &>/dev/null; then
                docker compose up --build
            else
                print_error "Docker Compose not found"
                return 1
            fi
            ;;
        2|dev)
            print_info "Starting development servers..."
            bash "${SCRIPT_DIR}/start-dev.sh"
            ;;
        3|skip|"")
            print_info "Skipping startup. You can start manually:"
            echo "  Docker: docker compose up --build"
            echo "  Dev:    ./start-dev.sh"
            ;;
        *)
            print_warning "Invalid choice. Skipping startup."
            ;;
    esac
}

# =============================================================================
# SUMMARY
# =============================================================================

print_summary() {
    print_header "Setup Complete!"

    echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║     IAM-Dynamic is ready to use! 🎉              ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
    echo

    # Show what was configured
    echo "Configuration:"
    echo "  ├─ .env file: ${GREEN}Created${NC}"
    if [[ "$SKIP_AWS" != "true" ]]; then
        echo "  ├─ AWS setup: ${GREEN}Complete${NC}"
    fi
    if [[ "$SKIP_AUTH" != "true" ]]; then
        echo "  ├─ Auth setup: ${GREEN}Complete${NC}"
    fi
    echo "  └─ Validation: ${GREEN}Passed${NC}"
    echo

    # Next steps
    echo "Next Steps:"
    echo "  1. Review your .env file and add any missing API keys"
    echo "  2. Start the application:"
    echo "     ${CYAN}docker compose up --build${NC}     # Docker"
    echo "     ${CYAN}./start-dev.sh${NC}                 # Dev mode"
    echo
    echo "  3. Open your browser:"
    echo "     ${CYAN}http://localhost:8080${NC}           # Docker"
    echo "     ${CYAN}http://localhost:3000${NC}           # Dev mode"
    echo

    # Documentation links
    echo "Documentation:"
    echo "  ├─ ${CYAN}docs/GETTING-STARTED.md${NC}  - Quick start guide"
    echo "  ├─ ${CYAN}docs/AWS-SETUP.md${NC}         - AWS configuration"
    echo "  ├─ ${CYAN}docs/local-docker-testing.md${NC} - Docker testing"
    echo "  └─ ${CYAN}README.md${NC}                  - Project overview"
    echo
}

# =============================================================================
# HELP
# =============================================================================

show_help() {
    cat << EOF
${BOLD}IAM-Dynamic Master Setup Script${NC}

${CYAN}Usage:${NC}
  ./setup.sh [options]

${CYAN}Options:${NC}
  -h, --help       Show this help message
  -q, --quick      Quick setup with defaults (fewer prompts)
  -c, --ci         CI/CD mode (no prompts, auto-confirm)
  --skip-aws       Skip AWS setup steps
  --skip-auth      Skip authentication setup steps

${CYAN}Examples:${NC}
  ./setup.sh              # Interactive guided setup
  ./setup.sh --quick      # Quick setup with sensible defaults
  ./setup.sh --ci         # Automated setup for CI/CD
  ./setup.sh --skip-aws   # Skip AWS (if already configured)

${CYAN}What this script does:${NC}
  1. Checks prerequisites (Python, Node.js, Docker, AWS CLI)
  2. Runs AWS setup (creates IAM role, user, credentials)
  3. Runs Auth setup (password, JWT, LLM provider selection)
  4. Validates configuration
  5. Offers to start the application

EOF
}

# =============================================================================
# MAIN
# =============================================================================

main() {
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -q|--quick)
                QUICK_MODE=true
                shift
                ;;
            -c|--ci)
                CI_MODE=true
                shift
                ;;
            --skip-aws)
                SKIP_AWS=true
                shift
                ;;
            --skip-auth)
                SKIP_AUTH=true
                shift
                ;;
            *)
                echo "Unknown option: $1"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done

    # Print banner
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════════════════════════════╗"
    echo "║                                                               ║"
    echo "║         ${BOLD}IAM-Dynamic First-Time Setup${NC}${CYAN}                      ║"
    echo "║                                                               ║"
    echo "╚═══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"

    # Run setup steps
    check_prerequisites
    run_aws_setup
    run_auth_setup
    validate_env_file

    # Show summary and offer startup
    print_summary

    if [[ "$CI_MODE" != "true" ]]; then
        offer_app_startup
    fi

    print_success "Setup completed successfully!"
    exit 0
}

# Run main
main "$@"
