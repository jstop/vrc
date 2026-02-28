"""
One-time migration: backfill existing DynamoDB items with handle, gsi1pk, gsi1sk
so they appear in the feed GSI.

Usage:
  DYNAMODB_TABLE=<table-name> python migrate_feed_gsi.py
"""

import os
import boto3

TABLE_NAME = os.environ.get("DYNAMODB_TABLE")
if not TABLE_NAME:
    print("Set DYNAMODB_TABLE env var first.")
    raise SystemExit(1)

ddb = boto3.resource("dynamodb")
table = ddb.Table(TABLE_NAME)

scan_kwargs = {
    "FilterExpression": "pk = :pk",
    "ExpressionAttributeValues": {":pk": "ANALYSIS"},
}

updated = 0
scanned = 0

while True:
    resp = table.scan(**scan_kwargs)
    items = resp.get("Items", [])
    scanned += len(items)

    for item in items:
        sk = item["sk"]
        needs_update = False
        update_expr_parts = []
        attr_values = {}

        if "gsi1pk" not in item:
            update_expr_parts.append("gsi1pk = :feedpk")
            attr_values[":feedpk"] = "FEED"
            needs_update = True

        if "gsi1sk" not in item:
            update_expr_parts.append("gsi1sk = :sk")
            attr_values[":sk"] = sk
            needs_update = True

        if "handle" not in item:
            update_expr_parts.append("handle = :h")
            attr_values[":h"] = "anon"
            needs_update = True

        if needs_update:
            table.update_item(
                Key={"pk": "ANALYSIS", "sk": sk},
                UpdateExpression="SET " + ", ".join(update_expr_parts),
                ExpressionAttributeValues=attr_values,
            )
            updated += 1
            print(f"  Updated {sk}")

    if "LastEvaluatedKey" not in resp:
        break
    scan_kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

print(f"\nDone. Scanned {scanned} items, updated {updated}.")
