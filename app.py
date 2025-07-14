from flask import Flask, request, jsonify
import subprocess
import uuid
import json
import threading
import time
from datetime import datetime, timedelta
import logging

# --- Logging Configuration ---
# Configure logging to output to the console with a specific format and level.
# This setup is done once when the application starts.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)
# --- End of Logging Configuration ---

app = Flask(__name__)

IMAGE_NAME = "python:3.13-alpine"
INACTIVITY_TIMEOUT = 60  # seconds
WORKDIR = "/workspace"
session_containers = {}
session_lock = threading.Lock()

def now():
    return datetime.utcnow()

def create_container():
    """Creates a new Docker container."""
    container_name = f"sandbox-{uuid.uuid4().hex[:8]}"
    logger.info(f"Attempting to create container: {container_name}")
    
    # Start the container
    start_cmd = ["docker", "run", "-d", "--name", container_name, IMAGE_NAME, "sleep", "3600"]
    start_proc = subprocess.run(start_cmd, capture_output=True, text=True)
    if start_proc.returncode != 0:
        error_message = f"Error starting container: {start_proc.stderr}"
        logger.error(error_message)
        raise Exception(error_message)
        
    logger.info(f"Container {container_name} started successfully.")
    
    # Create the workspace directory
    mkdir_cmd = ["docker", "exec", container_name, "mkdir", "-p", WORKDIR]
    mkdir_proc = subprocess.run(mkdir_cmd, capture_output=True, text=True)
    if mkdir_proc.returncode != 0:
        logger.error(f"Error creating workspace in {container_name}. Cleaning up.")
        destroy_container(container_name)  # Clean up the failed container
        error_message = f"Error creating workspace: {mkdir_proc.stderr}"
        raise Exception(error_message)
        
    logger.info(f"Workspace created in {container_name}.")
    return container_name

def destroy_container(container_name):
    """Stops and removes a Docker container forcefully."""
    logger.info(f"Destroying container: {container_name}")
    subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)

def run_code_in_container(container_name, code, data_vars):
    """Executes Python code inside the specified container."""
    data_code = "".join([f"{k} = {json.dumps(v)}\n" for k, v in data_vars.items()])
    full_code = (
        "import json\n"
        + data_code
        + "\n"
        + code
        + "\nprint(json.dumps(result))"
    )
    
    exec_cmd = ["docker", "exec", "-i", "-w", WORKDIR, container_name, "python3"]
    logger.info(f"Executing code in container {container_name}")
    exec_proc = subprocess.run(exec_cmd, input=full_code, capture_output=True, text=True)
    
    if exec_proc.returncode != 0:
        error_message = f"Error running code: {exec_proc.stderr}\nSTDOUT:\n{exec_proc.stdout}"
        logger.error(f"Code execution failed in {container_name}. Details: {error_message}")
        return None, error_message
        
    output_lines = exec_proc.stdout.strip().split('\n')
    json_result = next((line for line in reversed(output_lines) if line.strip()), "null")
    
    try:
        result = json.loads(json_result)
        logger.info(f"Code executed successfully in {container_name}.")
    except Exception as e:
        error_message = f"Could not parse result as JSON: {e}\nRaw output:\n{exec_proc.stdout}"
        logger.error(f"JSON parsing failed for output from {container_name}. Details: {error_message}")
        return None, error_message
        
    return result, None

def list_files_in_workspace(container_name):
    """Lists all files and folders in the container's workspace."""
    exec_cmd = ["docker", "exec", container_name, "sh", "-c", f"ls -lR {WORKDIR}"]
    proc = subprocess.run(exec_cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        logger.warning(f"Failed to list files in workspace for {container_name}")
        return "Error listing files"
    return proc.stdout

def cleanup_inactive_containers():
    """Periodically checks for and removes inactive containers."""
    logger.info("Cleanup thread started.")
    while True:
        time.sleep(10)
        with session_lock:
            to_remove = []
            for user_id, info in session_containers.items():
                if now() - info["last_active"] > timedelta(seconds=INACTIVITY_TIMEOUT):
                    logger.info(f"Session for user {user_id} timed out. Removing container {info['container_name']}.")
                    destroy_container(info["container_name"])
                    to_remove.append(user_id)
            
            if to_remove:
                for user_id in to_remove:
                    del session_containers[user_id]
                logger.info(f"Cleaned up {len(to_remove)} inactive container(s).")

@app.route('/run', methods=['POST'])
def run():
    payload = request.json
    code = payload.get('code')
    data_vars = payload.get('data', {})
    user_id = payload.get('user_id')

    if not code or not user_id:
        logger.warning(f"Bad request: 'code' or 'user_id' missing from payload.")
        return jsonify({'error': 'Code and user_id required'}), 400

    logger.info(f"Received /run request from user_id: {user_id}")
    
    with session_lock:
        if user_id in session_containers:
            container_name = session_containers[user_id]["container_name"]
            session_containers[user_id]["last_active"] = now()
            logger.info(f"Reusing existing container {container_name} for user {user_id}")
        else:
            logger.info(f"No active session for user {user_id}. Creating new container.")
            try:
                container_name = create_container()
            except Exception as e:
                logger.critical(f"Failed to create a container for user {user_id}: {e}")
                return jsonify({'error': f'Could not create container: {e}'}), 500
            
            session_containers[user_id] = {
                "container_name": container_name,
                "last_active": now()
            }

    result, error = run_code_in_container(container_name, code, data_vars)
    files = list_files_in_workspace(container_name)

    response = {
        "result": result,
        "workspace_files": files.splitlines()
    }
    if error:
        response["error"] = error

    return jsonify(response)


if __name__ == '__main__':
    # Start the background thread for cleaning up inactive containers
    cleanup_thread = threading.Thread(target=cleanup_inactive_containers, daemon=True)
    cleanup_thread.start()
    
    # Start the Flask application
    # For production, use a proper WSGI server like Gunicorn or Waitress instead of app.run()
    logger.info("Starting Flask application on port 5000 with debug mode.")
    app.run(debug=True, port=5000)
