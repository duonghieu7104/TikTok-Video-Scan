#!/bin/bash
# Helper script to process a video through the entire pipeline

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if VIDEO_URL is provided
if [ -z "$1" ]; then
    echo -e "${RED}Usage: $0 <video_url>${NC}"
    echo "Example: $0 https://www.tiktok.com/@username/video/1234567890"
    exit 1
fi

VIDEO_URL="$1"
export VIDEO_URL

echo -e "${GREEN}=== TikTok Video Scan Pipeline ===${NC}"
echo ""

# Step 1: Start infrastructure services
echo -e "${YELLOW}Step 1: Starting infrastructure services (MinIO, PostgreSQL)...${NC}"
docker-compose up -d minio postgres

echo "Waiting for services to be healthy..."
sleep 10

# Step 2: Download video
echo -e "${YELLOW}Step 2: Downloading video and extracting metadata...${NC}"
DOWNLOAD_OUTPUT=$(docker-compose run --rm yt-dlp 2>&1)

# Extract VIDEO_ID from output
VIDEO_ID=$(echo "$DOWNLOAD_OUTPUT" | grep -oP 'video_id["\s:]+["\s]+([^"]+)' | head -1 | sed 's/.*"\(.*\)".*/\1/')
if [ -z "$VIDEO_ID" ]; then
    VIDEO_ID=$(echo "$DOWNLOAD_OUTPUT" | grep -i "video_id" | head -1 | awk '{print $NF}' | tr -d '"')
fi

if [ -z "$VIDEO_ID" ]; then
    echo -e "${RED}Error: Could not extract VIDEO_ID from download output${NC}"
    echo "Download output:"
    echo "$DOWNLOAD_OUTPUT"
    exit 1
fi

export VIDEO_ID
export VIDEO_OBJECT="${VIDEO_ID}/video.mp4"

echo -e "${GREEN}Video downloaded successfully!${NC}"
echo "VIDEO_ID: $VIDEO_ID"
echo "VIDEO_OBJECT: $VIDEO_OBJECT"
echo ""

# Step 3: Process in parallel (Whisper, OCR, Detector)
echo -e "${YELLOW}Step 3: Processing video (Whisper, OCR, Object Detection)...${NC}"

echo "Starting Whisper..."
docker-compose run --rm whisper > /tmp/whisper.log 2>&1 &
WHISPER_PID=$!

echo "Starting OCR..."
docker-compose run --rm ocr > /tmp/ocr.log 2>&1 &
OCR_PID=$!

echo "Starting Object Detection..."
docker-compose run --rm detector > /tmp/detector.log 2>&1 &
DETECTOR_PID=$!

echo "Waiting for processing to complete..."
wait $WHISPER_PID
WHISPER_EXIT=$?

wait $OCR_PID
OCR_EXIT=$?

wait $DETECTOR_PID
DETECTOR_EXIT=$?

if [ $WHISPER_EXIT -ne 0 ]; then
    echo -e "${RED}Whisper processing failed${NC}"
    cat /tmp/whisper.log
fi

if [ $OCR_EXIT -ne 0 ]; then
    echo -e "${RED}OCR processing failed${NC}"
    cat /tmp/ocr.log
fi

if [ $DETECTOR_EXIT -ne 0 ]; then
    echo -e "${RED}Object Detection processing failed${NC}"
    cat /tmp/detector.log
fi

if [ $WHISPER_EXIT -ne 0 ] || [ $OCR_EXIT -ne 0 ] || [ $DETECTOR_EXIT -ne 0 ]; then
    echo -e "${RED}Some processing steps failed. Check logs above.${NC}"
    exit 1
fi

echo -e "${GREEN}All processing completed successfully!${NC}"
echo ""

# Step 4: Aggregate data
echo -e "${YELLOW}Step 4: Aggregating data and saving to PostgreSQL...${NC}"
docker-compose run --rm aggregator

if [ $? -eq 0 ]; then
    echo -e "${GREEN}=== Pipeline completed successfully! ===${NC}"
    echo ""
    echo "You can now query the database:"
    echo "  docker-compose exec postgres psql -U postgres -d tiktok_video_scan"
    echo ""
    echo "Or access MinIO console at:"
    echo "  http://localhost:9001 (minioadmin/minioadmin)"
else
    echo -e "${RED}Aggregation failed${NC}"
    exit 1
fi

