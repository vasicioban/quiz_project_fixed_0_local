import json
import os
import subprocess
import threading
import time
from datetime import datetime

# install with pip
import psutil
import uuid
import obsws_python as obs

from flask import Flask, jsonify, request
from flask_cors import CORS

import smbclient # pip pkg smbprotocol

# Path to the OBS WebSocket config file in %appdata%
OBS_PATH = r'C:\\Program Files\\obs-studio\\bin\\64bit'
OBS_EXECUTABLE = 'obs64.exe'
OBS_EXECUTABLE_PATH = OBS_PATH + r'\\' + OBS_EXECUTABLE
CONFIG_PATH = os.path.join(os.getenv('APPDATA'), 'obs-studio', 'plugin_config', 'obs-websocket', 'config.json')
SCENE_COLLECTION_NAME = 'exam_recording'
SCENE_NAME = 'Scene'

# Server parameters
SERVER_IP = "192.168.16.164"
SERVER_USERNAME = "HIDROELECTRICA\\asseco"
SERVER_PASSWORD = "Mihalache!@#$%"
SHARE_NAME = "hidroquiz_recordings"  # The shared folder name on the SMB server

connectionParams = None
obs_process = None

original_recording_file_path = None  # Holds the last recorded file path
renamed_recording_file_path = None
destination_file_path = None
recording_saved_event = threading.Event()  # Event to signal when recording is saved

username = None

# Function to read OBS WebSocket config from config.json
def read_obs_config():
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)

    port = int(config['server_port'])
    password = config['server_password']

    if not config.get('server_enabled'):
        print('WebSocket plugin not enabled!')
        enable_ws(config)
    
    return port, password

def enable_ws(data):
    print('Enabling WebSocket plugin (only happens on the first run)')

    data['server_enabled'] = True

    with open(CONFIG_PATH, 'w') as f:
        json.dump(data, f)

# Check if OBS is already running
def is_obs_running():
    global obs_process
    for process in psutil.process_iter(['pid', 'name']):
        if process.info['name'] == 'obs64.exe':
            obs_process = process
            print(obs_process)
            return True
    return False

# Start OBS from the command line
def start_obs():
    global obs_process
    if not is_obs_running():
        obs_process = subprocess.Popen([OBS_EXECUTABLE_PATH, '--minimize-to-tray', '--disable-shutdown-check'], cwd=OBS_PATH)

# Stop the OBS process
def stop_obs():
    global obs_process
    if obs_process is not None:
        obs_process.terminate()
        obs_process = None

# Check if the specified scene collection exists
def scene_collection_exists(req_client, collection_name):
    collections = req_client.get_scene_collection_list().scene_collections
    return collection_name in collections

# Get final path the recording will have
def get_final_path(original_path):
    _, original_filename = os.path.split(original_path)
    original_filename = original_filename.replace(' ', '_')
    new_filename = f"{username}_{original_filename}"

    destination_file_path = f"\\\\{SERVER_IP}\\{SHARE_NAME}\\{new_filename}"
    
    new_path = os.path.join(destination_file_path, new_filename)
    print('final_path: ', new_path)

    return new_path
    

# Rename the local file with username
def rename_local_file(original_path, username):
    directory, original_filename = os.path.split(original_path)
    original_filename = original_filename.replace(' ', '_')
    new_filename = f"{username}_{original_filename}"  # Adjust extension if needed
    new_path = os.path.join(directory, new_filename)

    try:
        os.rename(original_path, new_path)
        print(f"File renamed locally to {new_path}")
        return new_path
    except Exception as e:
        print(f"Error renaming file: {e}")
        return None


# Move file to server with SMB
def move_file_to_server_smb(file_path):
    # Define date folder and destination path on the SMB server
    date_folder = datetime.now().date().isoformat()  # ISO 8601 format YYYY-MM-DD
    destination_path = f"\\\\{SERVER_IP}\\{SHARE_NAME}\\{date_folder}\\{os.path.basename(file_path)}"
    print('destination_path ', destination_path)

    try:
        smbclient.makedirs(f"\\\\{SERVER_IP}\\{SHARE_NAME}\\{date_folder}", exist_ok=True)

        with open(file_path, "rb") as local_file, smbclient.open_file(destination_path, mode="wb") as remote_file:
            remote_file.write(local_file.read())
            
        print(f"File successfully moved to {destination_path}")
    except Exception as e:
        print(f"Error transferring file via SMB: {e}")

# Create Flask app
app = Flask(__name__)
CORS(app)

# Route to start recording
@app.route('/start', methods=['GET'])
def start_recording():
    global original_recording_file_path, username
    
    username = request.args.get('username', 'unknown_user')
    
    # Connect to OBS
    obs_req = obs.ReqClient(**connectionParams)
    if obs_req is None:
        return jsonify({'error': 'Unable to connect to OBS WebSocket'}), 500

    def on_record_state_changed(event_data):
        global original_recording_file_path
        if event_data.output_path:  # Check if outputPath is present in event data
            original_recording_file_path = event_data.output_path.replace('/', '\\')
            print(f'original_recording_file_path = {original_recording_file_path}')
            recording_saved_event.set()

        if not event_data.output_active and event_data.output_path:
            # Rename the file locally and then move it to the server
            print(f'calling rename_local_file({original_recording_file_path}, {username})')
            renamed_path = rename_local_file(original_recording_file_path, username)
            if renamed_path:
                move_file_to_server_smb(renamed_path)

    # Subscribe to RecordStateChanged event
    obs_event = obs.EventClient(**connectionParams)
    obs_event.callback.register(on_record_state_changed)
    
    # Start recording
    try:
        obs_req.start_record()
        if recording_saved_event.wait(60):
            return jsonify({'status': 'Recording started', 'path': get_final_path(original_recording_file_path)})
        else:
            return jsonify({'status': 'Recording started', 'error': 'Timeout waiting for recording output file'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Route to stop recording
@app.route('/stop', methods=['GET'])
def stop_recording():
    global original_recording_file_path

    obs_req = obs.ReqClient(**connectionParams)

    try:
        # Stop recording
        obs_req.stop_record()
        
        # Clear variables
        temp_file_path = original_recording_file_path
        original_recording_file_path = None
        recording_saved_event.clear()
        
        return jsonify({'status': 'Recording stopped', 'path': get_final_path(temp_file_path)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Main entry point
if __name__ == '__main__':
    # Start Flask server

    port, password = read_obs_config()
    connectionParams = {'port': port, 'password': password, 'timeout': 10}
    smbclient.register_session(SERVER_IP, username=SERVER_USERNAME, password=SERVER_PASSWORD)
    start_obs()
    app.run(host='0.0.0.0', port=5055)
