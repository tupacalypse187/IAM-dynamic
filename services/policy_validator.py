"""
AWS IAM policy validation service
"""
import logging
from typing import Dict, Any, List, Tuple

logger = logging.getLogger(__name__)


class PolicyValidationError(Exception):
    """Raised when policy validation fails"""
    pass


class PolicyValidator:
    """
    Validate IAM policies against AWS best practices

    Provides static methods for policy structure validation,
    risk assessment, and improvement suggestions.
    """

    # High-risk actions that require special scrutiny
    HIGH_RISK_ACTIONS = {
        "iam:*", "iam:CreateUser", "iam:CreateAccessKey", "iam:PutUserPolicy",
        "iam:AttachRolePolicy", "iam:PutRolePolicy",
        "ec2:*", "s3:*", "lambda:*", "dynamodb:*",
        "sts:*", "kms:*", "secretsmanager:*",
        "ec2:TerminateInstances", "ec2:DeleteVolume"
    }

    # Actions that should never be wildcarded
    NEVER_WILDCARD = {
        "iam:DeleteUser", "iam:DeleteRole", "iam:DeletePolicy",
        "iam:AttachRolePolicy", "iam:PutRolePolicy",
        "ec2:TerminateInstances", "ec2:DeleteVolume",
        "s3:DeleteBucket", "s3:PutBucketPolicy",
        "lambda:DeleteFunction",
        "dynamodb:DeleteTable", "dynamodb:DeleteItem"
    }

    @staticmethod
    def validate_policy_structure(policy: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate policy has required fields

        Args:
            policy: IAM policy document

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        if not isinstance(policy, dict):
            errors.append("Policy must be a dictionary")
            return False, errors

        if "Version" not in policy:
            errors.append("Missing required field: Version")

        if "Statement" not in policy:
            errors.append("Missing required field: Statement")
            return False, errors

        if not isinstance(policy["Statement"], list):
            errors.append("Statement must be a list")
            return False, errors

        if len(policy["Statement"]) == 0:
            errors.append("Statement list cannot be empty")

        # Validate each statement
        for i, stmt in enumerate(policy["Statement"]):
            if not isinstance(stmt, dict):
                errors.append(f"Statement {i} must be a dictionary")
                continue

            if "Effect" not in stmt:
                errors.append(f"Statement {i} missing required field: Effect")

            if "Action" not in stmt:
                errors.append(f"Statement {i} missing required field: Action")

        return len(errors) == 0, errors

    @staticmethod
    def check_wildcard_risk(policy: Dict[str, Any]) -> List[str]:
        """
        Check for wildcard usage and assess risk

        Args:
            policy: IAM policy document

        Returns:
            List of warnings about wildcard usage
        """
        warnings = []

        for stmt in policy.get("Statement", []):
            effect = stmt.get("Effect", "")
            if effect != "Allow":
                continue

            actions = stmt.get("Action", [])
            if isinstance(actions, str):
                actions = [actions]

            resources = stmt.get("Resource", [])
            if isinstance(resources, str):
                resources = [resources]

            # Check for resource wildcarding
            if "*" in resources and actions:
                action_str = ", ".join(actions[:3])
                if len(actions) > 3:
                    action_str += f" (+{len(actions) - 3} more)"
                warnings.append(f"⚠️ Resource wildcard (*) used with actions: {action_str}")

            # Check for action wildcarding
            for action in actions:
                if action == "*" or action.endswith(":*"):
                    warnings.append(f"🔴 Action wildcard detected: {action}")
                elif action in PolicyValidator.NEVER_WILDCARD:
                    warnings.append(f"🚨 High-risk action (should never wildcard): {action}")

        return warnings

    @staticmethod
    def assess_policy_risk(policy: Dict[str, Any]) -> Tuple[str, List[str]]:
        """
        Assess overall policy risk level

        Args:
            policy: IAM policy document

        Returns:
            Tuple of (risk_level, list_of_reasons)
        """
        warnings = PolicyValidator.check_wildcard_risk(policy)
        reasons = []

        # Count high-risk actions
        high_risk_count = 0
        total_actions = 0

        for stmt in policy.get("Statement", []):
            if stmt.get("Effect") != "Allow":
                continue

            actions = stmt.get("Action", [])
            if isinstance(actions, str):
                actions = [actions]

            for action in actions:
                total_actions += 1

                # Check if action is high-risk
                for high_risk in PolicyValidator.HIGH_RISK_ACTIONS:
                    if action == high_risk or (
                        high_risk.endswith("*") and action.startswith(high_risk.rstrip("*"))
                    ):
                        high_risk_count += 1
                        break

        # Determine risk level
        if total_actions == 0:
            risk = "low"
        elif high_risk_count == 0 and "*" not in str(policy):
            risk = "low"
            reasons.append("No high-risk actions detected")
        elif high_risk_count <= 2 and "*" not in str(policy):
            risk = "medium"
            reasons.append(f"{high_risk_count} high-risk action(s) detected")
        elif "*" in str(policy) or high_risk_count > 2:
            risk = "high"
            if "*" in str(policy):
                reasons.append("Wildcard permissions detected")
            if high_risk_count > 2:
                reasons.append(f"{high_risk_count} high-risk actions detected")
        else:
            risk = "critical"
            reasons.append("Multiple high-risk indicators")

        if warnings:
            reasons.extend(warnings[:3])  # Limit to top 3

        return risk, reasons

    @staticmethod
    def suggest_policy_improvements(policy: Dict[str, Any]) -> List[str]:
        """
        Suggest improvements to reduce policy risk

        Args:
            policy: IAM policy document

        Returns:
            List of improvement suggestions
        """
        suggestions = []

        for stmt in policy.get("Statement", []):
            if stmt.get("Effect") != "Allow":
                continue

            actions = stmt.get("Action", [])
            resources = stmt.get("Resource", [])

            if isinstance(resources, str):
                resources = [resources]

            # Suggest specific resources
            if "*" in resources and len(actions) > 0:
                service = actions[0].split(":")[0] if ":" in str(actions[0]) else "unknown"
                suggestions.append(
                    f"Consider limiting resources to specific ARNs for {service} "
                    f"(e.g., 'arn:aws:{service}::*:resource-name/*')"
                )

            # Suggest reducing action scope
            if "*" in str(actions):
                suggestions.append(
                    "Replace wildcard actions with specific actions needed for the task"
                )

            # Suggest adding conditions
            if "Condition" not in stmt:
                suggestions.append(
                    "Consider adding Condition constraints (e.g., IP restrictions, time-based access)"
                )

        return suggestions

    @staticmethod
    def analyze_policy_permissions(policy: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze policy to extract permission details

        Args:
            policy: IAM policy document

        Returns:
            Dictionary with analysis results
        """
        services = set()
        actions = []
        resource_patterns = []

        for stmt in policy.get("Statement", []):
            if stmt.get("Effect") != "Allow":
                continue

            stmt_actions = stmt.get("Action", [])
            if isinstance(stmt_actions, str):
                stmt_actions = [stmt_actions]

            for action in stmt_actions:
                actions.append(action)
                if isinstance(action, str) and ":" in action:
                    service = action.split(":")[0]
                    services.add(service)

            stmt_resources = stmt.get("Resource", [])
            if isinstance(stmt_resources, str):
                stmt_resources = [stmt_resources]

            for resource in stmt_resources:
                resource_patterns.append(resource)

        return {
            "services": sorted(list(services)),
            "action_count": len(actions),
            "unique_actions": len(set(actions)),
            "resource_patterns": resource_patterns,
            "has_wildcard_resource": "*" in resource_patterns,
            "has_wildcard_action": any(a == "*" or a.endswith(":*") for a in actions)
        }
