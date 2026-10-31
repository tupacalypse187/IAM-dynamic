#!/usr/bin/env bash
# Create (or update) the on-demand Windows packaging project in CodeBuild.
#
# Usage:
#   BUCKET=my-release-bucket ROLE_ARN=arn:aws:iam::123:role/CodeBuildWindows \
#     FEED_URL=https://releases.example.com/desktop \
#     ./desktop/scripts/setup-codebuild.sh
#
# Prerequisites: aws CLI authenticated; BUCKET already exists; ROLE_ARN
# trusts codebuild.amazonaws.com and can read/write BUCKET plus write
# CloudWatch Logs. Nothing in this script starts a build — builds are
# started manually (`aws codebuild start-build`) or from CI on release tags.
set -euo pipefail

: "${BUCKET:?Set BUCKET to the S3 bucket for release artifacts}"
: "${ROLE_ARN:?Set ROLE_ARN to the CodeBuild service role ARN}"
: "${FEED_URL:?Set FEED_URL to the public URL serving the artifacts}"

PROJECT="${PROJECT_NAME:-iam-dynamic-desktop-windows}"
REPO_URL="$(git config --get remote.origin.url)"
BRANCH="${SOURCE_BRANCH:-main}"

echo "Configuring CodeBuild project: ${PROJECT}"

aws codebuild create-project \
  --name "${PROJECT}" \
  --source "type=GITHUB,location=${REPO_URL},buildspec=desktop/buildspec-windows.yml,gitCloneDepth=1" \
  --source-version "${BRANCH}" \
  --artifacts "type=S3,location=${BUCKET}/desktop,packaging=NONE,overrideArtifactName=false" \
  --cache "type=S3,location=${BUCKET}/codebuild-cache/desktop-windows" \
  --environment "type=WINDOWS_SERVER_2022_CONTAINER,computeType=BUILD_GENERAL1_MEDIUM,image=aws/codebuild/windows-base:2022-1.0,privilegedMode=false,environmentVariables=[{name=UPDATE_FEED_URL,value=${FEED_URL},type=PLAINTEXT}]" \
  --service-role "${ROLE_ARN}" \
  --timeout-in-minutes 30 \
  --queued-timeout-in-minutes 60 \
  >/dev/null && echo "Created ${PROJECT}." \
  || aws codebuild update-project \
    --name "${PROJECT}" \
    --source "type=GITHUB,location=${REPO_URL},buildspec=desktop/buildspec-windows.yml,gitCloneDepth=1" \
    --artifacts "type=S3,location=${BUCKET}/desktop,packaging=NONE,overrideArtifactName=false" \
    --cache "type=S3,location=${BUCKET}/codebuild-cache/desktop-windows" \
    --environment "type=WINDOWS_SERVER_2022_CONTAINER,computeType=BUILD_GENERAL1_MEDIUM,image=aws/codebuild/windows-base:2022-1.0,privilegedMode=false,environmentVariables=[{name=UPDATE_FEED_URL,value=${FEED_URL},type=PLAINTEXT}]" \
    --service-role "${ROLE_ARN}" \
    --timeout-in-minutes 30 \
    --queued-timeout-in-minutes 60 \
  >/dev/null && echo "Updated ${PROJECT}."

echo "Start a build with: aws codebuild start-build --project-name ${PROJECT}"
