import configparser
import os
import json
import psutil
import time
import subprocess
import threading
from flask import Flask, jsonify
import obsws_python as obs

# Path to the OBS WebSocket config file in %appdata%
OBS_PATH = r'C:\\Program Files\\obs-studio\\bin\\64bit'
OBS_EXECUTABLE = 'obs64.exe'
OBS_EXECUTABLE_PATH = OBS_PATH + r'\\' + OBS_EXECUTABLE
CONFIG_PATH = os.path.join(os.getenv('APPDATA'), 'obs-studio', 'plugin_config', 'obs-websocket', 'config.json')
SCENE_COLLECTION_NAME = 'exam_recording'
SCENE_NAME = 'Scene'

global connectionParams
connectionParams = None
obs_process = None
recording_file_path = None  # Holds the last recorded file path
recording_saved_event = threading.Event()  # Event to signal when recording is saved

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

# Create Flask app
app = Flask(__name__)

# Route to start recording
@app.route('/start', methods=['GET'])
def start_recording():
    global recording_file_path
    recording_file_path = None # Reset before starting

    # Start OBS if not already running
    start_obs()
    
    # Connect to OBS
    obs_req = obs.ReqClient(**connectionParams)
    if obs_req is None:
        return jsonify({'error': 'Unable to connect to OBS WebSocket'}), 500

    # Set the scene collection if it exists
    if not scene_collection_exists(obs_req, SCENE_COLLECTION_NAME):
        return jsonify({'error': f"Scene collection '{SCENE_COLLECTION_NAME}' does not exist"}), 400

    # Select appropriate scene
    try:
        obs_req.set_current_scene_collection(SCENE_COLLECTION_NAME)
        obs_req.set_current_program_scene(SCENE_NAME)
    except Exception as e:
        return jsonify({'error': f"Failed to set scene collection or scene: {e}"}), 500

    # Start recording
    try:
        obs_req.start_record()
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    obs_event = obs.EventClient(**connectionParams)

    def on_record_state_changed(event_data):
        global recording_file_path
        if event_data.output_path:  # Check if outputPath is present in event data
            recording_file_path = event_data.output_path
            recording_saved_event.set()

    # Subscribe to RecordStateChanged event
    obs_event.callback.register(on_record_state_changed)

    if recording_saved_event.wait(60):
        return jsonify({'status': 'Recording started', 'path': recording_file_path})
    else:
        return jsonify({'status': 'Recording started', 'error': 'Timeout waiting for recording output file'}), 500

# Route to stop recording
@app.route('/stop', methods=['GET'])
def stop_recording():
    global recording_file_path

    # Save recording_file_path in a variable before clearing
    file_path = recording_file_path

    # Clear variables
    recording_file_path = None
    recording_saved_event.clear()

    obs_req = obs.ReqClient(**connectionParams)

    try:
        # Stop recording
        obs_req.stop_record()

        # Stop OBS if necessary
        stop_obs()

        if file_path:
            return jsonify({'status': 'Recording stopped', 'file_path': file_path})
        else:
            return jsonify({'status': 'Recording stopped', 'file_path': 'File path not available'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Main entry point
if __name__ == '__main__':
    # Start Flask server

    port, password = read_obs_config()
    connectionParams = {'port': port, 'password': password, 'timeout': 10}
    app.run(host='0.0.0.0', port=5055)