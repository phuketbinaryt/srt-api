# Audio Transcription API

A FastAPI-based service that converts audio files to SRT subtitle files using OpenAI Whisper for automatic speech recognition.

## Features

- **Audio to SRT Conversion**: Upload audio files and receive properly formatted SRT subtitle files
- **Multiple Format Support**: Supports MP3, WAV, M4A, FLAC, OGG, and WMA audio formats
- **Automatic Language Detection**: Uses OpenAI Whisper to automatically detect the spoken language
- **Large File Support**: Handles files up to 100MB in size
- **Timestamp Accuracy**: Generates precise timestamps for subtitle segments
- **RESTful API**: Clean REST API with automatic documentation
- **Error Handling**: Comprehensive error handling for unsupported formats and transcription failures

## Requirements

- Python 3.8 or higher
- FFmpeg (required by Whisper for audio processing)

## Installation

1. **Clone or download the project files**

2. **Install FFmpeg** (required for audio processing):
   
   **macOS:**
   ```bash
   brew install ffmpeg
   ```
   
   **Ubuntu/Debian:**
   ```bash
   sudo apt update
   sudo apt install ffmpeg
   ```
   
   **Windows:**
   Download from https://ffmpeg.org/download.html and add to PATH

3. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

4. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

5. **Copy environment configuration:**
   ```bash
   cp .env.example .env
   ```

## Usage

### Starting the Server

**Option 1: Using the startup script (recommended)**
```bash
python start.py
```

**Option 2: Using uvicorn directly**
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at:
- **API Base URL**: http://localhost:8000
- **Interactive Documentation**: http://localhost:8000/docs
- **Alternative Documentation**: http://localhost:8000/redoc

### API Endpoints

#### POST /upload
Upload an audio file and receive an SRT subtitle file.

**Request:**
- Method: `POST`
- Content-Type: `multipart/form-data`
- Body: Audio file (form field name: `file`)

**Response:**
- Content-Type: `application/x-subrip`
- Body: SRT file download

**Example using curl:**
```bash
curl -X POST "http://localhost:8000/upload" \
     -H "accept: application/x-subrip" \
     -H "Content-Type: multipart/form-data" \
     -F "file=@your_audio_file.mp3" \
     --output subtitles.srt
```

**Example using Python requests:**
```python
import requests

url = "http://localhost:8000/upload"
files = {"file": open("your_audio_file.mp3", "rb")}

response = requests.post(url, files=files)

if response.status_code == 200:
    with open("subtitles.srt", "wb") as f:
        f.write(response.content)
    print("SRT file saved as subtitles.srt")
else:
    print(f"Error: {response.status_code} - {response.text}")
```

#### GET /
Health check and API information.

**Response:**
```json
{
  "message": "Audio Transcription API is running",
  "supported_formats": [".mp3", ".wav", ".m4a", ".flac", ".ogg", ".wma"],
  "max_file_size_mb": 100
}
```

#### GET /health
Simple health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "model": "whisper-base"
}
```

## Configuration

Edit the `.env` file to customize the API behavior:

```env
# Server Configuration
PORT=8000
HOST=0.0.0.0

# Whisper Model Configuration
# Options: tiny, base, small, medium, large
# Note: Larger models are more accurate but slower
WHISPER_MODEL=base

# File Upload Configuration
MAX_FILE_SIZE_MB=100

# CORS Configuration
CORS_ORIGINS=*
```

### Whisper Model Options

| Model  | Size | Speed | Accuracy | Use Case |
|--------|------|-------|----------|----------|
| tiny   | 39 MB | Fastest | Basic | Quick testing |
| base   | 74 MB | Fast | Good | Recommended default |
| small  | 244 MB | Medium | Better | Higher accuracy needed |
| medium | 769 MB | Slow | Very Good | Professional use |
| large  | 1550 MB | Slowest | Best | Maximum accuracy |

## Error Handling

The API provides detailed error messages for common issues:

- **400 Bad Request**: Unsupported file format or missing filename
- **413 Payload Too Large**: File exceeds 100MB limit
- **500 Internal Server Error**: Transcription processing failed

## Example SRT Output

```srt
1
00:00:00,000 --> 00:00:03,000
Hello, welcome to our audio transcription service.

2
00:00:03,000 --> 00:00:07,500
This API converts your audio files into subtitle files automatically.

3
00:00:07,500 --> 00:00:12,000
The transcription includes proper timestamps for video synchronization.
```

## Performance Notes

- **First Run**: The first transcription may take longer as Whisper downloads the model
- **Model Loading**: The model is loaded once at startup and reused for all requests
- **Processing Time**: Varies based on audio length and selected model size
- **Memory Usage**: Larger models require more RAM (base model ~1GB, large model ~4GB)

## Troubleshooting

### Common Issues

1. **FFmpeg not found**
   ```
   Error: ffmpeg not found
   ```
   Solution: Install FFmpeg and ensure it's in your system PATH

2. **Out of memory**
   ```
   RuntimeError: CUDA out of memory
   ```
   Solution: Use a smaller Whisper model (tiny or base)

3. **File format not supported**
   ```
   400 Bad Request: Unsupported file format
   ```
   Solution: Convert your audio to MP3, WAV, or another supported format

4. **Slow transcription**
   Solution: Use a smaller model or ensure you have adequate CPU/GPU resources

### Development

To run in development mode with auto-reload:
```bash
python start.py
```

The server will automatically restart when you make changes to the code.

## License

This project uses OpenAI Whisper, which is released under the MIT License.