# Async Audio Transcription API Guide

## 🚀 Overview

The Audio Transcription API now supports **asynchronous processing** with job polling to prevent timeouts in automation tools like n8n. Instead of waiting for the entire transcription to complete, you can:

1. **Submit a job** and get a job ID immediately
2. **Poll the job status** until completion
3. **Download the SRT file** when ready

This prevents timeout issues and allows for better integration with workflow automation tools.

## 📡 API Endpoints

### 1. Submit Transcription Job

**Endpoint**: `POST /jobs`

Submit an audio file for transcription and receive a job ID for polling.

**Request**:
```bash
curl -X POST "https://your-api-url.com/jobs" \
     -F "file=@audio.mp3"
```

**Response**:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Transcription job submitted successfully",
  "filename": "audio.mp3",
  "file_size_mb": 15.2,
  "estimated_time_minutes": 7.6
}
```

### 2. Check Job Status

**Endpoint**: `GET /jobs/{job_id}`

Check the current status of a transcription job.

**Request**:
```bash
curl "https://your-api-url.com/jobs/550e8400-e29b-41d4-a716-446655440000"
```

**Response (Processing)**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "audio.mp3",
  "file_size": 15925248,
  "status": "processing",
  "created_at": "2025-01-15T10:30:00.000Z",
  "started_at": "2025-01-15T10:30:05.000Z",
  "processing_time_seconds": 45.2,
  "completed_at": null,
  "segments_count": null,
  "detected_language": null,
  "error": null
}
```

**Response (Completed)**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "audio.mp3",
  "file_size": 15925248,
  "status": "completed",
  "created_at": "2025-01-15T10:30:00.000Z",
  "started_at": "2025-01-15T10:30:05.000Z",
  "completed_at": "2025-01-15T10:32:30.000Z",
  "processing_time_seconds": 145.0,
  "srt_filename": "audio_subtitles.srt",
  "segments_count": 42,
  "detected_language": "en",
  "error": null
}
```

### 3. Download SRT File

**Endpoint**: `GET /jobs/{job_id}/download`

Download the completed SRT file.

**Request**:
```bash
curl "https://your-api-url.com/jobs/550e8400-e29b-41d4-a716-446655440000/download" \
     --output subtitles.srt
```

**Response**: SRT file download

### 4. List Jobs

**Endpoint**: `GET /jobs`

List recent transcription jobs with optional filtering.

**Parameters**:
- `limit`: Maximum number of jobs (default: 10)
- `status`: Filter by status (`pending`, `processing`, `completed`, `failed`)

**Request**:
```bash
curl "https://your-api-url.com/jobs?limit=5&status=completed"
```

**Response**:
```json
{
  "jobs": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "filename": "audio.mp3",
      "status": "completed",
      "created_at": "2025-01-15T10:30:00.000Z",
      "completed_at": "2025-01-15T10:32:30.000Z",
      "segments_count": 42,
      "detected_language": "en"
    }
  ],
  "total": 1,
  "active_jobs": 0
}
```

## 🔄 Job Status Flow

```
pending → processing → completed
                    ↘ failed
```

- **`pending`**: Job submitted, waiting to start
- **`processing`**: Transcription in progress
- **`completed`**: Transcription finished, SRT file ready
- **`failed`**: Error occurred during processing

## 🤖 n8n Integration Example

### Method 1: Using HTTP Request Nodes

**Step 1: Submit Job**
```json
{
  "method": "POST",
  "url": "https://your-api-url.com/jobs",
  "sendBinaryData": true,
  "binaryPropertyName": "audio_file",
  "options": {
    "timeout": 30000
  }
}
```

**Step 2: Wait and Poll (Loop)**
```json
{
  "method": "GET",
  "url": "https://your-api-url.com/jobs/{{$json.job_id}}",
  "options": {
    "timeout": 10000
  }
}
```

**Step 3: Download SRT (When Complete)**
```json
{
  "method": "GET",
  "url": "https://your-api-url.com/jobs/{{$json.id}}/download",
  "options": {
    "timeout": 30000,
    "response": {
      "responseFormat": "file"
    }
  }
}
```

### Method 2: Complete n8n Workflow

```json
{
  "name": "Audio Transcription Workflow",
  "nodes": [
    {
      "name": "Submit Job",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "method": "POST",
        "url": "https://your-api-url.com/jobs",
        "sendBinaryData": true,
        "binaryPropertyName": "audio_file"
      }
    },
    {
      "name": "Wait 30 seconds",
      "type": "n8n-nodes-base.wait",
      "parameters": {
        "amount": 30,
        "unit": "seconds"
      }
    },
    {
      "name": "Check Status",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "method": "GET",
        "url": "https://your-api-url.com/jobs/{{$node['Submit Job'].json.job_id}}"
      }
    },
    {
      "name": "Status Check",
      "type": "n8n-nodes-base.if",
      "parameters": {
        "conditions": {
          "string": [
            {
              "value1": "{{$json.status}}",
              "operation": "equal",
              "value2": "completed"
            }
          ]
        }
      }
    },
    {
      "name": "Download SRT",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "method": "GET",
        "url": "https://your-api-url.com/jobs/{{$node['Check Status'].json.id}}/download",
        "options": {
          "response": {
            "responseFormat": "file"
          }
        }
      }
    },
    {
      "name": "Wait More",
      "type": "n8n-nodes-base.wait",
      "parameters": {
        "amount": 30,
        "unit": "seconds"
      }
    }
  ],
  "connections": {
    "Submit Job": {
      "main": [["Wait 30 seconds"]]
    },
    "Wait 30 seconds": {
      "main": [["Check Status"]]
    },
    "Check Status": {
      "main": [["Status Check"]]
    },
    "Status Check": {
      "main": [
        ["Download SRT"],
        ["Wait More"]
      ]
    },
    "Wait More": {
      "main": [["Check Status"]]
    }
  }
}
```

## 🐍 Python Example

```python
import requests
import time

def transcribe_audio_async(api_url, audio_file_path):
    # Submit job
    with open(audio_file_path, 'rb') as f:
        response = requests.post(f"{api_url}/jobs", files={"file": f})
    
    if response.status_code != 200:
        raise Exception(f"Failed to submit job: {response.text}")
    
    job_data = response.json()
    job_id = job_data["job_id"]
    print(f"Job submitted: {job_id}")
    print(f"Estimated time: {job_data['estimated_time_minutes']} minutes")
    
    # Poll for completion
    while True:
        response = requests.get(f"{api_url}/jobs/{job_id}")
        job_status = response.json()
        
        print(f"Status: {job_status['status']}")
        
        if job_status["status"] == "completed":
            print(f"Transcription completed in {job_status['processing_time_seconds']:.1f} seconds")
            print(f"Detected language: {job_status['detected_language']}")
            print(f"Segments: {job_status['segments_count']}")
            break
        elif job_status["status"] == "failed":
            raise Exception(f"Transcription failed: {job_status['error']}")
        
        time.sleep(10)  # Wait 10 seconds before checking again
    
    # Download SRT file
    response = requests.get(f"{api_url}/jobs/{job_id}/download")
    srt_filename = job_status["srt_filename"]
    
    with open(srt_filename, 'wb') as f:
        f.write(response.content)
    
    print(f"SRT file saved: {srt_filename}")
    return srt_filename

# Usage
api_url = "https://your-api-url.com"
srt_file = transcribe_audio_async(api_url, "audio.mp3")
```

## 🔧 JavaScript/Node.js Example

```javascript
const axios = require('axios');
const fs = require('fs');
const FormData = require('form-data');

async function transcribeAudioAsync(apiUrl, audioFilePath) {
    // Submit job
    const formData = new FormData();
    formData.append('file', fs.createReadStream(audioFilePath));
    
    const submitResponse = await axios.post(`${apiUrl}/jobs`, formData, {
        headers: formData.getHeaders()
    });
    
    const { job_id, estimated_time_minutes } = submitResponse.data;
    console.log(`Job submitted: ${job_id}`);
    console.log(`Estimated time: ${estimated_time_minutes} minutes`);
    
    // Poll for completion
    while (true) {
        const statusResponse = await axios.get(`${apiUrl}/jobs/${job_id}`);
        const jobStatus = statusResponse.data;
        
        console.log(`Status: ${jobStatus.status}`);
        
        if (jobStatus.status === 'completed') {
            console.log(`Transcription completed in ${jobStatus.processing_time_seconds} seconds`);
            console.log(`Detected language: ${jobStatus.detected_language}`);
            console.log(`Segments: ${jobStatus.segments_count}`);
            break;
        } else if (jobStatus.status === 'failed') {
            throw new Error(`Transcription failed: ${jobStatus.error}`);
        }
        
        await new Promise(resolve => setTimeout(resolve, 10000)); // Wait 10 seconds
    }
    
    // Download SRT file
    const downloadResponse = await axios.get(`${apiUrl}/jobs/${job_id}/download`, {
        responseType: 'stream'
    });
    
    const srtFilename = `${job_id}_subtitles.srt`;
    const writer = fs.createWriteStream(srtFilename);
    downloadResponse.data.pipe(writer);
    
    return new Promise((resolve, reject) => {
        writer.on('finish', () => {
            console.log(`SRT file saved: ${srtFilename}`);
            resolve(srtFilename);
        });
        writer.on('error', reject);
    });
}

// Usage
transcribeAudioAsync('https://your-api-url.com', 'audio.mp3')
    .then(srtFile => console.log('Done:', srtFile))
    .catch(console.error);
```

## ⚡ Performance Tips

### Polling Frequency
- **Small files (<5MB)**: Poll every 10-15 seconds
- **Medium files (5-25MB)**: Poll every 20-30 seconds  
- **Large files (25-100MB)**: Poll every 45-60 seconds

### Timeout Settings
- **Job submission**: 30 seconds timeout
- **Status polling**: 10 seconds timeout
- **File download**: 60 seconds timeout

### Error Handling
Always check for these conditions:
- Job not found (404)
- Job failed status
- Network timeouts
- File download errors

## 🔒 Security Notes

- Job IDs are UUIDs and not easily guessable
- Jobs are automatically cleaned up after 24 hours
- SRT files are temporarily stored and cleaned up
- No authentication required (add if needed for production)

## 🆚 Sync vs Async Comparison

| Feature | Sync API (`/upload`) | Async API (`/jobs`) |
|---------|---------------------|-------------------|
| **Timeout Risk** | High (long files) | None |
| **n8n Compatible** | Limited | Full |
| **Progress Tracking** | No | Yes |
| **Scalability** | Limited | High |
| **Use Case** | Small files, testing | Production, automation |

## 🎯 Best Practices for n8n

1. **Always use async endpoints** for files >5MB
2. **Implement proper polling loops** with reasonable delays
3. **Handle all job statuses** (pending, processing, completed, failed)
4. **Set appropriate timeouts** for each request type
5. **Store job IDs** for later reference if needed
6. **Clean up downloaded files** after processing

The async API ensures your n8n workflows never timeout, regardless of audio file size! 🚀