-- PostgreSQL Schema for TikTok Video Scan System

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Videos table - Main table for video information
CREATE TABLE IF NOT EXISTS videos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    video_url TEXT NOT NULL UNIQUE,
    video_id TEXT NOT NULL UNIQUE,
    title TEXT,
    description TEXT,
    channel TEXT,
    channel_id TEXT,
    account TEXT,
    duration INTEGER, -- in seconds
    view_count BIGINT,
    like_count BIGINT,
    upload_date DATE,
    thumbnail_url TEXT,
    video_object TEXT, -- MinIO object path
    metadata_object TEXT, -- MinIO metadata path
    thumbnail_object TEXT, -- MinIO thumbnail path
    extractor TEXT,
    webpage_url TEXT,
    downloaded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Hashtags table
CREATE TABLE IF NOT EXISTS hashtags (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    video_id UUID NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    hashtag TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(video_id, hashtag)
);

-- Transcripts table - Whisper results
CREATE TABLE IF NOT EXISTS transcripts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    video_id UUID NOT NULL UNIQUE REFERENCES videos(id) ON DELETE CASCADE,
    text TEXT,
    language TEXT,
    transcript_json_object TEXT, -- MinIO object path
    transcript_txt_object TEXT, -- MinIO object path
    transcribed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Transcript segments table - Detailed segments from Whisper
CREATE TABLE IF NOT EXISTS transcript_segments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    transcript_id UUID NOT NULL REFERENCES transcripts(id) ON DELETE CASCADE,
    start REAL,
    "end" REAL,
    text TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- OCR results table
CREATE TABLE IF NOT EXISTS ocr_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    video_id UUID NOT NULL UNIQUE REFERENCES videos(id) ON DELETE CASCADE,
    all_text TEXT,
    total_frames INTEGER,
    frames_with_text INTEGER,
    ocr_json_object TEXT, -- MinIO object path
    ocr_txt_object TEXT, -- MinIO object path
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- OCR frame results table
CREATE TABLE IF NOT EXISTS ocr_frames (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ocr_result_id UUID NOT NULL REFERENCES ocr_results(id) ON DELETE CASCADE,
    frame_number INTEGER,
    timestamp REAL,
    filename TEXT,
    frame_object TEXT, -- MinIO object path
    ocr_text TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Object detections table
CREATE TABLE IF NOT EXISTS object_detections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    video_id UUID NOT NULL UNIQUE REFERENCES videos(id) ON DELETE CASCADE,
    total_frames_processed INTEGER,
    total_detections INTEGER,
    model TEXT,
    confidence_threshold REAL,
    detections_json_object TEXT, -- MinIO object path
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Detected products table
CREATE TABLE IF NOT EXISTS detected_products (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    detection_id UUID NOT NULL REFERENCES object_detections(id) ON DELETE CASCADE,
    product_name TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(detection_id, product_name)
);

-- Detection frame results table
CREATE TABLE IF NOT EXISTS detection_frames (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    detection_id UUID NOT NULL REFERENCES object_detections(id) ON DELETE CASCADE,
    frame_number INTEGER,
    timestamp REAL,
    total_detections INTEGER,
    frame_object TEXT, -- MinIO object path (annotated frame)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Detection details table - Individual object detections
CREATE TABLE IF NOT EXISTS detection_details (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    detection_frame_id UUID NOT NULL REFERENCES detection_frames(id) ON DELETE CASCADE,
    class_id INTEGER,
    class_name TEXT NOT NULL,
    confidence REAL,
    bbox_x1 REAL,
    bbox_y1 REAL,
    bbox_x2 REAL,
    bbox_y2 REAL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_videos_video_id ON videos(video_id);
CREATE INDEX IF NOT EXISTS idx_videos_video_url ON videos(video_url);
CREATE INDEX IF NOT EXISTS idx_hashtags_video_id ON hashtags(video_id);
CREATE INDEX IF NOT EXISTS idx_hashtags_hashtag ON hashtags(hashtag);
CREATE INDEX IF NOT EXISTS idx_transcripts_video_id ON transcripts(video_id);
CREATE INDEX IF NOT EXISTS idx_ocr_results_video_id ON ocr_results(video_id);
CREATE INDEX IF NOT EXISTS idx_object_detections_video_id ON object_detections(video_id);
CREATE INDEX IF NOT EXISTS idx_detected_products_detection_id ON detected_products(detection_id);
CREATE INDEX IF NOT EXISTS idx_detected_products_product_name ON detected_products(product_name);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger to auto-update updated_at
CREATE TRIGGER update_videos_updated_at BEFORE UPDATE ON videos
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

