import boto3
import os
from botocore.exceptions import NoCredentialsError

s3_client = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_REGION', 'eu-west-1')
)

BUCKET_NAME = os.getenv('S3_BUCKET', 'umukozihr-tailor-artifacts')

def upload_to_s3(local_path: str) -> str:
    """Upload file to S3 and return signed URL"""
    try:
        file_name = os.path.basename(local_path)
        s3_key = f"artifacts/{file_name}"
        
        # upload
        s3_client.upload_file(local_path, BUCKET_NAME, s3_key)
        
        # generate signed URL (7 days expiry)
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': BUCKET_NAME, 'Key': s3_key},
            ExpiresIn=604800  # 7 days
        )
        return url
        
    except NoCredentialsError:
        # fallback to local if S3 not configured
        return f"/artifacts/{os.path.basename(local_path)}"