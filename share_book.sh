
#!/bin/bash
set -euo pipefail

# Check for three required arguments.
if [ "$#" -ne 3 ]; then
    echo "Usage: $0 BOOK_URL BUCKET EXPIRATION_SECONDS"
    exit 1
fi

URL="$1"
BUCKET="$2"
EXPIRATION="$3"

# Create the local books directory.
mkdir -p books

# Keep the filename from the URL.
FILENAME="${URL##*/}"
FILE_PATH="books/$FILENAME"

# Download the selected book.
curl -fL "$URL" -o "$FILE_PATH"

# Create the private bucket if necessary.
if ! aws s3 ls "s3://$BUCKET" > /dev/null 2>&1; then
    aws s3 mb "s3://$BUCKET" --region us-east-1
fi

# Upload the book without making it public.
aws s3 cp "$FILE_PATH" "s3://$BUCKET/$FILENAME" \
    --content-type "text/plain; charset=utf-8"

# Generate a temporary URL to the private book.
echo "Presigned URL:"
aws s3 presign "s3://$BUCKET/$FILENAME" \
    --expires-in "$EXPIRATION"
