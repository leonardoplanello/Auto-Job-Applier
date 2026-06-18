import subprocess
import sys
import os
import time
import socket
import webbrowser


def install_python_requirements():
    print("Checking and installing Python dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("Python dependencies verified.")
    except Exception as e:
        print(f"Warning: Failed to auto-install dependencies: {str(e)}")

def build_react_frontend():
    frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
    dist_dir = os.path.join(frontend_dir, "dist")
    
    if os.path.exists(frontend_dir) and not os.path.exists(dist_dir):
        print("Frontend build output (dist) is missing. Compiling React frontend...")
        try:
            # Run npm install if node_modules is missing
            node_modules = os.path.join(frontend_dir, "node_modules")
            if not os.path.exists(node_modules):
                print("Running 'npm install' in frontend folder...")
                subprocess.check_call("npm install", shell=True, cwd=frontend_dir)
                
            print("Running 'npm run build' in frontend folder...")
            subprocess.check_call("npm run build", shell=True, cwd=frontend_dir)
            print("React frontend compiled successfully.")
        except Exception as e:
            print(f"Error compiling React frontend: {str(e)}")
            print("Please compile manually using 'cd frontend && npm install && npm run build'")

def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def wait_for_server(port: int, timeout: int = 15) -> bool:
    start_time = time.time()
    while time.time() - start_time < timeout:
        if is_port_in_use(port):
            return True
        time.sleep(0.5)
    return False

def start_application():
    # 1. Install requirements
    install_python_requirements()
    
    # 2. Compile React App to Static Files (for production FastAPI serving)
    build_react_frontend()
    
    # 3. Port check
    port = 7000
    if is_port_in_use(port):
        print(f"Port {port} is already in use. The backend is likely already running.")
        print(f"Please open your browser manually and navigate to http://localhost:{port}")
        webbrowser.open(f"http://localhost:{port}")
        return
        
    print(f"Starting FastAPI backend on http://localhost:{port}...")
    
    # Spawn uvicorn process
    try:
        # We start uvicorn in a subprocess
        cmd = [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", str(port)]
        backend_proc = subprocess.Popen(cmd)
        
        # Wait for port 7000 to be responsive
        if wait_for_server(port):
            print("Server is responsive.")
            print(f"Please open your browser manually and navigate to http://localhost:{port}")
            webbrowser.open(f"http://localhost:{port}")
            
            # Keep parent script running to monitor uvicorn
            backend_proc.wait()
        else:
            print("Server failed to respond within timeout.")
            backend_proc.terminate()
            
    except KeyboardInterrupt:
        print("\nStopping Auto J*b Applier...")
    except Exception as e:
        print(f"Error starting application: {str(e)}")

if __name__ == "__main__":
    start_application()
