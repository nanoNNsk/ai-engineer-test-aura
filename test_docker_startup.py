#!/usr/bin/env python3
"""
Docker Startup Test Script
Tests the "One-Command Startup" requirement for the RAG system.
"""

import subprocess
import time
import sys
import socket
import requests
from pathlib import Path


def print_header(message):
    """Print formatted header"""
    print(f"\n{'='*60}")
    print(f"  {message}")
    print(f"{'='*60}\n")


def check_port_available(port):
    """Check if a port is available"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(('localhost', port))
        sock.close()
        return True
    except OSError:
        return False


def run_command(cmd, cwd=None, capture_output=False):
    """Run a shell command"""
    try:
        if capture_output:
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=120
            )
            return result.returncode, result.stdout, result.stderr
        else:
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=cwd,
                timeout=120
            )
            return result.returncode, None, None
    except subprocess.TimeoutExpired:
        print(f"❌ Command timed out: {cmd}")
        return -1, None, None
    except Exception as e:
        print(f"❌ Error running command: {e}")
        return -1, None, None


def clean_slate():
    """Remove all containers and volumes"""
    print_header("Step 1: Clean Slate")
    
    print("🧹 Removing all containers and volumes...")
    returncode, stdout, stderr = run_command(
        "docker compose down -v",
        cwd=None,  # Run from root
        capture_output=True
    )
    
    if returncode != 0:
        print(f"⚠️  Warning: docker compose down returned {returncode}")
        if stderr:
            print(f"   {stderr}")
    else:
        print("✅ Cleaned up successfully")
    
    return True


def check_ports():
    """Check if required ports are available"""
    print_header("Step 2: Port Availability Check")
    
    ports = {
        8000: "Backend API",
        5432: "PostgreSQL",
        6379: "Redis"
    }
    
    all_available = True
    for port, service in ports.items():
        if check_port_available(port):
            print(f"✅ Port {port} ({service}) is available")
        else:
            print(f"⚠️  Port {port} ({service}) is in use!")
            all_available = False
    
    if not all_available:
        print("\n⚠️  WARNING: Some ports are in use. This may cause issues.")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            return False
    
    return True


def start_docker_compose():
    """Start Docker Compose services"""
    print_header("Step 3: Building and Starting Docker Containers")
    
    print("🚀 Building and Starting Docker Containers...")
    print("   This may take a few minutes on first run...\n")
    
    returncode, stdout, stderr = run_command(
        "docker compose up -d --build",
        cwd=None,  # Run from root
        capture_output=False
    )
    
    if returncode != 0:
        print(f"\n❌ Docker Compose failed to start (exit code: {returncode})")
        return False
    
    print("\n✅ Docker Compose started successfully")
    return True


def health_check_loop():
    """Poll health endpoint until ready or timeout"""
    print_header("Step 4: Health Check")
    
    url = "http://localhost:8000/health"
    timeout = 60  # seconds
    interval = 2  # seconds
    start_time = time.time()
    
    print(f"🔍 Polling {url} every {interval} seconds...")
    print(f"   Timeout: {timeout} seconds\n")
    
    attempt = 0
    while time.time() - start_time < timeout:
        attempt += 1
        elapsed = int(time.time() - start_time)
        
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print(f"\n✅ System is READY! (after {elapsed} seconds, {attempt} attempts)")
                print(f"   Response: {response.json()}")
                return True
            else:
                print(f"⏳ Attempt {attempt} ({elapsed}s): Status {response.status_code}")
        except requests.exceptions.ConnectionError:
            print(f"⏳ Attempt {attempt} ({elapsed}s): Connection refused (service starting...)")
        except requests.exceptions.Timeout:
            print(f"⏳ Attempt {attempt} ({elapsed}s): Request timeout")
        except Exception as e:
            print(f"⏳ Attempt {attempt} ({elapsed}s): {type(e).__name__}")
        
        time.sleep(interval)
    
    print(f"\n❌ Health check TIMEOUT after {timeout} seconds")
    return False


def show_logs():
    """Show Docker Compose logs for debugging"""
    print_header("Docker Compose Logs (Last 50 lines)")
    
    print("📋 Fetching logs...\n")
    returncode, stdout, stderr = run_command(
        "docker compose logs --tail=50",
        cwd=None,  # Run from root
        capture_output=True
    )
    
    if stdout:
        print(stdout)
    if stderr:
        print(stderr)


def cleanup():
    """Stop Docker Compose services"""
    print_header("Cleanup")
    
    print("🛑 Stopping Docker Compose services...")
    returncode, stdout, stderr = run_command(
        "docker compose down",
        cwd=None,  # Run from root
        capture_output=True
    )
    
    if returncode == 0:
        print("✅ Services stopped successfully")
    else:
        print(f"⚠️  Warning: docker compose down returned {returncode}")


def main():
    """Main test flow"""
    print_header("Docker Startup Test - Multi-tenant RAG System")
    
    try:
        # Step 1: Clean slate
        if not clean_slate():
            print("❌ Failed to clean up")
            return 1
        
        # Step 2: Check ports
        if not check_ports():
            print("❌ Port check failed")
            return 1
        
        # Step 3: Start Docker Compose
        if not start_docker_compose():
            print("❌ Failed to start Docker Compose")
            show_logs()
            cleanup()
            return 1
        
        # Step 4: Health check
        if not health_check_loop():
            print("❌ Health check failed")
            show_logs()
            cleanup()
            return 1
        
        # Success!
        print_header("✅ SUCCESS - System is Ready!")
        print("🎉 The system passed the One-Command Startup test!")
        print("\n📍 Next steps:")
        print("   - API Docs: http://localhost:8000/docs")
        print("   - Health Check: http://localhost:8000/health")
        print("\n💡 To stop the system:")
        print("   docker compose down")
        
        return 0
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        cleanup()
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        cleanup()
        return 1


if __name__ == "__main__":
    sys.exit(main())
