"""
Production configuration for Render deployment
Optimized for handling large audio files with limited memory
"""
import os

# Memory-optimized settings for Render
RENDER_CONFIG = {
    # File size limits based on instance type
    "FREE_TIER_MAX_MB": 10,      # 10MB for free tier
    "STARTER_MAX_MB": 25,        # 25MB for starter ($7/month)
    "STANDARD_MAX_MB": 50,       # 50MB for standard ($25/month)
    
    # Whisper model recommendations by instance type
    "FREE_TIER_MODEL": "tiny",    # Fastest, least memory
    "STARTER_MODEL": "base",      # Good balance
    "STANDARD_MODEL": "small",    # Better accuracy
    
    # Memory thresholds (MB)
    "MEMORY_WARNING_THRESHOLD": 400,  # Warn at 400MB
    "MEMORY_CRITICAL_THRESHOLD": 450, # Stop processing at 450MB
    
    # Timeout settings (seconds)
    "TRANSCRIPTION_TIMEOUT": 300,     # 5 minutes max
    "FILE_UPLOAD_TIMEOUT": 120,       # 2 minutes for upload
}

def get_instance_config():
    """
    Determine optimal configuration based on environment
    """
    # Try to detect instance type from memory or environment
    instance_type = os.getenv("RENDER_INSTANCE_TYPE", "starter").lower()
    
    if instance_type == "free":
        return {
            "max_file_size_mb": RENDER_CONFIG["FREE_TIER_MAX_MB"],
            "whisper_model": RENDER_CONFIG["FREE_TIER_MODEL"],
            "memory_limit_mb": 400,
        }
    elif instance_type == "standard":
        return {
            "max_file_size_mb": RENDER_CONFIG["STANDARD_MAX_MB"],
            "whisper_model": RENDER_CONFIG["STANDARD_MODEL"],
            "memory_limit_mb": 1800,
        }
    else:  # starter or default
        return {
            "max_file_size_mb": RENDER_CONFIG["STARTER_MAX_MB"],
            "whisper_model": "base",  # Force base model for reliability
            "memory_limit_mb": 450,
        }

def get_optimized_whisper_params():
    """
    Get Whisper parameters optimized for memory usage
    """
    return {
        "fp16": False,           # Use fp32 for stability
        "verbose": False,        # Reduce logging
        "word_timestamps": False, # Disable to save memory
        "condition_on_previous_text": False,  # Reduce memory usage
    }