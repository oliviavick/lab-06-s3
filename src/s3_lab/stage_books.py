
#!/usr/bin/env python3
"""Download books and stage them in a public AWS S3 bucket."""

import json
import logging
import os
import sys
import time

import boto3
import requests
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

s3 = boto3.client("s3", region_name="us-east-1")


def parse_args():
    """Read the book list, index path, and bucket name."""
    if len(sys.argv) < 4:
        log.error("Usage: stage_books.py LIST_FILE INDEX_PATH BUCKET")
        sys.exit(1)
    return sys.argv[1], sys.argv[2], sys.argv[3]


def download_books(list_file, dest_dir):
    """Download Gutenberg books, skipping existing files."""
    os.makedirs(dest_dir, exist_ok=True)
    paths = []

    try:
        with open(list_file, encoding="utf-8") as file:
            urls = [line.strip() for line in file if line.strip()]
    except OSError as error:
        log.error("Cannot read book list: %s", error)
        return paths

    for url in urls:
        filename = url.split("/")[-1]
        path = os.path.join(dest_dir, filename)

        if os.path.exists(path):
            log.info("Already downloaded: %s", filename)
            paths.append(path)
            continue

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            with open(path, "wb") as file:
                file.write(response.content)
            paths.append(path)
            log.info("Downloaded: %s", filename)
            time.sleep(1)
        except (requests.RequestException, OSError) as error:
            log.error("Error downloading %s: %s", url, error)

    return paths


def create_bucket(bucket):
    """Create an S3 bucket unless it already exists."""
    try:
        s3.head_bucket(Bucket=bucket)
        log.info("Bucket already exists: %s", bucket)
        return True
    except ClientError:
        pass

    try:
        s3.create_bucket(Bucket=bucket)
        log.info("Created bucket: %s", bucket)
        return True
    except ClientError as error:
        log.error("Cannot create bucket: %s", error)
        return False


def make_public(bucket):
    """Allow public read access to objects in the bucket."""
    try:
        s3.put_public_access_block(
            Bucket=bucket,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": False,
                "IgnorePublicAcls": False,
                "BlockPublicPolicy": False,
                "RestrictPublicBuckets": False,
            },
        )

        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:GetObject",
                    "Resource": f"arn:aws:s3:::{bucket}/*",
                }
            ],
        }

        s3.put_bucket_policy(Bucket=bucket, Policy=json.dumps(policy))
        log.info("Public access enabled for %s", bucket)
        return True
    except ClientError as error:
        log.error("Cannot make bucket public: %s", error)
        return False


def upload_files(bucket, file_paths):
    """Upload books to the bucket with text content types."""
    uploaded = 0

    for path in file_paths:
        try:
            s3.upload_file(
                path,
                bucket,
                os.path.basename(path),
                ExtraArgs={"ContentType": "text/plain; charset=utf-8"},
            )
            uploaded += 1
            log.info("Uploaded: %s", os.path.basename(path))
        except (ClientError, OSError) as error:
            log.error("Upload failed for %s: %s", path, error)

    return uploaded


def upload_index(bucket, index_path):
    """Upload the HTML index page."""
    try:
        s3.upload_file(
            index_path,
            bucket,
            "index.html",
            ExtraArgs={"ContentType": "text/html"},
        )
        log.info("Uploaded index.html")
        return True
    except (ClientError, OSError) as error:
        log.error("Index upload failed: %s", error)
        return False


def main():
    """Run the book staging workflow."""
    list_file, index_path, bucket = parse_args()

    books = download_books(list_file, "books")
    if not books:
        log.error("No books available to upload.")
        sys.exit(1)

    if not create_bucket(bucket):
        sys.exit(1)

    if not make_public(bucket):
        sys.exit(1)

    uploaded = upload_files(bucket, books)
    index_uploaded = upload_index(bucket, index_path)

    url = f"https://{bucket}.s3.amazonaws.com/index.html"
    if uploaded == len(books) and index_uploaded:
        log.info("Success! Uploaded %d books.", uploaded)
        log.info("Public index: %s", url)
    else:
        log.error("Incomplete upload: %d of %d books.", uploaded, len(books))
        sys.exit(1)


if __name__ == "__main__":
    main()
