import os
import tempfile
import whisper
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import aiofiles
from typing import List, Dict, Optional
import re
from datetime import timedelta, datetime
import asyncio
import gc
import psutil
import uuid
import json
from enum import Enum
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

# Job status enumeration
class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

# In-memory job storage (in production, use Redis or database)
jobs: Dict[str, Dict] = {}

app = FastAPI(
    title="Audio Transcription API",
    description="API for converting audio files to SRT subtitles using OpenAI Whisper",
    version="1.1.0"
)

# Add URL normalization middleware to handle double slashes
from fastapi import Request
from fastapi.responses import RedirectResponse

@app.middleware("http")
async def normalize_url_middleware(request: Request, call_next):
    """Normalize URLs by removing double slashes and handling common URL issues"""
    url_path = str(request.url.path)
    
    # Fix double slashes (//upload -> /upload)
    if "//" in url_path and url_path != "/":
        normalized_path = url_path.replace("//", "/")
        # Redirect to normalized URL
        query_string = str(request.url.query)
        new_url = f"{normalized_path}{'?' + query_string if query_string else ''}"
        return RedirectResponse(url=new_url, status_code=307)  # 307 preserves POST method
    
    response = await call_next(request)
    return response

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

async def get_model_async():
    """Async wrapper for model loading with timeout"""
    global model
    if model is None:
        model_size = instance_config["whisper_model"]
        print(f"Loading Whisper model: {model_size} (optimized for current instance)")
        
        try:
            # Try loading with timeout
            model = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: whisper.load_model(model_size)
                ),
                timeout=120  # 2 minutes timeout for model loading
            )
            print("Model loaded successfully")
        except asyncio.TimeoutError:
            print(f"Timeout loading {model_size} model, falling back to 'base'...")
            try:
                model = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: whisper.load_model("base")
                    ),
                    timeout=120
                )
                print("Base model loaded successfully")
            except asyncio.TimeoutError:
                print("Timeout loading base model, falling back to 'tiny'...")
                model = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: whisper.load_model("tiny")
                    ),
                    timeout=60
                )
                print("Tiny model loaded successfully")
        except Exception as e:
            print(f"Failed to load {model_size} model: {e}")
            print("Falling back to 'base' model...")
            try:
                model = whisper.load_model("base")
                print("Base model loaded successfully")
            except Exception as e2:
                print(f"Failed to load base model: {e2}")
                print("Falling back to 'tiny' model...")
                model = whisper.load_model("tiny")
                print("Tiny model loaded successfully")
    return model

def get_model():
    """Lazy load the Whisper model to save memory"""
    global model
    if model is None:
        # Force use of base model for reliability
        model_size = "base"
        print(f"Loading Whisper model: {model_size} (forced for reliability)")
        
        try:
            model = whisper.load_model(model_size)
            print("Model loaded successfully")
        except Exception as e:
            print(f"Failed to load {model_size} model: {e}")
            print("Falling back to 'tiny' model...")
            model = whisper.load_model("tiny")
            print("Tiny model loaded successfully")
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

async def process_transcription_job(job_id: str, temp_audio_path: str, filename: str):
    """Background task to process transcription"""
    try:
        # Update job status to processing
        jobs[job_id]["status"] = JobStatus.PROCESSING
        jobs[job_id]["started_at"] = datetime.utcnow().isoformat()
        
        print(f"Starting transcription job {job_id}")
        
        # Load model
        whisper_model = get_model()
        
        # Transcribe audio
        whisper_params = get_optimized_whisper_params()
        result = whisper_model.transcribe(
            temp_audio_path,
            task="transcribe",
            language=None,
            **whisper_params
        )
        
        # Convert to SRT
        srt_content = create_srt_content(result['segments'])
        
        # Save SRT file
        srt_filename = f"{os.path.splitext(filename)[0]}_subtitles.srt"
        srt_path = f"/tmp/{job_id}_{srt_filename}"
        
        with open(srt_path, 'w', encoding='utf-8') as f:
            f.write(srt_content)
        
        # Update job with results
        jobs[job_id].update({
            "status": JobStatus.COMPLETED,
            "completed_at": datetime.utcnow().isoformat(),
            "srt_path": srt_path,
            "srt_filename": srt_filename,
            "segments_count": len(result['segments']),
            "detected_language": result.get('language', 'unknown')
        })
        
        print(f"Transcription job {job_id} completed successfully")
        
    except Exception as e:
        # Update job with error
        jobs[job_id].update({
            "status": JobStatus.FAILED,
            "completed_at": datetime.utcnow().isoformat(),
            "error": str(e)
        })
        print(f"Transcription job {job_id} failed: {e}")
    
    finally:
        # Clean up temp audio file
        cleanup_temp_files(temp_audio_path)
        gc.collect()

def create_job(filename: str, file_size: int) -> str:
    """Create a new transcription job"""
    job_id = str(uuid.uuid4())
    
    jobs[job_id] = {
        "id": job_id,
        "filename": filename,
        "file_size": file_size,
        "status": JobStatus.PENDING,
        "created_at": datetime.utcnow().isoformat(),
        "started_at": None,
        "completed_at": None,
        "srt_path": None,
        "srt_filename": None,
        "segments_count": None,
        "detected_language": None,
        "error": None
    }
    
    return job_id

def cleanup_old_jobs():
    """Clean up jobs older than 24 hours"""
    cutoff_time = datetime.utcnow() - timedelta(hours=24)
    
    jobs_to_remove = []
    for job_id, job in jobs.items():
        created_at = datetime.fromisoformat(job["created_at"])
        if created_at < cutoff_time:
            # Clean up SRT file if it exists
            if job.get("srt_path") and os.path.exists(job["srt_path"]):
                cleanup_temp_files(job["srt_path"])
            jobs_to_remove.append(job_id)
    
    for job_id in jobs_to_remove:
        del jobs[job_id]
    
    if jobs_to_remove:
        print(f"Cleaned up {len(jobs_to_remove)} old jobs")

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

@app.get("/frontend.html")
async def frontend():
    """Serve the frontend HTML file"""
    from fastapi.responses import HTMLResponse
    try:
        with open("frontend.html", "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content=content)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Frontend file not found")

@app.post("/jobs")
@app.post("/jobs/")
async def submit_transcription_job(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """
    Submit an audio file for transcription and get a job ID for polling
    
    - **file**: Audio file in supported format (mp3, wav, m4a, flac, ogg, wma)
    - Returns: Job ID and status for polling
    """
    try:
        # Clean up old jobs periodically
        cleanup_old_jobs()
        
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
        
        # Create job
        job_id = create_job(file.filename, file_size)
        
        # Start background processing
        background_tasks.add_task(process_transcription_job, job_id, temp_audio_path, file.filename)
        
        return {
            "job_id": job_id,
            "status": JobStatus.PENDING,
            "message": "Transcription job submitted successfully",
            "filename": file.filename,
            "file_size_mb": round(file_size / (1024 * 1024), 2),
            "estimated_time_minutes": round(file_size / (1024 * 1024) * 0.5, 1)  # Rough estimate
        }
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        print(f"Job submission error: {error_msg}")
        raise HTTPException(status_code=500, detail=f"Failed to submit job: {error_msg}")

@app.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """
    Get the status of a transcription job
    
    - **job_id**: The job ID returned from job submission
    - Returns: Job status and details
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id].copy()
    
    # Calculate processing time if applicable
    if job["started_at"]:
        started_at = datetime.fromisoformat(job["started_at"])
        if job["completed_at"]:
            completed_at = datetime.fromisoformat(job["completed_at"])
            job["processing_time_seconds"] = (completed_at - started_at).total_seconds()
        else:
            job["processing_time_seconds"] = (datetime.utcnow() - started_at).total_seconds()
    
    # Remove internal paths from response
    job.pop("srt_path", None)
    
    return job

@app.get("/jobs/{job_id}/download")
async def download_srt_file(job_id: str):
    """
    Download the SRT file for a completed transcription job
    
    - **job_id**: The job ID returned from job submission
    - Returns: SRT file download
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    
    if job["status"] != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Job is not completed. Current status: {job['status']}"
        )
    
    srt_path = job.get("srt_path")
    if not srt_path or not os.path.exists(srt_path):
        raise HTTPException(status_code=404, detail="SRT file not found")
    
    return FileResponse(
        path=srt_path,
        filename=job["srt_filename"],
        media_type='application/x-subrip'
    )

@app.get("/jobs")
async def list_jobs(limit: int = 10, status: Optional[JobStatus] = None):
    """
    List recent transcription jobs
    
    - **limit**: Maximum number of jobs to return (default: 10)
    - **status**: Filter by job status (optional)
    - Returns: List of jobs
    """
    # Clean up old jobs
    cleanup_old_jobs()
    
    # Filter and sort jobs
    filtered_jobs = []
    for job in jobs.values():
        if status is None or job["status"] == status:
            job_copy = job.copy()
            job_copy.pop("srt_path", None)  # Remove internal paths
            filtered_jobs.append(job_copy)
    
    # Sort by creation time (newest first)
    filtered_jobs.sort(key=lambda x: x["created_at"], reverse=True)
    
    return {
        "jobs": filtered_jobs[:limit],
        "total": len(filtered_jobs),
        "active_jobs": len([j for j in jobs.values() if j["status"] in [JobStatus.PENDING, JobStatus.PROCESSING]])
    }

@app.post("/upload")
@app.post("/upload/")  # Handle trailing slash
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