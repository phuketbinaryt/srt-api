import os
import tempfile
import whisper
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import aiofiles
from typing import List
import re
from datetime import timedelta
import asyncio
import gc
import psutil
try:
    from render_config import get_instance_config, get_optimized_whisper_params
except ImportError:
    # Fallback configuration if render_config is not available
    def get_instance_config():
        return {
            "max_file_size_mb": int(os.getenv("MAX_FILE_SIZE_MB", "25")),
            "whisper_model": os.getenv("WHISPER_MODEL", "base"),
            "memory_limit_mb": 450,
        }
    
    def get_optimized_whisper_params():
        return {
            "fp16": False,
            "verbose": True,  # Enable verbose to see progress
            "word_timestamps": False,
            "condition_on_previous_text": False,
            "temperature": 0,  # Use deterministic decoding
            "compression_ratio_threshold": 2.4,  # Prevent infinite loops
            "logprob_threshold": -1.0,  # More conservative threshold
            "no_speech_threshold": 0.6,  # Higher threshold for silence
        }

app = FastAPI(
    title="Audio Transcription API",
    description="API for converting audio files to SRT subtitles using OpenAI Whisper",
    version="1.1.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global model variable - load lazily
model = None

# Get optimized configuration for current instance
instance_config = get_instance_config()

# Supported audio formats
SUPPORTED_FORMATS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".wma"}
# Use instance-specific file size limit
MAX_FILE_SIZE = instance_config["max_file_size_mb"] * 1024 * 1024

def get_model():
    """Lazy load the Whisper model to save memory"""
    global model
    if model is None:
        model_size = instance_config["whisper_model"]
        print(f"Loading Whisper model: {model_size} (optimized for current instance)")
        model = whisper.load_model(model_size)
        print("Model loaded successfully")
    return model

def cleanup_temp_files(*file_paths):
    """Clean up temporary files"""
    for file_path in file_paths:
        try:
            if file_path and os.path.exists(file_path):
                os.unlink(file_path)
        except Exception as e:
            print(f"Warning: Could not delete temp file {file_path}: {e}")

def get_memory_usage():
    """Get current memory usage"""
    try:
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024  # MB
    except:
        return 0

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
    memory_mb = get_memory_usage()
    return {
        "message": "Audio Transcription API is running",
        "supported_formats": list(SUPPORTED_FORMATS),
        "max_file_size_mb": MAX_FILE_SIZE // (1024 * 1024),
        "memory_usage_mb": round(memory_mb, 1),
        "model_loaded": model is not None
    }

@app.post("/upload")
async def transcribe_audio(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """
    Upload an audio file and get back an SRT subtitle file
    
    - **file**: Audio file in supported format (mp3, wav, m4a, flac, ogg, wma)
    - Returns: SRT file for download
    """
    temp_audio_path = None
    temp_srt_path = None
    
    try:
        # Check memory before processing
        initial_memory = get_memory_usage()
        print(f"Initial memory usage: {initial_memory:.1f}MB")
        
        # Validate file format
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        file_extension = os.path.splitext(file.filename)[1].lower()
        if file_extension not in SUPPORTED_FORMATS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format. Supported formats: {', '.join(SUPPORTED_FORMATS)}"
            )
        
        # Read file in chunks to avoid memory issues
        file_size = 0
        temp_audio_fd, temp_audio_path = tempfile.mkstemp(suffix=file_extension)
        
        try:
            with os.fdopen(temp_audio_fd, 'wb') as temp_file:
                while chunk := await file.read(8192):  # Read in 8KB chunks
                    file_size += len(chunk)
                    if file_size > MAX_FILE_SIZE:
                        raise HTTPException(
                            status_code=413,
                            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024 * 1024)}MB"
                        )
                    temp_file.write(chunk)
        except Exception as e:
            cleanup_temp_files(temp_audio_path)
            raise e
        
        print(f"File size: {file_size / (1024 * 1024):.1f}MB")
        
        # Load model if not already loaded
        whisper_model = get_model()
        
        # Check memory after model loading
        model_memory = get_memory_usage()
        print(f"Memory after model load: {model_memory:.1f}MB")
        
        # Transcribe audio using Whisper with optimized settings
        print("Starting transcription...")
        whisper_params = get_optimized_whisper_params()
        
        # Add timeout to prevent hanging
        try:
            result = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: whisper_model.transcribe(
                        temp_audio_path,
                        task="transcribe",
                        language=None,  # Auto-detect language
                        **whisper_params
                    )
                ),
                timeout=300  # 5 minutes timeout
            )
        except asyncio.TimeoutError:
            cleanup_temp_files(temp_audio_path)
            raise HTTPException(
                status_code=408,
                detail="Transcription timeout after 5 minutes. Try a shorter audio file or upgrade instance."
            )
        
        print("Transcription completed")
        
        # Clean up audio file immediately after transcription
        cleanup_temp_files(temp_audio_path)
        temp_audio_path = None
        
        # Force garbage collection to free memory
        gc.collect()
        
        # Convert to SRT format
        srt_content = create_srt_content(result['segments'])
        
        # Create temporary SRT file
        temp_srt_fd, temp_srt_path = tempfile.mkstemp(suffix='.srt')
        with os.fdopen(temp_srt_fd, 'w', encoding='utf-8') as temp_srt:
            temp_srt.write(srt_content)
        
        # Generate output filename
        base_filename = os.path.splitext(file.filename)[0]
        output_filename = f"{base_filename}_subtitles.srt"
        
        # Schedule cleanup of SRT file after response
        background_tasks.add_task(cleanup_temp_files, temp_srt_path)
        
        final_memory = get_memory_usage()
        print(f"Final memory usage: {final_memory:.1f}MB")
        
        # Return SRT file as download
        return FileResponse(
            path=temp_srt_path,
            filename=output_filename,
            media_type='application/x-subrip'
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        cleanup_temp_files(temp_audio_path, temp_srt_path)
        raise
    except Exception as e:
        # Clean up any temporary files in case of error
        cleanup_temp_files(temp_audio_path, temp_srt_path)
        
        # Force garbage collection on error
        gc.collect()
        
        error_msg = str(e)
        print(f"Transcription error: {error_msg}")
        
        # Provide more specific error messages
        if "out of memory" in error_msg.lower() or "memory" in error_msg.lower():
            raise HTTPException(
                status_code=507,
                detail="Server out of memory. Try a smaller file or upgrade server instance."
            )
        elif "timeout" in error_msg.lower():
            raise HTTPException(
                status_code=408,
                detail="Transcription timeout. File may be too large or complex."
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Transcription failed: {error_msg}"
            )

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {"status": "healthy", "model": "whisper-base"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)