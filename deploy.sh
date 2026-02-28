#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# VRC Manual Deploy Script
# Builds a Lambda deployment zip, uploads to S3, updates Lambda, health-checks.
# ---------------------------------------------------------------------------

FUNCTION_NAME="vrc-app"
S3_BUCKET="osmio.routinebuilders.com"
S3_KEY="lambda-packages/vrc/lambda.zip"
HEALTH_URL="https://vrc.routinebuilders.com/health"

echo "=== VRC Deploy ==="

# 1. Build in a temp directory
BUILD_DIR=$(mktemp -d)
trap 'rm -rf "$BUILD_DIR"' EXIT

echo "→ Installing dependencies to $BUILD_DIR/package ..."
pip install \
    --target "$BUILD_DIR/package" \
    --platform manylinux2014_x86_64 \
    --only-binary=:all: \
    --implementation cp \
    --python-version 3.12 \
    -r requirements.txt \
    --quiet

echo "→ Copying application files ..."
cp app.py dung_solver.py "$BUILD_DIR/package/"
cp -r templates "$BUILD_DIR/package/"

echo "→ Creating zip ..."
(cd "$BUILD_DIR/package" && zip -r9 "$BUILD_DIR/lambda.zip" . -q)

ZIP_SIZE=$(du -h "$BUILD_DIR/lambda.zip" | cut -f1)
echo "  Zip size: $ZIP_SIZE"

# 2. Upload to S3
echo "→ Uploading to s3://$S3_BUCKET/$S3_KEY ..."
aws s3 cp "$BUILD_DIR/lambda.zip" "s3://$S3_BUCKET/$S3_KEY"

# 3. Update Lambda function code
echo "→ Updating Lambda function $FUNCTION_NAME ..."
aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" \
    --s3-bucket "$S3_BUCKET" \
    --s3-key "$S3_KEY" \
    --no-cli-pager

echo "→ Waiting for function to become active ..."
aws lambda wait function-active-v2 --function-name "$FUNCTION_NAME"

# 4. Health check
echo "→ Running health check ..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL")
if [ "$HTTP_CODE" = "200" ]; then
    echo "✓ Health check passed (HTTP $HTTP_CODE)"
    exit 0
else
    echo "✗ Health check failed (HTTP $HTTP_CODE)"
    exit 1
fi
