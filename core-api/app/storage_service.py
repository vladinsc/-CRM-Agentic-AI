import os
import uuid
import boto3
from botocore.exceptions import ClientError

class StorageService:
    def __init__(self):
        self.endpoint = os.getenv("MINIO_ENDPOINT")
        self.access_key = os.getenv("MINIO_ACCESS_KEY")
        self.secret_key = os.getenv("MINIO_SECRET_KEY")
        self.bucket_name = os.getenv("MINIO_BUCKET_NAME", "client-emails")

        self.s3_client = boto3.client(
            's3',
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name='us-east-1'
        )
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        """Verifica daca bucket-ul exista. Daca nu, il creeaza."""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                print(f"Creare bucket nou in MinIO: {self.bucket_name}")
                self.s3_client.create_bucket(Bucket=self.bucket_name)
            else:
                raise e

    def upload_email(self,user_id: int, project_id: int, raw_html_content: str) -> str:
        """
        Incarca continutul email-ului in S3Bucket si returneaza calea pentru baza de date.
        """
        # Generam un ID unic pentru fisier (ex: msg_abc123.html) ca sa nu suprascriem mailuri
        unique_id = uuid.uuid4().hex[:16]
        file_name = f"users/{user_id}/projects/{project_id}/msg_{unique_id}.html"

        # Incarcam string-ul direct ca fisier in MinIO
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=file_name,
            Body=raw_html_content.encode('utf-8'),
            ContentType='text/html'
        )

        # Returnam calea exacta (ex: client-emails/projects/12/msg_abc123.html)
        return f"{self.bucket_name}/{file_name}"