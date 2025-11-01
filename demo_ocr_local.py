#!/usr/bin/env python3
"""
Local OCR Demo: Extract frames from videos and recognize text displayed on video
Supports Vietnamese and English text recognition
"""
import os
import json
import cv2
import numpy as np
from pathlib import Path
from datetime import datetime
import easyocr
# Alternative: import pytesseract (if using Tesseract instead)

# Configuration
DATA_FOLDER = "./data"
OUTPUT_FOLDER = "./output/ocr"
FRAME_INTERVAL = 5  # Extract frame every N seconds
MAX_FRAMES = 10  # Maximum frames to process per video
OCR_ENGINE = "easyocr"  # Options: "easyocr" or "tesseract"
LANGUAGES = ['en', 'vi']  # English and Vietnamese

# Create output folder
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Initialize EasyOCR reader (done once, reused for all videos)
easyocr_reader = None
if OCR_ENGINE == "easyocr":
    print(f"Initializing EasyOCR with languages: {LANGUAGES}...")
    print("(First run will download models - this may take a while)")
    easyocr_reader = easyocr.Reader(LANGUAGES, gpu=False)
    print("✓ EasyOCR initialized")


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
    
    print(f"  Video: {duration:.2f}s, FPS: {fps:.2f}, Total frames: {total_frames}")
    
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
    print(f"  ✓ Extracted {len(extracted_frames)} frames")
    return extracted_frames


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
            'confidence': float(confidence),
            'bbox': bbox
        })
    
    return {
        'text': full_text,
        'words': words_data,
        'total_detections': len(words_data)
    }


def ocr_tesseract(image_path):
    """Perform OCR using Tesseract (alternative)"""
    import pytesseract
    from PIL import Image
    
    image = Image.open(image_path)
    text = pytesseract.image_to_string(image, lang='eng+vie')
    
    # Get detailed data
    data = pytesseract.image_to_data(image, lang='eng+vie', output_type=pytesseract.Output.DICT)
    
    words_data = []
    for i in range(len(data.get('text', []))):
        if data['text'][i].strip():
            words_data.append({
                'text': data['text'][i],
                'confidence': float(data['conf'][i]) if data['conf'][i] != -1 else 0,
                'bbox': [
                    data['left'][i], data['top'][i],
                    data['left'][i] + data['width'][i],
                    data['top'][i] + data['height'][i]
                ]
            })
    
    return {
        'text': text.strip(),
        'words': words_data,
        'total_detections': len(words_data)
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


def process_video_local(video_path):
    """Process video: extract frames, perform OCR, save results"""
    video_name = Path(video_path).stem
    print(f"\n{'='*60}")
    print(f"Processing video: {video_name}")
    print(f"{'='*60}")
    
    # Create frames directory for this video
    frames_dir = f"{OUTPUT_FOLDER}/{video_name}_frames"
    os.makedirs(frames_dir, exist_ok=True)
    
    try:
        # Extract frames
        print("Extracting frames...")
        frames = extract_frames(video_path, frames_dir)
        
        if not frames:
            print("  ✗ No frames extracted")
            return None
        
        # Perform OCR on each frame
        print("Performing OCR on frames...")
        ocr_results = []
        frames_with_text = 0
        
        for i, frame_info in enumerate(frames, 1):
            print(f"  Frame {i}/{len(frames)} ({frame_info['timestamp']:.2f}s)...", end=' ')
            ocr_result = perform_ocr_on_frame(frame_info['path'], frame_info)
            ocr_results.append(ocr_result)
            
            if ocr_result['ocr_text'].strip():
                frames_with_text += 1
                print(f"✓ Found text: {len(ocr_result['ocr_text'])} chars")
            else:
                print("✗ No text detected")
        
        # Aggregate all OCR text
        all_text_parts = []
        for result in ocr_results:
            if result['ocr_text'].strip():
                timestamp = result['timestamp']
                text = result['ocr_text']
                all_text_parts.append(f"[{timestamp:.2f}s] {text}")
        
        all_text = '\n\n'.join(all_text_parts)
        
        # Prepare OCR summary
        ocr_summary = {
            'video_file': str(video_path),
            'video_name': video_name,
            'total_frames': len(ocr_results),
            'frames_with_text': frames_with_text,
            'all_text': all_text,
            'frame_results': ocr_results,
            'processed_at': datetime.now().isoformat(),
            'ocr_engine': OCR_ENGINE,
            'frame_interval': FRAME_INTERVAL
        }
        
        # Convert NumPy types to native Python types before JSON serialization
        ocr_summary = convert_numpy_types(ocr_summary)
        
        # Save OCR results as JSON
        ocr_json = f"{OUTPUT_FOLDER}/{video_name}_ocr.json"
        with open(ocr_json, 'w', encoding='utf-8') as f:
            json.dump(ocr_summary, f, indent=2, ensure_ascii=False)
        print(f"✓ Saved OCR JSON: {ocr_json}")
        
        # Save plain text OCR results
        ocr_txt = f"{OUTPUT_FOLDER}/{video_name}_ocr.txt"
        with open(ocr_txt, 'w', encoding='utf-8') as f:
            f.write(all_text)
        print(f"✓ Saved OCR text: {ocr_txt}")
        
        # Print summary
        print(f"\n{'─'*60}")
        print(f"OCR Summary:")
        print(f"  Total frames processed: {len(ocr_results)}")
        print(f"  Frames with text: {frames_with_text}")
        print(f"  Total text detected: {len(all_text)} characters")
        if all_text:
            print(f"  Preview:")
            preview = all_text[:200].replace('\n', ' ')
            print(f"  {preview}...")
        print(f"{'─'*60}\n")
        
        return ocr_summary
        
    except Exception as e:
        print(f"✗ Error processing video: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Main function"""
    print("="*60)
    print("OCR Local Demo - Text Recognition from Video Frames")
    print("="*60)
    print(f"OCR Engine: {OCR_ENGINE}")
    print(f"Languages: {LANGUAGES}")
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
