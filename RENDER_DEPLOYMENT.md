# Render Deployment Guide for SRT API

This guide explains how to deploy the Audio Transcription API to Render.com.

## Prerequisites

1. GitHub account with the srt-api repository
2. Render.com account (free tier available)

## Deployment Steps

### 1. Push to GitHub

Make sure your code is pushed to GitHub as the `srt-api` repository.

### 2. Connect to Render

1. Go to [Render.com](https://render.com) and sign in
2. Click "New +" and select "Web Service"
3. Connect your GitHub account if not already connected
4. Select the `srt-api` repository

### 3. Configure the Service

**Basic Settings:**
- **Name**: `srt-api` (or your preferred name)
- **Environment**: `Python 3`
- **Region**: Choose closest to your users
- **Branch**: `main` (or your default branch)

**Build & Deploy Settings:**
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python start.py`

**Environment Variables:**
Add these environment variables in Render dashboard:

| Key | Value | Description |
|-----|-------|-------------|
| `PORT` | `10000` | Render's default port |
| `HOST` | `0.0.0.0` | Listen on all interfaces |
| `WHISPER_MODEL` | `base` | Whisper model size |
| `MAX_FILE_SIZE_MB` | `100` | Max upload size |
| `CORS_ORIGINS` | `*` | CORS settings |
| `ENVIRONMENT` | `production` | Disable reload |

### 4. Advanced Settings

**Instance Type:**
- **Free Tier**: Limited to 512MB RAM (may struggle with larger audio files)
- **Starter ($7/month)**: 512MB RAM, better for production
- **Standard ($25/month)**: 2GB RAM, recommended for heavy usage

**Disk Storage:**
- Enable persistent disk if you need temporary file storage
- Size: 1GB should be sufficient for most use cases

### 5. Deploy

1. Click "Create Web Service"
2. Render will automatically build and deploy your application
3. The build process takes 5-10 minutes (downloading PyTorch and Whisper models)
4. Once deployed, you'll get a URL like: `https://srt-api-xxxx.onrender.com`

## Post-Deployment

### Testing Your Deployment

1. **Health Check**: Visit `https://your-app.onrender.com/health`
2. **API Docs**: Visit `https://your-app.onrender.com/docs`
3. **Upload Test**: Use the frontend or curl to test file uploads

### Performance Considerations

**Model Loading:**
- First request may be slow (30-60 seconds) as Whisper downloads the model
- Subsequent requests will be faster as the model stays in memory
- Consider using a larger instance type for better performance

**File Size Limits:**
- Render has request timeout limits (30 seconds for free tier)
- Large files may timeout during transcription
- Consider reducing `MAX_FILE_SIZE_MB` for free tier

**Memory Usage:**
- Base Whisper model: ~1GB RAM
- Small model: ~2GB RAM
- Free tier (512MB) may experience memory issues with longer audio files

### Monitoring

**Logs:**
- View logs in Render dashboard under "Logs" tab
- Monitor for memory issues or timeout errors

**Metrics:**
- Check CPU and memory usage in Render dashboard
- Monitor response times and error rates

### Troubleshooting

**Common Issues:**

1. **Build Fails:**
   ```
   Error: Could not find a version that satisfies the requirement torch
   ```
   - Solution: Ensure requirements.txt uses `>=` version specifiers

2. **Memory Issues:**
   ```
   Process killed (OOM)
   ```
   - Solution: Upgrade to a larger instance type or use smaller Whisper model

3. **Timeout Errors:**
   ```
   Request timeout
   ```
   - Solution: Reduce file size limits or upgrade instance type

4. **Model Download Fails:**
   ```
   Connection error downloading model
   ```
   - Solution: Restart the service, check internet connectivity

### Scaling

**Horizontal Scaling:**
- Render supports auto-scaling based on CPU usage
- Configure in "Settings" > "Scaling"

**Vertical Scaling:**
- Upgrade instance type for more RAM/CPU
- Recommended for processing larger files

### Security

**Environment Variables:**
- Never commit `.env` file to Git
- Use Render's environment variable settings
- Consider using Render's secret management for sensitive data

**CORS:**
- Update `CORS_ORIGINS` to specific domains in production
- Avoid using `*` for production deployments

### Cost Optimization

**Free Tier Limitations:**
- 750 hours/month free compute time
- Service sleeps after 15 minutes of inactivity
- Cold start time: 30-60 seconds

**Paid Tier Benefits:**
- No sleep mode
- Better performance
- More memory and CPU
- Priority support

## Alternative Deployment: Docker

If you prefer Docker deployment on Render:

1. Use the included `Dockerfile`
2. Set build command to: `docker build -t srt-api .`
3. Set start command to: `docker run -p 10000:8000 srt-api`

## Support

For issues with this deployment:
1. Check Render logs first
2. Review this troubleshooting guide
3. Check Render's documentation
4. Contact support if needed

## Production Checklist

- [ ] Environment variables configured
- [ ] Instance type appropriate for expected load
- [ ] CORS settings configured for your domain
- [ ] Health checks working
- [ ] API documentation accessible
- [ ] File upload limits tested
- [ ] Performance benchmarked
- [ ] Monitoring set up
- [ ] Backup strategy in place (if needed)