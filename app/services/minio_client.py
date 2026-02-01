"""MinIO client service for video storage operations."""

import logging
from datetime import timedelta
from functools import lru_cache

from minio import Minio
from minio.error import S3Error

from app.config import settings

logger = logging.getLogger(__name__)


class MinioClient:
    """Client for interacting with MinIO storage."""

    def __init__(self):
        """Initialize the MinIO client lazily."""
        self._client: Minio | None = None

    @property
    def client(self) -> Minio:
        """Get or create the MinIO client."""
        if self._client is None:
            self._client = Minio(
                endpoint=settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_SECURE,
            )
        return self._client

    def list_buckets(self) -> list[dict]:
        """List all available buckets.

        Returns:
            List of bucket information dicts with name and creation_date.
        """
        try:
            buckets = self.client.list_buckets()
            return [
                {
                    "name": bucket.name,
                    "creation_date": bucket.creation_date.isoformat() if bucket.creation_date else None,
                }
                for bucket in buckets
            ]
        except S3Error as e:
            logger.error(f"Error listing buckets: {e}")
            raise

    def bucket_exists(self, bucket_name: str) -> bool:
        """Check if a bucket exists.

        Args:
            bucket_name: Name of the bucket to check.

        Returns:
            True if the bucket exists, False otherwise.
        """
        try:
            return self.client.bucket_exists(bucket_name)
        except S3Error as e:
            logger.error(f"Error checking bucket existence: {e}")
            raise

    def list_videos(self, bucket_name: str) -> list[dict]:
        """List all .mp4 video files in a bucket.

        Args:
            bucket_name: Name of the bucket to list videos from.

        Returns:
            List of video information dicts with name, size, and last_modified.
        """
        try:
            objects = self.client.list_objects(bucket_name, recursive=True)
            videos = []
            for obj in objects:
                if obj.object_name and obj.object_name.lower().endswith(".mp4"):
                    videos.append({
                        "name": obj.object_name,
                        "size": obj.size,
                        "last_modified": obj.last_modified.isoformat() if obj.last_modified else None,
                    })
            return videos
        except S3Error as e:
            logger.error(f"Error listing videos in bucket {bucket_name}: {e}")
            raise

    def validate_bucket_for_video_distribution(self, bucket_name: str) -> dict:
        """Validate that a bucket exists and contains videos.

        Args:
            bucket_name: Name of the bucket to validate.

        Returns:
            Dict with validation results including is_valid, video_count, and any errors.
        """
        result = {
            "bucket_name": bucket_name,
            "is_valid": False,
            "exists": False,
            "video_count": 0,
            "error": None,
        }

        try:
            # Check bucket exists
            if not self.bucket_exists(bucket_name):
                result["error"] = f"Bucket '{bucket_name}' does not exist"
                return result

            result["exists"] = True

            # Count videos
            videos = self.list_videos(bucket_name)
            result["video_count"] = len(videos)

            if result["video_count"] == 0:
                result["error"] = f"Bucket '{bucket_name}' contains no .mp4 video files"
                return result

            result["is_valid"] = True
            return result

        except S3Error as e:
            result["error"] = str(e)
            return result

    def get_presigned_url(
        self,
        bucket_name: str,
        object_name: str,
        expires: timedelta = timedelta(hours=1),
    ) -> str:
        """Generate a presigned URL for accessing an object.

        Args:
            bucket_name: Name of the bucket.
            object_name: Name of the object (video file).
            expires: URL expiration time (default 1 hour).

        Returns:
            Presigned URL string.
        """
        try:
            url = self.client.presigned_get_object(
                bucket_name=bucket_name,
                object_name=object_name,
                expires=expires,
            )
            return url
        except S3Error as e:
            logger.error(f"Error generating presigned URL: {e}")
            raise

    def get_video_filenames(self, bucket_name: str) -> list[str]:
        """Get just the filenames of videos in a bucket.

        Args:
            bucket_name: Name of the bucket.

        Returns:
            List of video filenames.
        """
        videos = self.list_videos(bucket_name)
        return [v["name"] for v in videos]


@lru_cache()
def get_minio_client() -> MinioClient:
    """Get a singleton MinIO client instance."""
    return MinioClient()
