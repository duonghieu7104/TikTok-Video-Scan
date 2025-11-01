#!/usr/bin/env python3
"""
yt-dlp Container: Downloads video and metadata, uploads to MinIO
"""
import os
import json
import yt_dlp
from minio import Minio
from minio.error import S3Error
from datetime import datetime
import hashlib
from dotenv import load_dotenv

load_dotenv()

# MinIO Configuration
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET_VIDEOS = os.getenv("MINIO_BUCKET_VIDEOS", "videos")
MINIO_BUCKET_METADATA = os.getenv("MINIO_BUCKET_METADATA", "metadata")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"

# Initialize MinIO client
minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=MINIO_SECURE
)


def ensure_buckets():
    """Create buckets if they don't exist"""
    buckets = [MINIO_BUCKET_VIDEOS, MINIO_BUCKET_METADATA]
    for bucket in buckets:
        if not minio_client.bucket_exists(bucket):
            minio_client.make_bucket(bucket)
            print(f"Created bucket: {bucket}")


def extract_hashtags(text):
    """Extract hashtags from text"""
    if not text:
        return []
    import re
    hashtags = re.findall(r'#\w+', text)
    return [tag.lower() for tag in hashtags]


def download_video(video_url):
    """Download video and extract metadata using yt-dlp"""
    video_id = hashlib.md5(video_url.encode()).hexdigest()
    
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': f'/tmp/{video_id}.%(ext)s',
        'writeinfojson': True,
        'writethumbnail': True,
        'quiet': False,
        'no_warnings': False,
    }
    
    metadata = {}
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract info
            info = ydl.extract_info(video_url, download=True)
            
            # Prepare metadata
            metadata = {
                'video_url': video_url,
                'video_id': video_id,
                'title': info.get('title', ''),
                'description': info.get('description', ''),
                'channel': info.get('uploader', ''),
                'channel_id': info.get('channel_id', ''),
                'account': info.get('uploader', ''),
                'duration': info.get('duration', 0),
                'view_count': info.get('view_count', 0),
                'like_count': info.get('like_count', 0),
                'upload_date': info.get('upload_date', ''),
                'hashtags': extract_hashtags(info.get('description', '')),
                'thumbnail_url': info.get('thumbnail', ''),
                'extractor': info.get('extractor', ''),
                'extractor_key': info.get('extractor_key', ''),
                'webpage_url': info.get('webpage_url', ''),
                'downloaded_at': datetime.utcnow().isoformat(),
            }
            
            # Get downloaded file path
            ext = info.get('ext', 'mp4')
            video_file = f'/tmp/{video_id}.{ext}'
            metadata_file = f'/tmp/{video_id}.info.json'
            thumbnail_file = f'/tmp/{video_id}.{info.get("thumbnail_ext", "jpg")}'
            
            # Upload to MinIO
            if os.path.exists(video_file):
                video_object = f"{video_id}/video.{ext}"
                minio_client.fput_object(
                    MINIO_BUCKET_VIDEOS,
                    video_object,
                    video_file
                )
                metadata['video_object'] = video_object
                print(f"Uploaded video: {video_object}")
            
            # Upload metadata JSON
            if os.path.exists(metadata_file):
                with open(metadata_file, 'r') as f:
                    full_metadata = json.load(f)
                    metadata['full_metadata'] = full_metadata
                
                metadata_object = f"{video_id}/metadata.json"
                minio_client.fput_object(
                    MINIO_BUCKET_METADATA,
                    metadata_object,
                    metadata_file
                )
                metadata['metadata_object'] = metadata_object
                print(f"Uploaded metadata: {metadata_object}")
            
            # Upload thumbnail
            if os.path.exists(thumbnail_file):
                thumbnail_object = f"{video_id}/thumbnail.{info.get('thumbnail_ext', 'jpg')}"
                minio_client.fput_object(
                    MINIO_BUCKET_METADATA,
                    thumbnail_object,
                    thumbnail_file
                )
                metadata['thumbnail_object'] = thumbnail_object
                print(f"Uploaded thumbnail: {thumbnail_object}")
            
            # Cleanup
            for file in [video_file, metadata_file, thumbnail_file]:
                if os.path.exists(file):
                    os.remove(file)
            
            return metadata
            
    except Exception as e:
        print(f"Error downloading video: {e}")
        return None


def main():
    """Main function"""
    print("yt-dlp Container Starting...")
    
    # Ensure buckets exist
    ensure_buckets()
    
    # Get video URL from environment or stdin
    video_url = os.getenv("VIDEO_URL")
    
    if not video_url:
        print("Waiting for video URL...")
        # In production, you might want to use a message queue or API
        video_url = input("Enter video URL: ").strip()
    
    if video_url:
        print(f"Processing video: {video_url}")
        metadata = download_video(video_url)
        
        if metadata:
            print("Video downloaded and metadata extracted successfully!")
            print(json.dumps(metadata, indent=2))
        else:
            print("Failed to download video")
    else:
        print("No video URL provided")


if __name__ == "__main__":
    main()

