import requests
import os
import time
import socket
import argparse

hostname = socket.gethostname()
# Replace with your server URL
SERVER_URL = 'http://localhost:8000'

# Directory on the client where files are stored
client_directory = 'clientfiles'
hostname
# Local representation of file versions
local_file_versions = {}

def parseargs():
    parser = argparse.ArgumentParser(description='A great argparse function example.')
    parser.add_argument('-rpm','--rpm-self-update',action='store_true',required=False,help='if set, checks for new Versions of Alloy on remote and installs it if nessesary - needs the be able to sudo rpm -U XX')
    # Parsing arguments
    args = parser.parse_args()
    return args

def fetch_server_versions():
    try:
        response = requests.post(f'{SERVER_URL}/check_updates', json={'hostname': hostname, 'files': local_file_versions})
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching server versions: {e}")
        return {}
    
def fetch_server_rpmversions():
    try:
        response = requests.post(f'{SERVER_URL}/download/alloy_rpm')
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching server rpmversions: {e}")
        return {}

def delete_local_file(filename):
    try:
        os.remove(os.path.join(client_directory, filename))
        print(f"Deleted local file: {filename}")
    except OSError as e:
        print(f"Error deleting local file {filename}: {e}")

def download_file(filename:str,mtime):
    try:
        response = requests.get(f'{SERVER_URL}/download/{hostname}/{filename}')
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching file: {e}")
        return {}
    try:
        with open(os.path.join(client_directory, filename),'wb') as f:
            f.write(response.content)
        print(f"File '{filename}' downloaded successfully.")
    except Exception as e:
        print(f"File '{filename}' failed to write. {e}")
    try:
        os.utime(os.path.join(client_directory, filename), times=(mtime,mtime))
        print(f"File '{filename}' utime successfully set to {(mtime,mtime)}.")
    except Exception as e:
        print(f"File '{filename}' failed to set utime. {e}")

def check_for_updates():
    print("Checking for Updates...")
    server_updates = fetch_server_versions()
    #print("server_files:",server_updates)
    # Check local files
    current_versions = {}
    for filename in os.listdir(client_directory):
        filepath = os.path.join(client_directory, filename)
        if os.path.isfile(filepath):
            current_versions[filename] = os.path.getmtime(filepath)
    #print("local_files",current_versions)
    #check local dir against remote dir - to delete/mark for update
    keys_matched=[]
    update=None
    for key in current_versions:
        try:
            value_from_dict2 = next(server_updates[key] for dict2_key in server_updates if dict2_key == key)
            if value_from_dict2>current_versions[key]:
                print(f"Update found on {key} localmtime: {current_versions[key]} < remotemtime: {value_from_dict2}")
                update=True
                download_file(key,value_from_dict2)
            keys_matched.append(key)
        except StopIteration:
            print(f"{key} not found on remote > deleting locally")
            update=True
            delete_local_file(key)
    
    for key in server_updates:
        matched=False
        for matched_key in keys_matched:
            if matched_key==key:
                matched=True
                break
        if matched==True:
            continue
        else:
            update=True
            print(f"New File {key} detected")
            download_file(key,server_updates[key])
        
    if not update:
        return "No Updates"
    else:
        return "Updates"

def check_for_rpmupdates():
    print("Checking for Updates RPM...")
    server_updates = fetch_server_rpmversions()

def main(checkrpm:bool):
    while True:
        start_time=time.time()
        updates=check_for_updates()
        if checkrpm:
            rpmupdates=check_for_rpmupdates()
        end_time=time.time()
        elapsed_time = end_time - start_time
        print(updates, "elapsed time:", elapsed_time)
        time.sleep(5)  # Check for updates every minute (adjust interval as needed)

if __name__ == '__main__':
    args=parseargs()
    if args['rpm-self-update']:
        main(True)
    else:
        main(False)