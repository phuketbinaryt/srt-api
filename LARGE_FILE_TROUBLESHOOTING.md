# Large File Troubleshooting Guide

This guide addresses the issue where uploading large files (50MB+) causes the service to crash or become unresponsive.

## 🔧 Optimizations Applied

### 1. Memory Management
- **Lazy model loading**: Whisper model only loads when needed
- **Chunked file reading**: Files read in 8KB chunks to avoid memory spikes
- **Immediate cleanup**: Temporary files deleted as soon as possible
- **Garbage collection**: Force memory cleanup after processing
- **Memory monitoring**: Track memory usage throughout processing

### 2. File Size Limits by Instance Type
- **Free Tier**: 10MB max (uses "tiny" Whisper model)
- **Starter ($7/month)**: 25MB max (uses "base" Whisper model)
- **Standard ($25/month)**: 50MB max (uses "small" Whisper model)

### 3. Optimized Whisper Parameters
- `fp16=False`: Use 32-bit precision for stability
- `verbose=False`: Reduce logging overhead
- `word_timestamps=False`: Disable to save memory
- `condition_on_previous_text=False`: Reduce memory usage

### 4. Async Processing
- File transcription runs in background thread
- Non-blocking file operations
- Proper timeout handling

## 🚀 Deployment Configuration

### Environment Variables for Render

Add these to your Render service:

| Variable | Value | Description |
|----------|-------|-------------|
| `RENDER_INSTANCE_TYPE` | `starter` | Set to `free`, `starter`, or `standard` |
| `MAX_FILE_SIZE_MB` | `25` | Override default file size limit |
| `WHISPER_MODEL` | `base` | Override default model |

### Recommended Instance Types

**For 50MB files**: Use **Standard** instance ($25/month)
- 2GB RAM
- 50MB file limit
- "small" Whisper model
- Better performance

**For 25MB files**: Use **Starter** instance ($7/month)
- 512MB RAM
- 25MB file limit
- "base" Whisper model
- Good balance

**For testing**: Use **Free** tier
- 512MB RAM
- 10MB file limit
- "tiny" Whisper model
- Limited but functional

## 🔍 Troubleshooting Steps

### 1. Check Memory Usage
Visit your API's health endpoint: `https://your-app.onrender.com/`

Look for:
```json
{
  "memory_usage_mb": 245.3,
  "model_loaded": true,
  "max_file_size_mb": 25
}
```

### 2. Monitor Render Logs
In Render dashboard:
1. Go to your service
2. Click "Logs" tab
3. Look for these messages:

**Good signs:**
```
Loading Whisper model: base (optimized for current instance)
Model loaded successfully
Initial memory usage: 245.3MB
Starting transcription...
Transcription completed
```

**Warning signs:**
```
Memory after model load: 450.0MB
Server out of memory
Process killed (OOM)
```

### 3. Common Error Messages

**"Server out of memory"**
- **Solution**: Upgrade to larger instance or reduce file size
- **Cause**: File too large for current instance

**"Transcription timeout"**
- **Solution**: Upgrade instance or use smaller Whisper model
- **Cause**: Processing taking too long

**"File too large"**
- **Solution**: Reduce file size or upgrade instance
- **Cause**: File exceeds configured limit

## 🛠️ Quick Fixes

### For Immediate Relief
1. **Reduce file size limit**:
   - Set `MAX_FILE_SIZE_MB=10` for free tier
   - Set `MAX_FILE_SIZE_MB=15` for starter tier

2. **Use smaller model**:
   - Set `WHISPER_MODEL=tiny` for fastest processing
   - Set `WHISPER_MODEL=base` for balanced performance

3. **Upgrade instance**:
   - Free → Starter: $7/month, 25MB files
   - Starter → Standard: $25/month, 50MB files

### For Long-term Stability
1. **Monitor memory usage** regularly
2. **Set appropriate file limits** for your instance
3. **Use compression** on audio files before upload
4. **Consider audio preprocessing** (lower bitrate, mono channel)

## 📊 Performance Expectations

### Processing Times (approximate)
- **10MB file**: 30-60 seconds
- **25MB file**: 1-3 minutes
- **50MB file**: 3-8 minutes

### Memory Usage
- **Tiny model**: ~200MB
- **Base model**: ~400MB
- **Small model**: ~800MB

## 🔄 Testing Your Fixes

1. **Deploy updated code** to Render
2. **Test with small file** (5MB) first
3. **Gradually increase** file size
4. **Monitor memory** in health endpoint
5. **Check logs** for any warnings

## 📞 Still Having Issues?

If problems persist:

1. **Check Render status**: https://status.render.com
2. **Review instance metrics** in Render dashboard
3. **Try different audio formats** (MP3 vs WAV)
4. **Consider audio preprocessing** to reduce file size
5. **Contact Render support** if instance issues

## 🎯 Success Indicators

Your service is working properly when:
- ✅ Health endpoint shows reasonable memory usage
- ✅ Files process without timeout errors
- ✅ No "out of memory" errors in logs
- ✅ Service remains responsive after processing
- ✅ Memory usage returns to baseline after processing

The optimizations in this version should handle files up to your instance's limit without crashing!