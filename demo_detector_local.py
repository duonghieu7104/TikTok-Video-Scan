#!/usr/bin/env python3
"""
Local Object Detection Demo: Detect products/objects in video frames using YOLOv8
Reads videos from ./data folder and saves detection results locally
"""
import os
import json
import cv2
import numpy as np
from pathlib import Path
from datetime import datetime
from ultralytics import YOLO

# Configuration
DATA_FOLDER = "./data"
OUTPUT_FOLDER = "./output/detector"
YOLO_MODEL = "yolov8n.pt"  # Options: yolov8n, yolov8s, yolov8m, yolov8l, yolov8x (n=nano, s=small, m=medium, l=large, x=xlarge)
CONFIDENCE_THRESHOLD = 0.25  # Minimum confidence for detection (0.0-1.0)
FRAME_INTERVAL = 5  # Extract frame every N seconds
MAX_FRAMES = 10  # Maximum frames to process per video

# Product-related classes (COCO dataset classes - adjust as needed)
# These are classes that might be products in TikTok videos
PRODUCT_CLASSES = {
    39: 'bottle', 40: 'wine glass', 41: 'cup', 44: 'bowl',
    46: 'banana', 47: 'apple', 48: 'sandwich', 49: 'orange',
    50: 'broccoli', 51: 'carrot', 52: 'hot dog', 53: 'pizza',
    54: 'donut', 55: 'cake', 67: 'cell phone', 73: 'book',
    74: 'clock', 76: 'vase', 77: 'scissors', 78: 'teddy bear'
}

# Create output folder
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Load YOLO model
print(f"Loading YOLO model: {YOLO_MODEL}...")
print("(First run will download the model - this may take a while)")
yolo_model = YOLO(YOLO_MODEL)
print("✓ YOLO model loaded successfully")


def convert_numpy_types(obj):
    """Convert NumPy types to native Python types for JSON serialization"""
    # Handle NumPy scalar types
    if isinstance(obj, np.generic):
        return obj.item()  # Convert NumPy scalar to Python native type
    # Handle NumPy arrays
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    # Handle dictionaries
    elif isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    # Handle lists and tuples
    elif isinstance(obj, (list, tuple)):
        return type(obj)(convert_numpy_types(item) for item in obj)
    else:
        return obj


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
    
    print(f"  Video: {duration:.2f}s, FPS: {fps:.2f}, Total frames: {total_frames}")
    
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
    print(f"  ✓ Extracted {len(frames)} frames for detection")
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
                'class_id': int(class_id),
                'class_name': class_name,
                'confidence': float(confidence),
                'bbox': {
                    'x1': float(x1),
                    'y1': float(y1),
                    'x2': float(x2),
                    'y2': float(y2)
                }
            }
            
            detections.append(detection)
            
            # Track if it's a potential product
            if class_id in PRODUCT_CLASSES:
                detected_products.add(class_name)
    
    return {
        'timestamp': float(timestamp),
        'detections': detections,
        'detected_products': list(detected_products),
        'total_detections': len(detections)
    }


def draw_detections(frame, detections):
    """Draw bounding boxes and labels on frame"""
    annotated_frame = frame.copy()
    
    for det in detections['detections']:
        bbox = det['bbox']
        x1, y1, x2, y2 = int(bbox['x1']), int(bbox['y1']), int(bbox['x2']), int(bbox['y2'])
        class_name = det['class_name']
        confidence = det['confidence']
        
        # Choose color based on whether it's a product
        color = (0, 255, 0) if class_name in detections['detected_products'] else (255, 0, 0)
        
        # Draw rectangle
        cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)
        
        # Draw label with background
        label = f"{class_name} {confidence:.2f}"
        (label_width, label_height), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
        cv2.rectangle(annotated_frame, (x1, y1 - label_height - 10), 
                     (x1 + label_width, y1), color, -1)
        cv2.putText(annotated_frame, label, (x1, y1 - 5),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
    
    return annotated_frame


def process_video_local(video_path):
    """Process video: extract frames, detect objects, save results"""
    video_name = Path(video_path).stem
    print(f"\n{'='*60}")
    print(f"Processing video: {video_name}")
    print(f"{'='*60}")
    
    # Create frames directory for this video
    frames_dir = f"{OUTPUT_FOLDER}/{video_name}_detected_frames"
    os.makedirs(frames_dir, exist_ok=True)
    
    try:
        # Extract frames
        print("Extracting frames...")
        frames = extract_frames_for_detection(video_path)
        
        if not frames:
            print("  ✗ No frames extracted")
            return None
        
        # Detect objects in each frame
        print("Detecting objects in frames...")
        detection_results = []
        all_products = set()
        
        for i, frame_info in enumerate(frames, 1):
            timestamp = frame_info['timestamp']
            print(f"  Frame {i}/{len(frames)} ({timestamp:.2f}s)...", end=' ')
            
            result = detect_objects_in_frame(frame_info['frame'], timestamp)
            detection_results.append({
                'frame_number': frame_info['frame_number'],
                **result
            })
            
            # Collect all products
            all_products.update(result['detected_products'])
            
            # Draw detections on frame
            annotated_frame = draw_detections(frame_info['frame'], result)
            
            # Save annotated frame
            frame_filename = f"frame_{frame_info['frame_number']:04d}_{timestamp:.2f}s_detected.jpg"
            frame_path = os.path.join(frames_dir, frame_filename)
            cv2.imwrite(frame_path, annotated_frame)
            
            if result['total_detections'] > 0:
                print(f"✓ Found {result['total_detections']} object(s): {', '.join(result['detected_products']) if result['detected_products'] else 'objects detected'}")
            else:
                print("✗ No objects detected")
        
        # Prepare detection summary
        detection_summary = {
            'video_file': str(video_path),
            'video_name': video_name,
            'total_frames_processed': len(detection_results),
            'total_detections': sum(r['total_detections'] for r in detection_results),
            'detected_products': sorted(list(all_products)),
            'frame_results': detection_results,
            'processed_at': datetime.now().isoformat(),
            'model': YOLO_MODEL,
            'confidence_threshold': CONFIDENCE_THRESHOLD,
            'frame_interval': FRAME_INTERVAL
        }
        
        # Convert NumPy types to native Python types
        detection_summary = convert_numpy_types(detection_summary)
        
        # Save detection results as JSON
        detection_json = f"{OUTPUT_FOLDER}/{video_name}_detections.json"
        with open(detection_json, 'w', encoding='utf-8') as f:
            json.dump(detection_summary, f, indent=2, ensure_ascii=False)
        print(f"✓ Saved detection JSON: {detection_json}")
        
        # Print summary
        print(f"\n{'─'*60}")
        print(f"Detection Summary:")
        print(f"  Total frames processed: {len(detection_results)}")
        print(f"  Total detections: {detection_summary['total_detections']}")
        print(f"  Unique products detected: {len(all_products)}")
        if all_products:
            print(f"  Products: {', '.join(sorted(all_products))}")
        print(f"  Annotated frames saved to: {frames_dir}")
        print(f"{'─'*60}\n")
        
        return detection_summary
        
    except Exception as e:
        print(f"✗ Error processing video: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Main function"""
    print("="*60)
    print("Object Detection Local Demo - YOLOv8 Product Detection")
    print("="*60)
    print(f"YOLO Model: {YOLO_MODEL}")
    print(f"Confidence Threshold: {CONFIDENCE_THRESHOLD}")
    print(f"Frame interval: {FRAME_INTERVAL} seconds")
    print(f"Max frames per video: {MAX_FRAMES}")
    
    # Check data folder
    data_path = Path(DATA_FOLDER)
    if not data_path.exists():
        print(f"\n✗ Error: Data folder not found: {DATA_FOLDER}")
        print(f"  Please create the folder and add video files.")
        return
    
    # Find video files
    video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.webm', '.m4v']
    video_files = []
    
    for ext in video_extensions:
        video_files.extend(list(data_path.glob(f'*{ext}')))
        video_files.extend(list(data_path.glob(f'*{ext.upper()}')))
    
    if not video_files:
        print(f"\n✗ No video files found in {DATA_FOLDER}")
        print(f"  Supported formats: {', '.join(video_extensions)}")
        return
    
    print(f"\nFound {len(video_files)} video file(s):")
    for i, video_file in enumerate(video_files, 1):
        print(f"  {i}. {video_file.name}")
    
    # Process all videos
    results = []
    for video_file in video_files:
        result = process_video_local(str(video_file))
        if result:
            results.append(result)
    
    # Summary
    print("\n" + "="*60)
    print("Processing Summary")
    print("="*60)
    print(f"Total videos processed: {len(results)}/{len(video_files)}")
    print(f"Output folder: {OUTPUT_FOLDER}")
    print("="*60)


if __name__ == "__main__":
    main()
