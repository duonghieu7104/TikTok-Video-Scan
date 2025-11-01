#!/usr/bin/env python3
"""
Local Whisper Demo: Extract speech/transcription from Vietnamese videos
Reads videos from ./data folder and saves transcripts locally
"""
import os
import json
import whisper
import subprocess
from datetime import datetime
from pathlib import Path

# Configuration
DATA_FOLDER = "./data"
OUTPUT_FOLDER = "./output/whisper"
WHISPER_MODEL = "base"  # Options: tiny, base, small, medium, large
LANGUAGE = "vi"  # Vietnamese (or None for auto-detect)

# Create output folder
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


def extract_audio_from_video(video_path, audio_path):
    """Extract audio from video using ffmpeg"""
    cmd = [
        'ffmpeg', '-i', video_path,
        '-vn', '-acodec', 'libmp3lame',
        '-ar', '16000', '-ac', '1',
        '-y', audio_path
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    print(f"✓ Audio extracted: {audio_path}")


def transcribe_video_local(video_path):
    """Transcribe video using Whisper"""
    video_name = Path(video_path).stem
    print(f"\n{'='*60}")
    print(f"Processing video: {video_name}")
    print(f"{'='*60}")
    
    # Load Whisper model
    print(f"Loading Whisper model: {WHISPER_MODEL}...")
    model = whisper.load_model(WHISPER_MODEL)
    print("✓ Model loaded successfully")
    
    # Extract audio
    audio_path = f"{OUTPUT_FOLDER}/{video_name}_audio.mp3"
    try:
        extract_audio_from_video(video_path, audio_path)
    except Exception as e:
        print(f"✗ Error extracting audio: {e}")
        return None
    
    # Transcribe using Whisper
    try:
        print("Transcribing audio... (this may take a while)")
        result = model.transcribe(
            audio_path,
            language=LANGUAGE,  # Vietnamese
            task="transcribe",
            verbose=False
        )
        print("✓ Transcription completed")
        
        # Prepare transcript data
        transcript_data = {
            'video_file': video_path,
            'video_name': video_name,
            'text': result['text'],
            'language': result.get('language', LANGUAGE),
            'segments': result.get('segments', []),
            'transcribed_at': datetime.now().isoformat(),
            'model': WHISPER_MODEL
        }
        
        # Save transcript as JSON
        transcript_json = f"{OUTPUT_FOLDER}/{video_name}_transcript.json"
        with open(transcript_json, 'w', encoding='utf-8') as f:
            json.dump(transcript_data, f, indent=2, ensure_ascii=False)
        print(f"✓ Saved JSON transcript: {transcript_json}")
        
        # Save plain text transcript
        transcript_txt = f"{OUTPUT_FOLDER}/{video_name}_transcript.txt"
        with open(transcript_txt, 'w', encoding='utf-8') as f:
            f.write(result['text'])
        print(f"✓ Saved text transcript: {transcript_txt}")
        
        # Print summary
        print(f"\n{'─'*60}")
        print(f"Transcription Summary:")
        print(f"  Language detected: {result.get('language', LANGUAGE)}")
        print(f"  Total segments: {len(result.get('segments', []))}")
        print(f"  Text length: {len(result['text'])} characters")
        print(f"  Preview:")
        print(f"  {result['text'][:200]}...")
        print(f"{'─'*60}\n")
        
        # Optional: Save segments with timestamps
        segments_txt = f"{OUTPUT_FOLDER}/{video_name}_segments.txt"
        with open(segments_txt, 'w', encoding='utf-8') as f:
            for segment in result.get('segments', []):
                start = segment.get('start', 0)
                end = segment.get('end', 0)
                text = segment.get('text', '').strip()
                f.write(f"[{start:.2f}s - {end:.2f}s] {text}\n")
        print(f"✓ Saved segments with timestamps: {segments_txt}\n")
        
        return transcript_data
        
    except Exception as e:
        print(f"✗ Error transcribing: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Main function"""
    print("="*60)
    print("Whisper Local Demo - Vietnamese Video Transcription")
    print("="*60)
    
    # Check data folder
    data_path = Path(DATA_FOLDER)
    if not data_path.exists():
        print(f"✗ Error: Data folder not found: {DATA_FOLDER}")
        print(f"  Please create the folder and add video files.")
        return
    
    # Find video files
    video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.webm', '.m4v']
    video_files = []
    
    for ext in video_extensions:
        video_files.extend(list(data_path.glob(f'*{ext}')))
        video_files.extend(list(data_path.glob(f'*{ext.upper()}')))
    
    if not video_files:
        print(f"✗ No video files found in {DATA_FOLDER}")
        print(f"  Supported formats: {', '.join(video_extensions)}")
        return
    
    print(f"\nFound {len(video_files)} video file(s):")
    for i, video_file in enumerate(video_files, 1):
        print(f"  {i}. {video_file.name}")
    
    # Process all videos
    results = []
    for video_file in video_files:
        result = transcribe_video_local(str(video_file))
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
