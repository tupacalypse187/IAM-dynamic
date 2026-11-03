"""Policy summary helper tests (notification card grants)."""
from services.policy_summary import (
    policy_actions,
    policy_resources,
    privilege_level,
    short_resource,
    summarize_policy,
)


POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": ["s3:GetObject", "s3:ListBucket"],
            "Resource": ["arn:aws:s3:::team-bucket", "arn:aws:s3:::logs-bucket/*"],
        },
        {
            "Effect": "Allow",
            "Action": ["s3:GetObject"],
            "Resource": ["arn:aws:s3:::team-bucket"],
        },
    ],
}


class TestPolicySummary:
    def test_actions_deduped_in_order(self):
        assert policy_actions(POLICY) == ["s3:GetObject", "s3:ListBucket"]

    def test_resources_deduped_in_order(self):
        assert policy_resources(POLICY) == [
            "arn:aws:s3:::team-bucket",
            "arn:aws:s3:::logs-bucket/*",
        ]

    def test_short_resource_arn_to_service_name(self):
        assert short_resource("arn:aws:s3:::team-bucket") == "s3:team-bucket"
        assert short_resource("*") == "*"
        assert short_resource("some-bucket") == "some-bucket"

    def test_summarize_counts_and_names(self):
        summary = summarize_policy(POLICY)
        assert "2 actions" in summary
        assert "s3:GetObject" in summary and "s3:ListBucket" in summary
        assert "2 resources" in summary
        assert "s3:team-bucket" in summary

    def test_summarize_truncates_with_more(self):
        policy = {
            "Statement": [
                {
                    "Action": [f"s3:Action{i}" for i in range(10)],
                    "Resource": [f"arn:aws:s3:::bucket-{i}" for i in range(6)],
                }
            ]
        }
        summary = summarize_policy(policy)
        assert "+4 more" in summary
        assert "+2 more" in summary

    def test_summarize_empty_policy(self):
        assert summarize_policy({}) == "No granted actions recorded."
        assert summarize_policy(None) == "No granted actions recorded."

    def test_privilege_levels(self):
        assert privilege_level(["iam:CreateUser"]) == "admin-level"
        assert privilege_level(["s3:DeleteObject"]) == "admin-level"
        assert privilege_level(["s3:*"]) == "admin-level"
        assert privilege_level(["dynamodb:PutItem"]) == "admin-level"
        assert privilege_level(["dynamodb:UpdateItem"]) == "write-level"
        assert privilege_level(["s3:GetObject", "s3:ListBucket"]) == "read-only"
        assert privilege_level([]) == "mixed"
