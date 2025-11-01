#!/usr/bin/env python3
"""
Aggregate Results Demo: Combine Whisper, OCR, and Object Detection results
into a single structured file for each video
Includes Gemini AI summary for easier understanding
"""
import os
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables
load_dotenv()

# Configuration
WHISPER_OUTPUT = "./output/whisper"
OCR_OUTPUT = "./output/ocr"
DETECTOR_OUTPUT = "./output/detector"
AGGREGATE_OUTPUT = "./output/aggregated"

# Gemini API Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-2.5-flash"  # or "gemini-1.5-flash" if 2.0 not available

# Initialize Gemini if API key is provided
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    print(f"✓ Gemini API configured (Model: {GEMINI_MODEL})")
else:
    print("⚠ Gemini API key not found. Summarization will be skipped.")
    print("  Set GEMINI_API_KEY in .env file to enable AI summaries")

# Create output folder
os.makedirs(AGGREGATE_OUTPUT, exist_ok=True)


def generate_ai_summary(video_data):
    """Generate AI summary using Gemini 2.5 Flash"""
    if not GEMINI_API_KEY:
        return None
    
    try:
        # Prepare prompt with video data (Vietnamese)
        prompt = f"""Bạn đang phân tích một video TikTok. Hãy tóm tắt nội dung video một cách ngắn gọn và dễ hiểu bằng tiếng Việt.

Dữ liệu phân tích video:

1. CHỮ HIỂN THỊ TRÊN VIDEO (OCR):
{video_data.get('text_on_video', 'Không có')}

2. LỜI THOẠI/TRANSCCIPTION (Whisper):
{video_data.get('whisper_content', 'Không có')}

3. ĐỐI TƯỢNG ĐƯỢC PHÁT HIỆN:
{', '.join(video_data.get('detected_objects', [])) if video_data.get('detected_objects') else 'Không có'}

4. SẢN PHẨM ĐƯỢC TÌM THẤY:
{', '.join(video_data.get('detected_products', [])) if video_data.get('detected_products') else 'Không có'}

Hãy cung cấp:
- Tóm tắt ngắn gọn video nói về gì (2-3 câu)
- Thông tin chính hoặc thông điệp chính
- Sản phẩm hoặc mặt hàng được đề cập/hiển thị
- Các chi tiết quan trọng khác

Viết tóm tắt bằng tiếng Việt, rõ ràng và ngắn gọn."""

        # Use Gemini API
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(prompt)
        
        return response.text.strip()
        
    except Exception as e:
        print(f"  ✗ Error generating AI summary: {e}")
        return None


def load_whisper_results(video_name):
    """Load Whisper transcript results"""
    transcript_json = f"{WHISPER_OUTPUT}/{video_name}_transcript.json"
    
    if not os.path.exists(transcript_json):
        return None
    
    try:
        with open(transcript_json, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return {
            'text': data.get('text', '').strip(),
            'language': data.get('language', 'unknown'),
            'segments_count': len(data.get('segments', []))
        }
    except Exception as e:
        print(f"  ✗ Error loading Whisper results: {e}")
        return None


def load_ocr_results(video_name):
    """Load OCR results"""
    ocr_json = f"{OCR_OUTPUT}/{video_name}_ocr.json"
    
    if not os.path.exists(ocr_json):
        return None
    
    try:
        with open(ocr_json, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Get all text from OCR (combine all frames)
        all_text = data.get('all_text', '').strip()
        
        # Extract unique text lines (remove timestamps for cleaner output)
        text_lines = []
        for line in all_text.split('\n'):
            if line.strip() and not line.strip().startswith('['):
                text_lines.append(line.strip())
        
        return {
            'text_on_video': ' '.join(text_lines) if text_lines else '',
            'total_frames': data.get('total_frames', 0),
            'frames_with_text': data.get('frames_with_text', 0),
            'raw_text': all_text
        }
    except Exception as e:
        print(f"  ✗ Error loading OCR results: {e}")
        return None


def load_detector_results(video_name):
    """Load Object Detection results"""
    detector_json = f"{DETECTOR_OUTPUT}/{video_name}_detections.json"
    
    if not os.path.exists(detector_json):
        return None
    
    try:
        with open(detector_json, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Get all detected objects (including products)
        detected_products = data.get('detected_products', [])
        
        # Get all unique objects detected across all frames
        all_objects = set()
        for frame_result in data.get('frame_results', []):
            for detection in frame_result.get('detections', []):
                all_objects.add(detection.get('class_name', ''))
        
        return {
            'detected_products': detected_products,
            'all_detected_objects': sorted(list(all_objects)),
            'total_detections': data.get('total_detections', 0),
            'frames_processed': data.get('total_frames_processed', 0)
        }
    except Exception as e:
        print(f"  ✗ Error loading Detector results: {e}")
        return None


def aggregate_video_results(video_name):
    """Aggregate all results for a single video"""
    print(f"\nProcessing: {video_name}")
    
    whisper_data = load_whisper_results(video_name)
    ocr_data = load_ocr_results(video_name)
    detector_data = load_detector_results(video_name)
    
    # Build aggregated structure
    aggregated = {
        'video_name': video_name,
        'processed_at': datetime.now().isoformat(),
        'text_on_video': ocr_data.get('text_on_video', '') if ocr_data else '',
        'whisper_content': whisper_data.get('text', '') if whisper_data else '',
        'detected_objects': detector_data.get('all_detected_objects', []) if detector_data else [],
        'detected_products': detector_data.get('detected_products', []) if detector_data else []
    }
    
    # Add metadata (optional, for reference)
    if whisper_data:
        aggregated['whisper_language'] = whisper_data.get('language', '')
        aggregated['whisper_segments'] = whisper_data.get('segments_count', 0)
    
    if ocr_data:
        aggregated['ocr_frames_processed'] = ocr_data.get('total_frames', 0)
        aggregated['ocr_frames_with_text'] = ocr_data.get('frames_with_text', 0)
    
    if detector_data:
        aggregated['detection_total_objects'] = detector_data.get('total_detections', 0)
        aggregated['detection_frames_processed'] = detector_data.get('frames_processed', 0)
    
    # Generate AI summary if API key is available
    if GEMINI_API_KEY:
        print("  Generating AI summary...", end=' ')
        ai_summary = generate_ai_summary(aggregated)
        if ai_summary:
            aggregated['ai_summary'] = ai_summary
            print("✓")
        else:
            print("✗")
            aggregated['ai_summary'] = ''
    else:
        aggregated['ai_summary'] = ''
    
    return aggregated


def find_all_videos():
    """Find all videos that have been processed (have at least one result file)"""
    video_names = set()
    
    # Check Whisper output
    if os.path.exists(WHISPER_OUTPUT):
        for file in os.listdir(WHISPER_OUTPUT):
            if file.endswith('_transcript.json'):
                video_name = file.replace('_transcript.json', '')
                video_names.add(video_name)
    
    # Check OCR output
    if os.path.exists(OCR_OUTPUT):
        for file in os.listdir(OCR_OUTPUT):
            if file.endswith('_ocr.json'):
                video_name = file.replace('_ocr.json', '')
                video_names.add(video_name)
    
    # Check Detector output
    if os.path.exists(DETECTOR_OUTPUT):
        for file in os.listdir(DETECTOR_OUTPUT):
            if file.endswith('_detections.json'):
                video_name = file.replace('_detections.json', '')
                video_names.add(video_name)
    
    return sorted(list(video_names))


def main():
    """Main function"""
    print("="*60)
    print("Aggregate Results - Combine All Analysis Data")
    print("="*60)
    
    if GEMINI_API_KEY:
        print("AI Summary: Enabled (Gemini)")
    else:
        print("AI Summary: Disabled (no API key)")
    
    # Find all processed videos
    video_names = find_all_videos()
    
    if not video_names:
        print("\n✗ No processed videos found!")
        print(f"  Make sure you've run:")
        print(f"    - demo_whisper_local.py")
        print(f"    - demo_ocr_local.py")
        print(f"    - demo_detector_local.py")
        return
    
    print(f"\nFound {len(video_names)} processed video(s):")
    for i, name in enumerate(video_names, 1):
        print(f"  {i}. {name}")
    
    # Process each video
    all_results = []
    for video_name in video_names:
        result = aggregate_video_results(video_name)
        if result:
            all_results.append(result)
    
    # Save individual JSON files
    print(f"\n{'='*60}")
    print("Saving Results")
    print(f"{'='*60}")
    
    for result in all_results:
        video_name = result['video_name']
        
        # Save as JSON
        json_file = f"{AGGREGATE_OUTPUT}/{video_name}_aggregated.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"✓ Saved: {json_file}")
        
        # Save as readable text file
        txt_file = f"{AGGREGATE_OUTPUT}/{video_name}_aggregated.txt"
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write("="*60 + "\n")
            f.write(f"Video Analysis Results\n")
            f.write("="*60 + "\n\n")
            
            f.write(f"Video Name: {result['video_name']}\n")
            f.write(f"Processed At: {result['processed_at']}\n\n")
            
            # AI Summary section (if available)
            if result.get('ai_summary'):
                f.write("="*60 + "\n")
                f.write("AI SUMMARY (Gemini 2.5 Flash)\n")
                f.write("="*60 + "\n")
                f.write(f"{result['ai_summary']}\n\n")
            
            f.write("-"*60 + "\n")
            f.write("TEXT ON VIDEO (OCR)\n")
            f.write("-"*60 + "\n")
            f.write(f"{result['text_on_video']}\n\n")
            
            f.write("-"*60 + "\n")
            f.write("WHISPER CONTENT (Speech Transcription)\n")
            f.write("-"*60 + "\n")
            f.write(f"{result['whisper_content']}\n\n")
            
            f.write("-"*60 + "\n")
            f.write("DETECTED OBJECTS\n")
            f.write("-"*60 + "\n")
            if result['detected_objects']:
                f.write(f"All Objects: {', '.join(result['detected_objects'])}\n")
            else:
                f.write("No objects detected\n")
            f.write("\n")
            
            if result['detected_products']:
                f.write(f"Products Found: {', '.join(result['detected_products'])}\n")
            else:
                f.write("No products detected\n")
            f.write("\n")
            
        print(f"✓ Saved: {txt_file}")
    
    # Save combined summary
    summary_file = f"{AGGREGATE_OUTPUT}/all_videos_summary.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"✓ Saved summary: {summary_file}")
    
    # Print summary
    print(f"\n{'='*60}")
    print("Summary")
    print(f"{'='*60}")
    print(f"Total videos aggregated: {len(all_results)}")
    print(f"Output folder: {AGGREGATE_OUTPUT}")
    print("="*60)
    
    # Print preview
    if all_results:
        print(f"\nPreview of first video:")
        first = all_results[0]
        print(f"  Video: {first['video_name']}")
        if first.get('ai_summary'):
            print(f"  AI Summary: {first['ai_summary'][:150]}...")
        print(f"  Text on video: {first['text_on_video'][:100]}..." if first['text_on_video'] else "  Text on video: (none)")
        print(f"  Whisper: {first['whisper_content'][:100]}..." if first['whisper_content'] else "  Whisper: (none)")
        print(f"  Objects: {', '.join(first['detected_objects'][:10])}" if first['detected_objects'] else "  Objects: (none)")
        if first['detected_products']:
            print(f"  Products: {', '.join(first['detected_products'])}")


if __name__ == "__main__":
    main()
