"""
CodeAlpha — Cloud Computing, Task 1: Data Redundancy Removal System.

What it does (exactly what the task PDF asks for):
  1. Identifies and classifies each new record as UNIQUE, REDUNDANT,
     FALSE POSITIVE (possible duplicate) or INVALID.
  2. Validates new data before it touches the database.
  3. Prevents duplicate data from being added to the cloud database.
  4. Appends ONLY unique + verified records to DynamoDB (AWS, Sydney).

How a record is classified:
  - INVALID        -> fails validation (bad email, missing name, bad phone).
                    Never stored.
  - REDUNDANT      -> SHA-256 hash of the whole record already exists.
                    Exact duplicate. Never stored again.
  - FALSE POSITIVE -> same email already exists, but the rest of the
                    record is DIFFERENT. It *looks* like a duplicate but
                    may be the same person with a new phone, or a shared
                    email. Held for review — NOT auto-appended, NOT
                    auto-deleted. This is the "false positive" case the
                    PDF asks us to classify, not guess at.
  - UNIQUE         -> passes validation, hash new, email new.
                    Appended to DynamoDB.

Hashing: the record is canonicalised first (keys sorted, text stripped
and lower-cased) so " Ali " and "ali" hash the same — otherwise the
same person typed two ways would slip through as "unique".

Run it two ways:
  Local demo (no AWS needed, proves the logic):
      python redundancy.py --local
  Real cloud run (DynamoDB in ap-southeast-2, talal-admin profile):
      python redundancy.py --aws
      python redundancy.py --aws --cleanup     (deletes the table)

Cost: $0 for the demo — a few KB in DynamoDB on-demand (PAY_PER_REQUEST)
in the Free Tier, table deleted after the run. Region is locked to
ap-southeast-2 (Sydney), same as all his other AWS labs.
No credentials in this repo — boto3 uses the AWS CLI profile already
configured on his laptop (`aws configure`, IAM user talal-admin).
"""

import argparse
import hashlib
import json
import re
import sys

TABLE_NAME = "codealpha-redundancy-demo"
REGION = "ap-southeast-2"

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?\d{10,15}$")

# Demo data: 6 records that show every classification.
# 1 unique, 1 exact duplicate, 1 false positive, 1 invalid,
# 1 unique, 1 exact duplicate of #5.
SAMPLE_RECORDS = [
    {"name": "Ahmed Raza", "email": "ahmed.raza@example.com",
     "phone": "+923001234567", "city": "Rawalpindi"},
    {"name": "Ahmed Raza", "email": "ahmed.raza@example.com",
     "phone": "+923001234567", "city": "Rawalpindi"},
    {"name": "Ahmed Raza", "email": "ahmed.raza@example.com",
     "phone": "+923219876543", "city": "Islamabad"},
    {"name": "Sara Khan", "email": "sara.khan-at-example.com",
     "phone": "+923001112223", "city": "Lahore"},
    {"name": "Bilal Hussain", "email": "bilal.h@example.com",
     "phone": "+923334445556", "city": "Karachi"},
    {"name": "Bilal Hussain", "email": "bilal.h@example.com",
     "phone": "+923334445556", "city": "Karachi"},
]


def canonical(record):
    """One fixed form of a record, so the same data always hashes same."""
    clean = {k: (v.strip().lower() if isinstance(v, str) else v)
             for k, v in sorted(record.items())}
    return json.dumps(clean, sort_keys=True)


def record_hash(record):
    return hashlib.sha256(canonical(record).encode("utf-8")).hexdigest()


def validate(record):
    """Verified = required fields present and well-formed. Returns a
    reason string, or None when the record is valid."""
    if not record.get("name") or not str(record["name"]).strip():
        return "missing name"
    if not EMAIL_RE.match(str(record.get("email", ""))):
        return "bad email format"
    if not PHONE_RE.match(str(record.get("phone", "")).replace(" ", "")):
        return "bad phone format (10-15 digits)"
    return None


def classify(record, seen_hashes, seen_emails):
    """Returns (decision, reason). seen_* are what is already stored."""
    problem = validate(record)
    if problem:
        return "INVALID", problem
    h = record_hash(record)
    if h in seen_hashes:
        return "REDUNDANT", "exact duplicate — same hash already stored"
    email = str(record["email"]).strip().lower()
    if email in seen_emails:
        return "FALSE POSITIVE", (
            "same email, different details — held for review, "
            "not auto-appended")
    return "UNIQUE", "verified — new hash, new email"


class LocalStore:
    """In-memory stand-in for DynamoDB, so the logic can be run and
    checked with zero AWS calls."""

    def __init__(self):
        self.items = {}  # hash -> record

    def load_seen(self):
        hashes = set(self.items)
        emails = {r["email"].strip().lower() for r in self.items.values()}
        return hashes, emails

    def append(self, record):
        self.items[record_hash(record)] = record

    def count(self):
        return len(self.items)


class DynamoStore:
    """Real DynamoDB table, on-demand billing, Sydney region."""

    def __init__(self):
        import boto3  # imported here so --local works without boto3
        self.dynamodb = boto3.resource("dynamodb", region_name=REGION)
        self.table = self._get_or_create_table()

    def _get_or_create_table(self):
        client = self.dynamodb.meta.client
        existing = client.list_tables()["TableNames"]
        if TABLE_NAME in existing:
            return self.dynamodb.Table(TABLE_NAME)
        table = self.dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[{"AttributeName": "record_hash", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "record_hash", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
        return table

    def load_seen(self):
        hashes, emails = set(), set()
        resp = self.table.scan(ProjectionExpression="record_hash, email")
        for item in resp.get("Items", []):
            hashes.add(item["record_hash"])
            emails.add(str(item["email"]).strip().lower())
        return hashes, emails

    def append(self, record):
        item = dict(record)
        item["record_hash"] = record_hash(record)
        self.table.put_item(Item=item)

    def count(self):
        # item_count lags (eventually consistent) — count by scan instead.
        return self.table.scan(Select="COUNT")["Count"]

    def cleanup(self):
        self.table.delete()
        self.table.wait_until_not_exists()
        print("Table deleted: " + TABLE_NAME)


def run(store):
    """Feeds the sample records through classify() and stores only the
    unique + verified ones. Prints one line per record + a summary."""
    results = {"UNIQUE": 0, "REDUNDANT": 0, "FALSE POSITIVE": 0, "INVALID": 0}
    for i, record in enumerate(SAMPLE_RECORDS, start=1):
        seen_hashes, seen_emails = store.load_seen()
        decision, reason = classify(record, seen_hashes, seen_emails)
        results[decision] += 1
        if decision == "UNIQUE":
            store.append(record)
            action = "STORED in database"
        elif decision == "REDUNDANT":
            action = "BLOCKED — not stored"
        elif decision == "FALSE POSITIVE":
            action = "HELD for review — not stored"
        else:
            action = "REJECTED — not stored"
        print(f"[{i}] {decision:<14} {record['name']:<15} "
              f"{record['email']:<26} | {reason} | {action}")
    print("\nSummary: " + ", ".join(f"{k}={v}" for k, v in results.items()))
    print(f"Records in database now: {store.count()} "
          f"(expected 2 unique: Ahmed Raza + Bilal Hussain)")
    return results


def main():
    parser = argparse.ArgumentParser(
        description="CodeAlpha Task 1 — Data Redundancy Removal System")
    parser.add_argument("--local", action="store_true",
                        help="run against an in-memory store (no AWS)")
    parser.add_argument("--aws", action="store_true",
                        help="run against DynamoDB in ap-southeast-2")
    parser.add_argument("--cleanup", action="store_true",
                        help="delete the DynamoDB table and exit")
    args = parser.parse_args()

    if args.cleanup:
        DynamoStore().cleanup()
        return 0
    if args.aws:
        print(f"Mode: AWS DynamoDB | table={TABLE_NAME} | region={REGION}\n")
        run(DynamoStore())
    else:
        print("Mode: LOCAL demo (no AWS calls — logic check only)\n")
        run(LocalStore())
    return 0


if __name__ == "__main__":
    sys.exit(main())
