#!/usr/bin/env python3
"""
OCR Container: Extracts frames from video and performs OCR to recognize text
"""
import os
import json
import cv2
import numpy as np
from minio import Minio
from minio.error import S3Error
import tempfile
from datetime import datetime
import pytesseract
import easyocr
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

# MinIO Configuration
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET_VIDEOS = os.getenv("MINIO_BUCKET_VIDEOS", "videos")
MINIO_BUCKET_FRAMES = os.getenv("MINIO_BUCKET_FRAMES", "frames")
MINIO_BUCKET_OCR = os.getenv("MINIO_BUCKET_OCR", "ocr")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"

# OCR Configuration
OCR_ENGINE = os.getenv("OCR_ENGINE", "easyocr")  # tesseract or easyocr
FRAME_INTERVAL = int(os.getenv("FRAME_INTERVAL", "5"))  # Extract frame every N seconds
MAX_FRAMES = int(os.getenv("MAX_FRAMES", "10"))  # Maximum frames to process

# Initialize MinIO client
minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=MINIO_SECURE
)

# Initialize EasyOCR reader (if using)
easyocr_reader = None
if OCR_ENGINE == "easyocr":
    print("Initializing EasyOCR...")
    easyocr_reader = easyocr.Reader(['en', 'vi'], gpu=False)
    print("EasyOCR initialized")


def ensure_buckets():
    """Create buckets if they don't exist"""
    buckets = [MINIO_BUCKET_FRAMES, MINIO_BUCKET_OCR]
    for bucket in buckets:
        if not minio_client.bucket_exists(bucket):
            minio_client.make_bucket(bucket)
            print(f"Created bucket: {bucket}")


def extract_frames(video_path, output_dir):
    """Extract frames from video at regular intervals"""
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0
    
    frame_interval = FRAME_INTERVAL * fps  # Convert seconds to frames
    extracted_frames = []
    frame_count = 0
    extracted_count = 0
    
    print(f"Video: {duration:.2f}s, FPS: {fps:.2f}, Total frames: {total_frames}")
    
    while cap.isOpened() and extracted_count < MAX_FRAMES:
        ret, frame = cap.read()
        if not ret:
            break
        
        # Extract frame at intervals
        if frame_count % int(frame_interval) == 0:
            timestamp = frame_count / fps if fps > 0 else 0
            frame_filename = f"frame_{extracted_count:04d}_{timestamp:.2f}s.jpg"
            frame_path = os.path.join(output_dir, frame_filename)
            
            cv2.imwrite(frame_path, frame)
            extracted_frames.append({
                'frame_number': frame_count,
                'timestamp': timestamp,
                'filename': frame_filename,
                'path': frame_path
            })
            extracted_count += 1
        
        frame_count += 1
    
    cap.release()
    print(f"Extracted {len(extracted_frames)} frames")
    return extracted_frames


def ocr_tesseract(image_path):
    """Perform OCR using Tesseract"""
    image = Image.open(image_path)
    text = pytesseract.image_to_string(image, lang='eng+vie')
    
    # Get detailed data
    data = pytesseract.image_to_data(image, lang='eng+vie', output_type=pytesseract.Output.DICT)
    
    return {
        'text': text.strip(),
        'words': data.get('text', []),
        'confidences': data.get('conf', []),
        'boxes': list(zip(data.get('left', []), data.get('top', []), 
                         data.get('width', []), data.get('height', [])))
    }


def ocr_easyocr(image_path):
    """Perform OCR using EasyOCR"""
    results = easyocr_reader.readtext(image_path)
    
    text_lines = [result[1] for result in results]
    full_text = '\n'.join(text_lines)
    
    words_data = []
    for result in results:
        bbox, text, confidence = result
        words_data.append({
            'text': text,
            'confidence': confidence,
            'bbox': bbox
        })
    
    return {
        'text': full_text,
        'words': words_data
    }


def perform_ocr_on_frame(frame_path, frame_info):
    """Perform OCR on a single frame"""
    if OCR_ENGINE == "tesseract":
        ocr_result = ocr_tesseract(frame_path)
    elif OCR_ENGINE == "easyocr":
        ocr_result = ocr_easyocr(frame_path)
    else:
        raise ValueError(f"Unknown OCR engine: {OCR_ENGINE}")
    
    return {
        **frame_info,
        'ocr_text': ocr_result['text'],
        'ocr_data': ocr_result
    }


def process_video(video_id, video_object):
    """Download video, extract frames, perform OCR, and upload results"""
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
    
    # Create temporary directory for frames
    frames_dir = f"/tmp/{video_id}_frames"
    os.makedirs(frames_dir, exist_ok=True)
    
    try:
        # Extract frames
        frames = extract_frames(video_path, frames_dir)
        
        # Perform OCR on each frame
        ocr_results = []
        for frame_info in frames:
            print(f"Processing frame: {frame_info['filename']}")
            ocr_result = perform_ocr_on_frame(frame_info['path'], frame_info)
            ocr_results.append(ocr_result)
            
            # Upload frame to MinIO
            frame_object = f"{video_id}/frames/{frame_info['filename']}"
            minio_client.fput_object(
                MINIO_BUCKET_FRAMES,
                frame_object,
                frame_info['path']
            )
            ocr_result['frame_object'] = frame_object
        
        # Aggregate all OCR text
        all_text = '\n\n'.join([
            f"[{r['timestamp']:.2f}s] {r['ocr_text']}" 
            for r in ocr_results if r['ocr_text'].strip()
        ])
        
        # Prepare OCR summary
        ocr_summary = {
            'video_id': video_id,
            'total_frames': len(ocr_results),
            'frames_with_text': sum(1 for r in ocr_results if r['ocr_text'].strip()),
            'all_text': all_text,
            'frame_results': ocr_results,
            'processed_at': datetime.utcnow().isoformat(),
        }
        
        # Save OCR results as JSON
        ocr_json_path = f"/tmp/{video_id}_ocr.json"
        with open(ocr_json_path, 'w', encoding='utf-8') as f:
            json.dump(ocr_summary, f, indent=2, ensure_ascii=False)
        
        # Save OCR text
        ocr_txt_path = f"/tmp/{video_id}_ocr.txt"
        with open(ocr_txt_path, 'w', encoding='utf-8') as f:
            f.write(all_text)
        
        # Upload to MinIO
        ocr_json_object = f"{video_id}/ocr.json"
        ocr_txt_object = f"{video_id}/ocr.txt"
        
        minio_client.fput_object(
            MINIO_BUCKET_OCR,
            ocr_json_object,
            ocr_json_path
        )
        minio_client.fput_object(
            MINIO_BUCKET_OCR,
            ocr_txt_object,
            ocr_txt_path
        )
        
        print(f"Uploaded OCR results: {ocr_json_object}, {ocr_txt_object}")
        
        # Cleanup
        import shutil
        if os.path.exists(video_path):
            os.remove(video_path)
        if os.path.exists(frames_dir):
            shutil.rmtree(frames_dir)
        if os.path.exists(ocr_json_path):
            os.remove(ocr_json_path)
        if os.path.exists(ocr_txt_path):
            os.remove(ocr_txt_path)
        
        return ocr_summary
        
    except Exception as e:
        print(f"Error processing video: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Main function"""
    print("OCR Container Starting...")
    
    # Ensure buckets exist
    ensure_buckets()
    
    # Get video_id and video_object from environment
    video_id = os.getenv("VIDEO_ID")
    video_object = os.getenv("VIDEO_OBJECT")
    
    if not video_id or not video_object:
        print("Waiting for video to process...")
        print("Set VIDEO_ID and VIDEO_OBJECT environment variables")
        return
    
    ocr_summary = process_video(video_id, video_object)
    
    if ocr_summary:
        print("OCR processing completed successfully!")
        print(f"Frames processed: {ocr_summary['total_frames']}")
        print(f"Text found: {len(ocr_summary['all_text'])} characters")
    else:
        print("Failed to process video with OCR")


if __name__ == "__main__":
    main()

