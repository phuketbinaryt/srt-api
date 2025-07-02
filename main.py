import os
import tempfile
import whisper
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import aiofiles
from typing import List
import re
from datetime import timedelta

app = FastAPI(
    title="Audio Transcription API",
    description="API for converting audio files to SRT subtitles using OpenAI Whisper",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load Whisper model (using base model for balance of speed and accuracy)
model = whisper.load_model("base")

# Supported audio formats
SUPPORTED_FORMATS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".wma"}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB in bytes

def format_timestamp(seconds: float) -> str:
    """Convert seconds to SRT timestamp format (HH:MM:SS,mmm)"""
    td = timedelta(seconds=seconds)
    hours, remainder = divmod(td.total_seconds(), 3600)
    minutes, seconds = divmod(remainder, 60)
    milliseconds = int((seconds % 1) * 1000)
    return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d},{milliseconds:03d}"

def create_srt_content(segments: List[dict]) -> str:
    """Convert Whisper segments to SRT format"""
    srt_content = ""
    
    for i, segment in enumerate(segments, 1):
        start_time = format_timestamp(segment['start'])
        end_time = format_timestamp(segment['end'])
        text = segment['text'].strip()
        
        srt_content += f"{i}\n"
        srt_content += f"{start_time} --> {end_time}\n"
        srt_content += f"{text}\n\n"
    
    return srt_content

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "Audio Transcription API is running",
        "supported_formats": list(SUPPORTED_FORMATS),
        "max_file_size_mb": MAX_FILE_SIZE // (1024 * 1024)
    }

@app.post("/upload")
async def transcribe_audio(file: UploadFile = File(...)):
    """
    Upload an audio file and get back an SRT subtitle file
    
    - **file**: Audio file in supported format (mp3, wav, m4a, flac, ogg, wma)
    - Returns: SRT file for download
    """
    
    # Validate file format
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    file_extension = os.path.splitext(file.filename)[1].lower()
    if file_extension not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported file format. Supported formats: {', '.join(SUPPORTED_FORMATS)}"
        )
    
    # Check file size
    file_content = await file.read()
    if len(file_content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413, 
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024 * 1024)}MB"
        )
    
    # Reset file pointer
    await file.seek(0)
    
    try:
        # Create temporary file for audio processing
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_audio:
            # Write uploaded file to temporary file
            async with aiofiles.open(temp_audio.name, 'wb') as f:
                await f.write(file_content)
            
            # Transcribe audio using Whisper
            result = model.transcribe(
                temp_audio.name,
                task="transcribe",
                language=None,  # Auto-detect language
                word_timestamps=False
            )
            
            # Clean up temporary audio file
            os.unlink(temp_audio.name)
        
        # Convert to SRT format
        srt_content = create_srt_content(result['segments'])
        
        # Create temporary SRT file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.srt', encoding='utf-8') as temp_srt:
            temp_srt.write(srt_content)
            temp_srt_path = temp_srt.name
        
        # Generate output filename
        base_filename = os.path.splitext(file.filename)[0]
        output_filename = f"{base_filename}_subtitles.srt"
        
        # Return SRT file as download
        return FileResponse(
            path=temp_srt_path,
            filename=output_filename,
            media_type='application/x-subrip',
            background=lambda: os.unlink(temp_srt_path)  # Clean up after sending
        )
        
    except Exception as e:
        # Clean up any temporary files in case of error
        try:
            if 'temp_audio' in locals():
                os.unlink(temp_audio.name)
        except:
            pass
        try:
            if 'temp_srt_path' in locals():
                os.unlink(temp_srt_path)
        except:
            pass
        
        raise HTTPException(
            status_code=500, 
            detail=f"Transcription failed: {str(e)}"
        )

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {"status": "healthy", "model": "whisper-base"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)