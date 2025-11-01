#!/usr/bin/env python3
"""
Whisper Container: Extracts speech/transcription from video using Whisper AI
"""
import os
import json
import whisper
from minio import Minio
from minio.error import S3Error
import tempfile
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# MinIO Configuration
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET_VIDEOS = os.getenv("MINIO_BUCKET_VIDEOS", "videos")
MINIO_BUCKET_TRANSCRIPTS = os.getenv("MINIO_BUCKET_TRANSCRIPTS", "transcripts")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"

# Whisper Configuration
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")

# Initialize MinIO client
minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=MINIO_SECURE
)

# Load Whisper model
print(f"Loading Whisper model: {WHISPER_MODEL}")
whisper_model = whisper.load_model(WHISPER_MODEL)
print("Whisper model loaded successfully")


def ensure_buckets():
    """Create buckets if they don't exist"""
    buckets = [MINIO_BUCKET_TRANSCRIPTS]
    for bucket in buckets:
        if not minio_client.bucket_exists(bucket):
            minio_client.make_bucket(bucket)
            print(f"Created bucket: {bucket}")


def extract_audio_from_video(video_path, audio_path):
    """Extract audio from video using ffmpeg"""
    import subprocess
    cmd = [
        'ffmpeg', '-i', video_path,
        '-vn', '-acodec', 'libmp3lame',
        '-ar', '16000', '-ac', '1',
        '-y', audio_path
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def transcribe_video(video_id, video_object):
    """Download video from MinIO, transcribe, and upload transcript"""
    print(f"Processing video: {video_id}")
    
    # Download video from MinIO
    video_path = f"/tmp/{video_id}_video.mp4"
    try:
        minio_client.fget_object(
            MINIO_BUCKET_VIDEOS,
            video_object,
            video_path
        )
        print(f"Downloaded video: {video_object}")
    except S3Error as e:
        print(f"Error downloading video: {e}")
        return None
    
    # Extract audio
    audio_path = f"/tmp/{video_id}_audio.mp3"
    try:
        extract_audio_from_video(video_path, audio_path)
        print("Audio extracted")
    except Exception as e:
        print(f"Error extracting audio: {e}")
        return None
    
    # Transcribe using Whisper
    try:
        print("Transcribing audio...")
        result = whisper_model.transcribe(
            audio_path,
            language=None,  # Auto-detect language
            task="transcribe",
            verbose=False
        )
        print("Transcription completed")
        
        # Prepare transcript data
        transcript_data = {
            'video_id': video_id,
            'text': result['text'],
            'language': result.get('language', 'unknown'),
            'segments': result.get('segments', []),
            'transcribed_at': datetime.utcnow().isoformat(),
        }
        
        # Save transcript as JSON
        transcript_json = f"/tmp/{video_id}_transcript.json"
        with open(transcript_json, 'w', encoding='utf-8') as f:
            json.dump(transcript_data, f, indent=2, ensure_ascii=False)
        
        # Save plain text transcript
        transcript_txt = f"/tmp/{video_id}_transcript.txt"
        with open(transcript_txt, 'w', encoding='utf-8') as f:
            f.write(result['text'])
        
        # Upload to MinIO
        transcript_json_object = f"{video_id}/transcript.json"
        transcript_txt_object = f"{video_id}/transcript.txt"
        
        minio_client.fput_object(
            MINIO_BUCKET_TRANSCRIPTS,
            transcript_json_object,
            transcript_json
        )
        minio_client.fput_object(
            MINIO_BUCKET_TRANSCRIPTS,
            transcript_txt_object,
            transcript_txt
        )
        
        print(f"Uploaded transcripts: {transcript_json_object}, {transcript_txt_object}")
        
        # Cleanup
        for file in [video_path, audio_path, transcript_json, transcript_txt]:
            if os.path.exists(file):
                os.remove(file)
        
        return transcript_data
        
    except Exception as e:
        print(f"Error transcribing: {e}")
        return None


def main():
    """Main function"""
    print("Whisper Container Starting...")
    
    # Ensure buckets exist
    ensure_buckets()
    
    # Get video_id and video_object from environment
    video_id = os.getenv("VIDEO_ID")
    video_object = os.getenv("VIDEO_OBJECT")
    
    if not video_id or not video_object:
        print("Waiting for video to process...")
        # In production, you might want to use a message queue
        # For now, we'll wait for environment variables
        print("Set VIDEO_ID and VIDEO_OBJECT environment variables")
        return
    
    transcript_data = transcribe_video(video_id, video_object)
    
    if transcript_data:
        print("Transcription completed successfully!")
        print(f"Text: {transcript_data['text'][:200]}...")
    else:
        print("Failed to transcribe video")


if __name__ == "__main__":
    main()

