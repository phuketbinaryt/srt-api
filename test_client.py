#!/usr/bin/env python3
"""
Test client for the Audio Transcription API
"""
import requests
import sys
import os

def test_api(audio_file_path: str, api_url: str = "http://localhost:8000"):
    """
    Test the audio transcription API with a given audio file
    
    Args:
        audio_file_path: Path to the audio file to transcribe
        api_url: Base URL of the API (default: http://localhost:8000)
    """
    
    if not os.path.exists(audio_file_path):
        print(f"Error: Audio file '{audio_file_path}' not found")
        return False
    
    # Check if file is supported format
    supported_formats = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".wma"}
    file_extension = os.path.splitext(audio_file_path)[1].lower()
    
    if file_extension not in supported_formats:
        print(f"Error: Unsupported file format '{file_extension}'")
        print(f"Supported formats: {', '.join(supported_formats)}")
        return False
    
    # Check file size
    file_size = os.path.getsize(audio_file_path)
    max_size = 100 * 1024 * 1024  # 100MB
    
    if file_size > max_size:
        print(f"Error: File too large ({file_size / (1024*1024):.1f}MB). Maximum size: 100MB")
        return False
    
    print(f"Testing API with file: {audio_file_path}")
    print(f"File size: {file_size / (1024*1024):.1f}MB")
    print(f"API URL: {api_url}")
    print("-" * 50)
    
    try:
        # Test health endpoint first
        print("1. Testing health endpoint...")
        health_response = requests.get(f"{api_url}/health")
        
        if health_response.status_code == 200:
            print("✓ API is healthy")
        else:
            print(f"✗ Health check failed: {health_response.status_code}")
            return False
        
        # Test transcription endpoint
        print("2. Uploading audio file for transcription...")
        
        with open(audio_file_path, 'rb') as audio_file:
            files = {"file": audio_file}
            response = requests.post(f"{api_url}/upload", files=files)
        
        if response.status_code == 200:
            # Save the SRT file
            base_filename = os.path.splitext(os.path.basename(audio_file_path))[0]
            output_filename = f"{base_filename}_subtitles.srt"
            
            with open(output_filename, 'wb') as srt_file:
                srt_file.write(response.content)
            
            print(f"✓ Transcription successful!")
            print(f"✓ SRT file saved as: {output_filename}")
            
            # Show first few lines of the SRT file
            print("\nFirst few lines of the SRT file:")
            print("-" * 30)
            with open(output_filename, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                for i, line in enumerate(lines[:10]):  # Show first 10 lines
                    print(line.rstrip())
                if len(lines) > 10:
                    print("...")
            
            return True
            
        else:
            print(f"✗ Transcription failed: {response.status_code}")
            print(f"Error: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("✗ Connection failed. Make sure the API server is running.")
        print("Start the server with: python start.py")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {str(e)}")
        return False

def main():
    """Main function to run the test client"""
    if len(sys.argv) < 2:
        print("Usage: python test_client.py <audio_file_path> [api_url]")
        print("\nExample:")
        print("  python test_client.py sample_audio.mp3")
        print("  python test_client.py sample_audio.wav http://localhost:8000")
        print("\nSupported formats: mp3, wav, m4a, flac, ogg, wma")
        sys.exit(1)
    
    audio_file_path = sys.argv[1]
    api_url = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8000"
    
    success = test_api(audio_file_path, api_url)
    
    if success:
        print("\n🎉 Test completed successfully!")
    else:
        print("\n❌ Test failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()