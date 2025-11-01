#!/usr/bin/env python3
"""
Object Detection Container: Detects products/objects in video frames using YOLOv8
"""
import os
import json
import cv2
import numpy as np
from minio import Minio
from minio.error import S3Error
from datetime import datetime
from ultralytics import YOLO
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

# MinIO Configuration
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET_VIDEOS = os.getenv("MINIO_BUCKET_VIDEOS", "videos")
MINIO_BUCKET_FRAMES = os.getenv("MINIO_BUCKET_FRAMES", "frames")
MINIO_BUCKET_DETECTIONS = os.getenv("MINIO_BUCKET_DETECTIONS", "detections")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"

# YOLO Configuration
YOLO_MODEL = os.getenv("YOLO_MODEL", "yolov8n.pt")  # yolov8n, yolov8s, yolov8m, yolov8l, yolov8x
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.25"))
FRAME_INTERVAL = int(os.getenv("FRAME_INTERVAL", "5"))  # Process frame every N seconds
MAX_FRAMES = int(os.getenv("MAX_FRAMES", "10"))  # Maximum frames to process

# Product-related classes (COCO dataset classes - adjust as needed)
PRODUCT_CLASSES = {
    39: 'bottle', 40: 'wine glass', 41: 'cup', 44: 'bowl',
    46: 'banana', 47: 'apple', 48: 'sandwich', 49: 'orange',
    50: 'broccoli', 51: 'carrot', 52: 'hot dog', 53: 'pizza',
    54: 'donut', 55: 'cake', 67: 'cell phone', 73: 'book',
    74: 'clock', 76: 'vase', 77: 'scissors', 78: 'teddy bear'
}

# Initialize MinIO client
minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=MINIO_SECURE
)

# Load YOLO model
print(f"Loading YOLO model: {YOLO_MODEL}")
yolo_model = YOLO(YOLO_MODEL)
print("YOLO model loaded successfully")


def ensure_buckets():
    """Create buckets if they don't exist"""
    buckets = [MINIO_BUCKET_DETECTIONS]
    for bucket in buckets:
        if not minio_client.bucket_exists(bucket):
            minio_client.make_bucket(bucket)
            print(f"Created bucket: {bucket}")


def extract_frames_for_detection(video_path):
    """Extract frames from video at regular intervals"""
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0
    
    frame_interval = FRAME_INTERVAL * fps
    frames = []
    frame_count = 0
    extracted_count = 0
    
    print(f"Video: {duration:.2f}s, FPS: {fps:.2f}, Total frames: {total_frames}")
    
    while cap.isOpened() and extracted_count < MAX_FRAMES:
        ret, frame = cap.read()
        if not ret:
            break
        
        if frame_count % int(frame_interval) == 0:
            timestamp = frame_count / fps if fps > 0 else 0
            frames.append({
                'frame_number': frame_count,
                'timestamp': timestamp,
                'frame': frame.copy()
            })
            extracted_count += 1
        
        frame_count += 1
    
    cap.release()
    print(f"Extracted {len(frames)} frames for detection")
    return frames


def detect_objects_in_frame(frame, timestamp):
    """Detect objects in a single frame using YOLO"""
    results = yolo_model(frame, conf=CONFIDENCE_THRESHOLD, verbose=False)
    
    detections = []
    detected_products = set()
    
    for result in results:
        boxes = result.boxes
        for box in boxes:
            # Get box coordinates
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
            confidence = float(box.conf[0].cpu().numpy())
            class_id = int(box.cls[0].cpu().numpy())
            class_name = yolo_model.names[class_id]
            
            detection = {
                'class_id': class_id,
                'class_name': class_name,
                'confidence': confidence,
                'bbox': {
                    'x1': float(x1),
                    'y1': float(y1),
                    'x2': float(x2),
                    'y2': float(y2)
                }
            }
            
            detections.append(detection)
            
            # Track if it's a potential product
            if class_id in PRODUCT_CLASSES or 'product' in class_name.lower():
                detected_products.add(class_name)
    
    return {
        'timestamp': timestamp,
        'detections': detections,
        'detected_products': list(detected_products),
        'total_detections': len(detections)
    }


def draw_detections(frame, detections):
    """Draw bounding boxes on frame"""
    annotated_frame = frame.copy()
    for det in detections['detections']:
        bbox = det['bbox']
        x1, y1, x2, y2 = int(bbox['x1']), int(bbox['y1']), int(bbox['x2']), int(bbox['y2'])
        
        # Draw rectangle
        cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        
        # Draw label
        label = f"{det['class_name']} {det['confidence']:.2f}"
        cv2.putText(annotated_frame, label, (x1, y1 - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    
    return annotated_frame


def process_video(video_id, video_object):
    """Download video, detect objects in frames, and upload results"""
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
    
    try:
        # Extract frames
        frames = extract_frames_for_detection(video_path)
        
        # Detect objects in each frame
        detection_results = []
        all_products = set()
        
        for frame_info in frames:
            print(f"Detecting objects in frame at {frame_info['timestamp']:.2f}s...")
            result = detect_objects_in_frame(frame_info['frame'], frame_info['timestamp'])
            detection_results.append(result)
            
            # Collect all products
            all_products.update(result['detected_products'])
            
            # Draw detections on frame
            annotated_frame = draw_detections(frame_info['frame'], result)
            
            # Save annotated frame
            frame_filename = f"frame_{frame_info['frame_number']:04d}_{frame_info['timestamp']:.2f}s_detected.jpg"
            frame_path = f"/tmp/{frame_filename}"
            cv2.imwrite(frame_path, annotated_frame)
            
            # Upload annotated frame to MinIO
            frame_object = f"{video_id}/detected_frames/{frame_filename}"
            minio_client.fput_object(
                MINIO_BUCKET_DETECTIONS,
                frame_object,
                frame_path
            )
            
            # Cleanup
            if os.path.exists(frame_path):
                os.remove(frame_path)
        
        # Prepare detection summary
        detection_summary = {
            'video_id': video_id,
            'total_frames_processed': len(detection_results),
            'total_detections': sum(r['total_detections'] for r in detection_results),
            'detected_products': list(all_products),
            'frame_results': detection_results,
            'processed_at': datetime.utcnow().isoformat(),
            'model': YOLO_MODEL,
            'confidence_threshold': CONFIDENCE_THRESHOLD
        }
        
        # Save detection results as JSON
        detection_json_path = f"/tmp/{video_id}_detections.json"
        with open(detection_json_path, 'w', encoding='utf-8') as f:
            json.dump(detection_summary, f, indent=2, ensure_ascii=False)
        
        # Upload to MinIO
        detection_json_object = f"{video_id}/detections.json"
        minio_client.fput_object(
            MINIO_BUCKET_DETECTIONS,
            detection_json_object,
            detection_json_path
        )
        
        print(f"Uploaded detection results: {detection_json_object}")
        
        # Cleanup
        if os.path.exists(video_path):
            os.remove(video_path)
        if os.path.exists(detection_json_path):
            os.remove(detection_json_path)
        
        return detection_summary
        
    except Exception as e:
        print(f"Error processing video: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Main function"""
    print("Object Detection Container Starting...")
    
    # Ensure buckets exist
    ensure_buckets()
    
    # Get video_id and video_object from environment
    video_id = os.getenv("VIDEO_ID")
    video_object = os.getenv("VIDEO_OBJECT")
    
    if not video_id or not video_object:
        print("Waiting for video to process...")
        print("Set VIDEO_ID and VIDEO_OBJECT environment variables")
        return
    
    detection_summary = process_video(video_id, video_object)
    
    if detection_summary:
        print("Object detection completed successfully!")
        print(f"Frames processed: {detection_summary['total_frames_processed']}")
        print(f"Total detections: {detection_summary['total_detections']}")
        print(f"Products detected: {', '.join(detection_summary['detected_products']) if detection_summary['detected_products'] else 'None'}")
    else:
        print("Failed to process video with object detection")


if __name__ == "__main__":
    main()

