from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
import asyncio
from contextlib import asynccontextmanager
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import signal
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Directory to monitor
directory_to_watch = '../testserverpath'

# Dictionary to hold file versions for each host
file_versions = {}

class FileData(BaseModel):
    hostname: str
    files: dict

#Watchdog class that checks serverdir for changes and updates modtimes of all hosts and their files
class WatchdogEventHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.is_directory:
            return
        logger.info(f"File modified: {event.src_path}")
        update_file_versions()

    def on_created(self, event):
        if event.is_directory:
            return
        logger.info(f"File created: {event.src_path}")
        update_file_versions()

    def on_deleted(self, event):
        if event.is_directory:
            return
        logger.info(f"File deleted: {event.src_path}")
        update_file_versions()

    def on_moved(self, event):
        if event.is_directory:
            logger.info(f"Directory moved: {event.src_path} to {event.dest_path}")
        else:
            logger.info(f"File moved: {event.src_path} to {event.dest_path}")
        update_file_versions()

    

def update_file_versions():
    global file_versions
    for hostname in os.listdir(directory_to_watch):
        hostname_path = os.path.join(directory_to_watch, hostname)
        if os.path.isdir(hostname_path):
            current_versions = {}
            for filename in os.listdir(hostname_path):
                filepath = os.path.join(hostname_path, filename)
                if os.path.isfile(filepath):
                    current_versions[filename] = os.path.getmtime(filepath)
            file_versions[hostname] = current_versions

    # Print the contents of file_versions for debugging
    print("Current file_versions:")
    for hostname, versions in file_versions.items():
        print(f"Hostname: {hostname}")
        for filename, mtime in versions.items():
            print(f"  File: {filename}, Modified Time: {mtime}")
    print(file_versions)
    logger.info("File versions updated")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize watchdog observer
    event_handler = WatchdogEventHandler()
    observer = Observer()
    observer.schedule(event_handler, directory_to_watch, recursive=True)
    observer.start()
    try:
        # Run the initial update
        update_file_versions()
        yield
    finally:
        logger.info("Shutting down, stopping watchdog observer...")
        observer.stop()
        observer.join()

app.router.lifespan_context = lifespan

@app.post('/post')
async def receive_post(file_data: FileData):
    file_versions[file_data.hostname] = file_data.files
    return {'message': 'Data received'}

@app.post('/check_updates')
async def check_updates(file_data: FileData):
    if file_data.hostname not in file_versions:
        print(f"{file_data.hostname} not found")
        
        raise HTTPException(status_code=404, detail='file_data.hostname not found')

    remote_files = file_versions[file_data.hostname]
    updates = {filename: remote_files[filename] for filename in remote_files if filename not in file_data.files or remote_files[filename] > file_data.files[filename]}

    return updates

@app.get('/download/{hostname}/{filename}')
async def download_file(hostname: str, filename: str):
    filepath = os.path.join(directory_to_watch, hostname, filename)

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail='File not found')

    return FileResponse(filepath)

if __name__ == '__main__':
    import uvicorn

    def handle_exit(sig, frame):
        logger.info(f"Received exit signal {sig}...")
        # Gracefully shutdown the server
        uvicorn.Server.should_exit = True

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    uvicorn.run(app, host='0.0.0.0', port=8000)