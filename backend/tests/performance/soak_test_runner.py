
import os
import subprocess
import time
import psutil
import requests
import signal
import sys
import json
from datetime import datetime

# Configuration
DURATION_SECONDS = 300  # 5 minutes for demo/CI (User can increase to 1800)
MEMORY_THRESHOLD_MB = 1000 # 1GB Max
INITIAL_WAIT = 10
host = "http://127.0.0.1:8000"

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def check_server():
    try:
        r = requests.get(f"{host}/health", timeout=2)
        return r.status_code == 200
    except:
        return False

def run_soak_test():
    log("🚀 Starting Soak Test Runner")
    
    # 1. Start Server
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd()
    
    # Use explicit path to python
    python_exe = sys.executable
    if "python" not in python_exe:
        python_exe = os.path.join("..", ".venv", "Scripts", "python.exe")
        
    server_cmd = [python_exe, "-m", "uvicorn", "app.main:app", "--port", "8000", "--host", "127.0.0.1"]
    
    log(f"Starting server: {' '.join(server_cmd)}")
    server_process = subprocess.Popen(server_cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) # Silence server logs
    
    try:
        # Wait for healthy
        log("Waiting for server health check...")
        up = False
        for _ in range(30):
            if check_server():
                up = True
                break
            time.sleep(1)
            
        if not up:
            log("❌ Server failed to start")
            return
            
        log("✅ Server is UP")
        
        # Get Process ID for monitoring
        proc = psutil.Process(server_process.pid)
        initial_mem = proc.memory_info().rss / 1024 / 1024
        log(f"Initial Memory: {initial_mem:.2f} MB")
        
        # 2. Start Locust
        # Run headless, 20 users, spawn 2/s
        locust_cmd = [
            python_exe, "-m", "locust", 
            "-f", "tests/performance/locustfile.py", 
            "--headless", 
            "-u", "20", "-r", "2", 
            "--host", host,
            "--run-time", f"{DURATION_SECONDS}s",
            "--only-summary"
        ]
        
        log(f"Starting Locust: {' '.join(locust_cmd)}")
        locust_process = subprocess.Popen(locust_cmd, env=env)
        
        # 3. Monitor Loop
        start_time = time.time()
        max_mem = initial_mem
        mem_history = []
        
        while time.time() - start_time < DURATION_SECONDS:
            if locust_process.poll() is not None:
                log("⚠️ Locust finished early")
                break
                
            mem = proc.memory_info().rss / 1024 / 1024
            mem_history.append(mem)
            max_mem = max(max_mem, mem)
            
            # log(f"Memory: {mem:.2f} MB (Peak: {max_mem:.2f} MB)")
            
            if mem > MEMORY_THRESHOLD_MB:
                log(f"❌ MEMORY LEAK DETECTED: {mem:.2f} MB exceeding {MEMORY_THRESHOLD_MB} MB")
                locust_process.terminate()
                break
                
            time.sleep(5)
            
        log("Soak test completed.")
        final_mem = proc.memory_info().rss / 1024 / 1024
        growth = final_mem - initial_mem
        
        log(f"Final Memory: {final_mem:.2f} MB")
        log(f"Total Growth: {growth:.2f} MB")
        
        report = {
            "status": "PASS" if final_mem < MEMORY_THRESHOLD_MB else "FAIL",
            "duration": DURATION_SECONDS,
            "initial_memory_mb": initial_mem,
            "final_memory_mb": final_mem,
            "growth_mb": growth,
            "peak_memory_mb": max_mem
        }
        
        with open("soak_report.json", "w") as f:
            json.dump(report, f, indent=2)
            
        if report["status"] == "PASS":
            log("✅ SOAK TEST PASSED: System stable.")
        else:
            log("❌ SOAK TEST FAILED: Memory instability.")
            
    finally:
        # Cleanup
        log("Shutting down processes...")
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except:
            server_process.kill()
            
        if 'locust_process' in locals():
            locust_process.terminate()

if __name__ == "__main__":
    run_soak_test()
