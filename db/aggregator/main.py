#!/usr/bin/env python3
"""
Data Aggregator: Aggregates all data from different containers and writes to PostgreSQL
"""
import os
import json
import psycopg2
from minio import Minio
from minio.error import S3Error
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# MinIO Configuration
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET_METADATA = os.getenv("MINIO_BUCKET_METADATA", "metadata")
MINIO_BUCKET_TRANSCRIPTS = os.getenv("MINIO_BUCKET_TRANSCRIPTS", "transcripts")
MINIO_BUCKET_OCR = os.getenv("MINIO_BUCKET_OCR", "ocr")
MINIO_BUCKET_DETECTIONS = os.getenv("MINIO_BUCKET_DETECTIONS", "detections")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"

# PostgreSQL Configuration
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "tiktok_video_scan")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")

# Initialize MinIO client
minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=MINIO_SECURE
)


def get_db_connection():
    """Get PostgreSQL database connection"""
    return psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        database=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD
    )


def download_from_minio(bucket, object_path, local_path):
    """Download file from MinIO"""
    try:
        minio_client.fget_object(bucket, object_path, local_path)
        return True
    except S3Error as e:
        print(f"Error downloading from MinIO: {e}")
        return False


def load_json_from_minio(bucket, object_path):
    """Load JSON file from MinIO"""
    temp_file = f"/tmp/{os.path.basename(object_path)}"
    if download_from_minio(bucket, object_path, temp_file):
        with open(temp_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        os.remove(temp_file)
        return data
    return None


def aggregate_video_data(video_id):
    """Aggregate all data for a video and save to PostgreSQL"""
    print(f"Aggregating data for video: {video_id}")
    
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # 1. Load metadata from MinIO
        metadata_object = f"{video_id}/metadata.json"
        metadata = load_json_from_minio(MINIO_BUCKET_METADATA, metadata_object)
        
        if not metadata:
            print(f"Metadata not found for video: {video_id}")
            return False
        
        # Extract video metadata
        video_url = metadata.get('video_url', '')
        title = metadata.get('title', '')
        description = metadata.get('description', '')
        channel = metadata.get('channel', '')
        channel_id = metadata.get('channel_id', '')
        account = metadata.get('account', '')
        duration = metadata.get('duration', 0)
        view_count = metadata.get('view_count', 0)
        like_count = metadata.get('like_count', 0)
        upload_date = metadata.get('upload_date', '')
        hashtags = metadata.get('hashtags', [])
        thumbnail_url = metadata.get('thumbnail_url', '')
        
        # Convert upload_date to date if available
        upload_date_val = None
        if upload_date and len(upload_date) >= 8:
            try:
                upload_date_val = datetime.strptime(upload_date[:8], '%Y%m%d').date()
            except:
                pass
        
        # Insert or update video
        cur.execute("""
            INSERT INTO videos (
                video_id, video_url, title, description, channel, channel_id, account,
                duration, view_count, like_count, upload_date, thumbnail_url,
                video_object, metadata_object, thumbnail_object, extractor, webpage_url, downloaded_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (video_id) DO UPDATE SET
                title = EXCLUDED.title,
                description = EXCLUDED.description,
                channel = EXCLUDED.channel,
                account = EXCLUDED.account,
                duration = EXCLUDED.duration,
                view_count = EXCLUDED.view_count,
                like_count = EXCLUDED.like_count,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id
        """, (
            video_id, video_url, title, description, channel, channel_id, account,
            duration, view_count, like_count, upload_date_val, thumbnail_url,
            metadata.get('video_object'), metadata_object,
            metadata.get('thumbnail_object'), metadata.get('extractor'),
            metadata.get('webpage_url'), datetime.fromisoformat(metadata.get('downloaded_at', datetime.utcnow().isoformat()))
        ))
        
        video_uuid = cur.fetchone()[0]
        print(f"Video UUID: {video_uuid}")
        
        # Insert hashtags
        for hashtag in hashtags:
            cur.execute("""
                INSERT INTO hashtags (video_id, hashtag)
                VALUES (%s, %s)
                ON CONFLICT (video_id, hashtag) DO NOTHING
            """, (video_uuid, hashtag))
        
        # 2. Load transcript from MinIO
        transcript_object = f"{video_id}/transcript.json"
        transcript_data = load_json_from_minio(MINIO_BUCKET_TRANSCRIPTS, transcript_object)
        
        if transcript_data:
            cur.execute("""
                INSERT INTO transcripts (video_id, text, language, transcript_json_object, transcript_txt_object, transcribed_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (video_id) DO UPDATE SET
                    text = EXCLUDED.text,
                    language = EXCLUDED.language,
                    transcript_json_object = EXCLUDED.transcript_json_object,
                    transcript_txt_object = EXCLUDED.transcript_txt_object,
                    transcribed_at = EXCLUDED.transcribed_at
                RETURNING id
            """, (
                video_uuid,
                transcript_data.get('text'),
                transcript_data.get('language'),
                transcript_object,
                f"{video_id}/transcript.txt",
                datetime.fromisoformat(transcript_data.get('transcribed_at', datetime.utcnow().isoformat()))
            ))
            
            transcript_result = cur.fetchone()
            if transcript_result:
                transcript_uuid = transcript_result[0]
                
                # Delete old segments and insert new ones
                cur.execute("DELETE FROM transcript_segments WHERE transcript_id = %s", (transcript_uuid,))
                
                # Insert transcript segments
                for segment in transcript_data.get('segments', []):
                    cur.execute("""
                        INSERT INTO transcript_segments (transcript_id, start, "end", text)
                        VALUES (%s, %s, %s, %s)
                    """, (transcript_uuid, segment.get('start'), segment.get('end'), segment.get('text')))
        
        # 3. Load OCR results from MinIO
        ocr_object = f"{video_id}/ocr.json"
        ocr_data = load_json_from_minio(MINIO_BUCKET_OCR, ocr_object)
        
        if ocr_data:
            cur.execute("""
                INSERT INTO ocr_results (
                    video_id, all_text, total_frames, frames_with_text,
                    ocr_json_object, ocr_txt_object, processed_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (video_id) DO UPDATE SET
                    all_text = EXCLUDED.all_text,
                    total_frames = EXCLUDED.total_frames,
                    frames_with_text = EXCLUDED.frames_with_text,
                    ocr_json_object = EXCLUDED.ocr_json_object,
                    ocr_txt_object = EXCLUDED.ocr_txt_object,
                    processed_at = EXCLUDED.processed_at
                RETURNING id
            """, (
                video_uuid,
                ocr_data.get('all_text'),
                ocr_data.get('total_frames'),
                ocr_data.get('frames_with_text'),
                ocr_object,
                f"{video_id}/ocr.txt",
                datetime.fromisoformat(ocr_data.get('processed_at', datetime.utcnow().isoformat()))
            ))
            
            ocr_result = cur.fetchone()
            if ocr_result:
                ocr_uuid = ocr_result[0]
                
                # Delete old OCR frames and insert new ones
                cur.execute("DELETE FROM ocr_frames WHERE ocr_result_id = %s", (ocr_uuid,))
                
                # Insert OCR frames
                for frame_result in ocr_data.get('frame_results', []):
                    cur.execute("""
                        INSERT INTO ocr_frames (
                            ocr_result_id, frame_number, timestamp, filename,
                            frame_object, ocr_text
                        )
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        ocr_uuid,
                        frame_result.get('frame_number'),
                        frame_result.get('timestamp'),
                        frame_result.get('filename'),
                        frame_result.get('frame_object'),
                        frame_result.get('ocr_text')
                    ))
        
        # 4. Load object detection results from MinIO
        detection_object = f"{video_id}/detections.json"
        detection_data = load_json_from_minio(MINIO_BUCKET_DETECTIONS, detection_object)
        
        if detection_data:
            cur.execute("""
                INSERT INTO object_detections (
                    video_id, total_frames_processed, total_detections,
                    model, confidence_threshold, detections_json_object, processed_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (video_id) DO UPDATE SET
                    total_frames_processed = EXCLUDED.total_frames_processed,
                    total_detections = EXCLUDED.total_detections,
                    model = EXCLUDED.model,
                    confidence_threshold = EXCLUDED.confidence_threshold,
                    detections_json_object = EXCLUDED.detections_json_object,
                    processed_at = EXCLUDED.processed_at
                RETURNING id
            """, (
                video_uuid,
                detection_data.get('total_frames_processed'),
                detection_data.get('total_detections'),
                detection_data.get('model'),
                detection_data.get('confidence_threshold'),
                detection_object,
                datetime.fromisoformat(detection_data.get('processed_at', datetime.utcnow().isoformat()))
            ))
            
            detection_result = cur.fetchone()
            if detection_result:
                detection_uuid = detection_result[0]
                
                # Delete old detected products and insert new ones
                cur.execute("DELETE FROM detected_products WHERE detection_id = %s", (detection_uuid,))
                
                # Insert detected products
                for product in detection_data.get('detected_products', []):
                    cur.execute("""
                        INSERT INTO detected_products (detection_id, product_name)
                        VALUES (%s, %s)
                    """, (detection_uuid, product))
                
                # Delete old detection frames and insert new ones
                cur.execute("DELETE FROM detection_frames WHERE detection_id = %s", (detection_uuid,))
                
                # Insert detection frames
                for frame_result in detection_data.get('frame_results', []):
                    cur.execute("""
                        INSERT INTO detection_frames (
                            detection_id, frame_number, timestamp,
                            total_detections, frame_object
                        )
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING id
                    """, (
                        detection_uuid,
                        frame_result.get('frame_number'),
                        frame_result.get('timestamp'),
                        frame_result.get('total_detections'),
                        f"{video_id}/detected_frames/frame_{frame_result.get('frame_number', 0):04d}_{frame_result.get('timestamp', 0):.2f}s_detected.jpg"
                    ))
                    
                    detection_frame_result = cur.fetchone()
                    if detection_frame_result:
                        detection_frame_uuid = detection_frame_result[0]
                        
                        # Delete old detection details and insert new ones
                        cur.execute("DELETE FROM detection_details WHERE detection_frame_id = %s", (detection_frame_uuid,))
                        
                        # Insert detection details
                        for detection in frame_result.get('detections', []):
                            bbox = detection.get('bbox', {})
                            cur.execute("""
                                INSERT INTO detection_details (
                                    detection_frame_id, class_id, class_name,
                                    confidence, bbox_x1, bbox_y1, bbox_x2, bbox_y2
                                )
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            """, (
                                detection_frame_uuid,
                                detection.get('class_id'),
                                detection.get('class_name'),
                                detection.get('confidence'),
                                bbox.get('x1'),
                                bbox.get('y1'),
                                bbox.get('x2'),
                                bbox.get('y2')
                            ))
        
        # Commit transaction
        conn.commit()
        print(f"Successfully aggregated data for video: {video_id}")
        return True
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error aggregating data: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if conn:
            cur.close()
            conn.close()


def main():
    """Main function"""
    print("Data Aggregator Container Starting...")
    
    # Get video_id from environment
    video_id = os.getenv("VIDEO_ID")
    
    if not video_id:
        print("Waiting for video to aggregate...")
        print("Set VIDEO_ID environment variable")
        return
    
    success = aggregate_video_data(video_id)
    
    if success:
        print("Data aggregation completed successfully!")
    else:
        print("Failed to aggregate data")


if __name__ == "__main__":
    main()

