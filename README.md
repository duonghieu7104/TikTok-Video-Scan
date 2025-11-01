# TikTok Video Scan System

Hệ thống phân tích video TikTok tự động sử dụng AI: Trích xuất lời thoại (Whisper), nhận diện chữ (OCR), và phát hiện sản phẩm (Object Detection).

<img width="1542" height="562" alt="image" src="https://github.com/user-attachments/assets/b7ca26f2-5a94-4ced-b546-07e5d60b4647" />

## Tính năng

- 🎤 **Trích xuất lời thoại**: Sử dụng OpenAI Whisper để chuyển đổi giọng nói thành văn bản (hỗ trợ tiếng Việt)
- 📝 **Nhận diện chữ trên video**: Sử dụng EasyOCR để nhận diện text hiển thị trên video
- 🔍 **Phát hiện sản phẩm**: Sử dụng YOLOv8 để phát hiện đối tượng/sản phẩm trong video
- 🤖 **Tóm tắt AI**: Sử dụng Gemini 2.5 Flash để tạo tóm tắt video dễ hiểu

---

# Demo Local

Chạy các demo trên máy local để phân tích video.

## Yêu cầu hệ thống

- Python 3.11 hoặc cao hơn
- ffmpeg (để xử lý video)
- Git (để clone repository)

### Cài đặt ffmpeg

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install ffmpeg
```

**Fedora:**
```bash
sudo dnf install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

## Cài đặt

### 1. Clone repository

```bash
git clone <repository-url>
cd TikTok-Video-Scan
```

### 2. Tạo virtual environment

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# hoặc
venv\Scripts\activate  # Windows
```

### 3. Cài đặt dependencies

```bash
pip install -r requirements_local.txt
```

**Lưu ý:** Lần đầu chạy sẽ tự động tải xuống các models:
- Whisper model (~74MB cho base model)
- EasyOCR models (~100-200MB)
- YOLOv8 model (~6MB cho nano model)

### 4. Cấu hình Gemini API (tùy chọn)

Để sử dụng tính năng tóm tắt AI, tạo file `.env`:

```bash
cp .env.example .env
```

Sau đó chỉnh sửa `.env` và thêm Gemini API key:

```
GEMINI_API_KEY=your_gemini_api_key_here
```

Lấy API key tại: https://aistudio.google.com/app/apikey

## Sử dụng

### Bước 1: Thêm video vào thư mục `data/`

```bash
mkdir -p data
# Copy các file video (.mp4, .avi, .mov, v.v.) vào thư mục data/
cp /path/to/your/videos/*.mp4 data/
```

### Bước 2: Chạy các demo

#### Demo 1: Trích xuất lời thoại (Whisper)

```bash
python demo_whisper_local.py
```

**Output:** `./output/whisper/`
- `{video_name}_transcript.json` - Transcript đầy đủ với segments
- `{video_name}_transcript.txt` - Transcript dạng text
- `{video_name}_segments.txt` - Segments với timestamps

#### Demo 2: Nhận diện chữ trên video (OCR)

```bash
python demo_ocr_local.py
```

**Output:** `./output/ocr/`
- `{video_name}_ocr.json` - Kết quả OCR đầy đủ
- `{video_name}_ocr.txt` - Tất cả text đã nhận diện
- `{video_name}_frames/` - Các frame đã trích xuất

#### Demo 3: Phát hiện sản phẩm (Object Detection)

```bash
python demo_detector_local.py
```

**Output:** `./output/detector/`
- `{video_name}_detections.json` - Kết quả phát hiện đầy đủ
- `{video_name}_detected_frames/` - Frames với bounding boxes

#### Demo 4: Tổng hợp kết quả (Aggregate)

```bash
python demo_aggregate_results.py
```

**Output:** `./output/aggregated/`
- `{video_name}_aggregated.json` - Dữ liệu tổng hợp dạng JSON
- `{video_name}_aggregated.txt` - Báo cáo dạng text (có AI summary nếu đã cấu hình Gemini)

## Cấu trúc Output

Sau khi chạy tất cả các demo, bạn sẽ có:

```
output/
├── whisper/
│   ├── {video_name}_transcript.json
│   ├── {video_name}_transcript.txt
│   └── {video_name}_segments.txt
├── ocr/
│   ├── {video_name}_ocr.json
│   ├── {video_name}_ocr.txt
│   └── {video_name}_frames/
├── detector/
│   ├── {video_name}_detections.json
│   └── {video_name}_detected_frames/
└── aggregated/
    ├── {video_name}_aggregated.json
    ├── {video_name}_aggregated.txt
    └── all_videos_summary.json
```

## Output

### File tổng hợp (`aggregated.txt`):



## Cấu hình nâng cao

### Thay đổi Whisper model

Chỉnh sửa `demo_whisper_local.py`:

```python
WHISPER_MODEL = "small"  # tiny, base, small, medium, large
```

### Thay đổi OCR engine

Chỉnh sửa `demo_ocr_local.py`:

```python
OCR_ENGINE = "tesseract"  # easyocr hoặc tesseract
```

### Thay đổi YOLO model

Chỉnh sửa `demo_detector_local.py`:

```python
YOLO_MODEL = "yolov8s.pt"  # yolov8n, yolov8s, yolov8m, yolov8l, yolov8x
```

### Lỗi thiếu ffmpeg

```bash
# Kiểm tra ffmpeg đã cài đặt chưa
ffmpeg -version

# Nếu chưa có, cài đặt theo hướng dẫn ở phần "Yêu cầu hệ thống"
```

### Lỗi Out of Memory

- Giảm `MAX_FRAMES` trong các file demo
- Sử dụng model nhỏ hơn (tiny/small cho Whisper, nano cho YOLO)

### Models download chậm

- Models sẽ được cache sau lần tải đầu tiên
- Có thể tải thủ công và đặt vào thư mục cache tương ứng

---

# Build Lake House Docker

Xây dựng hệ thống data lake house với Docker containers để xử lý video và lưu trữ dữ liệu có cấu trúc.

