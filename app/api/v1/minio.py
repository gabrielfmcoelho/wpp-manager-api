"""MinIO endpoints for bucket and video management."""

import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.api.deps import CurrentAuthContext
from app.services.minio_client import get_minio_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/minio", tags=["minio"])


class BucketInfo(BaseModel):
    """Bucket information."""

    name: str
    creation_date: str | None


class BucketList(BaseModel):
    """List of buckets."""

    items: list[BucketInfo]


class VideoInfo(BaseModel):
    """Video file information."""

    name: str
    size: int | None
    last_modified: str | None


class VideoList(BaseModel):
    """List of videos in a bucket."""

    bucket_name: str
    items: list[VideoInfo]
    total: int


class BucketValidation(BaseModel):
    """Result of bucket validation."""

    bucket_name: str
    is_valid: bool
    exists: bool
    video_count: int
    error: str | None


@router.get("/buckets", response_model=BucketList)
async def list_buckets(
    auth: CurrentAuthContext,
) -> BucketList:
    """List all available MinIO buckets.

    Returns a list of bucket names that can be used for video distribution.
    """
    try:
        minio_client = get_minio_client()
        buckets = minio_client.list_buckets()
        return BucketList(
            items=[BucketInfo(**b) for b in buckets]
        )
    except Exception as e:
        logger.error(f"Error listing buckets: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to connect to MinIO: {str(e)}",
        )


@router.get("/buckets/{bucket_name}/validate", response_model=BucketValidation)
async def validate_bucket(
    bucket_name: str,
    auth: CurrentAuthContext,
) -> BucketValidation:
    """Validate that a bucket exists and contains .mp4 videos.

    This endpoint checks if the bucket is suitable for video distribution.
    """
    try:
        minio_client = get_minio_client()
        result = minio_client.validate_bucket_for_video_distribution(bucket_name)
        return BucketValidation(**result)
    except Exception as e:
        logger.error(f"Error validating bucket {bucket_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to validate bucket: {str(e)}",
        )


@router.get("/buckets/{bucket_name}/videos", response_model=VideoList)
async def list_videos(
    bucket_name: str,
    auth: CurrentAuthContext,
) -> VideoList:
    """List all .mp4 videos in a bucket.

    Returns information about each video file including size and last modified date.
    """
    try:
        minio_client = get_minio_client()

        # Verify bucket exists
        if not minio_client.bucket_exists(bucket_name):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Bucket '{bucket_name}' not found",
            )

        videos = minio_client.list_videos(bucket_name)
        return VideoList(
            bucket_name=bucket_name,
            items=[VideoInfo(**v) for v in videos],
            total=len(videos),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing videos in bucket {bucket_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to list videos: {str(e)}",
        )
