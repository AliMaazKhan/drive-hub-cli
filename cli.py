import os
from googleapiclient.http import MediaFileUpload
import fnmatch
import hashlib
import json
from typing import List
import typer
from drive import (
    pull,
    add as drive_add,
)
from authenticate import authenticate
from googleapiclient.discovery import build

app = typer.Typer()


def list_files_and_dirs(path):
    for root, dirs, files in os.walk(path):
        print(f"Current Directory: {root}")
        print(f"Subdirectories: {dirs}")
        print(f"Files: {files}")

def get_service(creds):
    """Initialize and return the Google Drive service."""
    return build("drive", "v3", credentials=creds)

def create_drive_folder(service, folder_name):
    """Create a folder on Google Drive."""
    file_metadata = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    folder = service.files().create(body=file_metadata, fields="id").execute()
    return folder.get("id")

def upload_file(service, file_path, parent_id):
    """Upload a file to Google Drive."""
    file_metadata = {"name": os.path.basename(file_path), "parents": [parent_id]}
    media = MediaFileUpload(file_path, resumable=True)
    service.files().create(body=file_metadata, media_body=media, fields="id").execute()

def upload_folder(service, folder_path, parent_id):
    """Recursively upload a folder to Google Drive."""
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            file_path = os.path.join(root, file)
            upload_file(service, file_path, parent_id)



def get_file_hash(file_path: str) -> str:
    """Generate a hash for the given file."""
    hash_sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            hash_sha256.update(chunk)
    return hash_sha256.hexdigest()

def load_state_file() -> dict:
    """Load the saved file states from .drivestate."""
    if os.path.exists(".drivestate"):
        with open(".drivestate", "r") as f:
            return json.load(f)
    return {}

def save_state_file(state: dict):
    """Save the current file states to .drivestate."""
    with open(".drivestate", "w") as f:
        json.dump(state, f, indent=2)


@app.command()
def init():
    """Initialize the Google Drive project."""
    local_folder = os.path.basename(os.getcwd())
    creds = authenticate()
    service = get_service(creds)
    
    # Create a folder on Google Drive
    drive_folder_id = create_drive_folder(service, local_folder)
    config = {"drive_folder_id": drive_folder_id}
    
    # Save the configuration locally
    with open(".driveconfig", "w") as f:
        json.dump(config, f)
    
    print("Google Drive project initialized successfully.")
    print(f"Linked to Drive folder: {local_folder} (ID: {drive_folder_id})")

@app.command()
def stage(files: List[str] = None):
    """Stage files for upload, only if they have changed."""
    state = load_state_file()
    files_to_stage = []

    if files is None or "." in files:  # If "." is passed or no files are passed
        all_files = [f for f in os.listdir('.') if os.path.isfile(f)]
        for file in all_files:
            current_hash = get_file_hash(file)
            if state.get(file) != current_hash:  # If the file has changed
                files_to_stage.append(file)
                state[file] = current_hash
    else:
        for file in files:
            if os.path.exists(file):  # Check if the file exists
                current_hash = get_file_hash(file)
                if state.get(file) != current_hash:  # If the file has changed
                    files_to_stage.append(file)
                    state[file] = current_hash
            else:
                print(f"Warning: File {file} does not exist.")
    
    if files_to_stage:
        print(f"Staging changed files: {files_to_stage}")
        drive_add(files_to_stage)
        save_state_file(state)  # Save the new file states
    else:
        print("No files have changed, nothing to stage.")

@app.command()
def download():
    """Download files from Google Drive."""
    creds = authenticate()
    service = get_service(creds)
    pull(service, "./")

@app.command()
def status():
    """Show the status of files in the directory."""
    state = load_state_file()
    current_files = {f: get_file_hash(f) for f in os.listdir('.') if os.path.isfile(f)}
    ignored_files = set()

    # Load ignore patterns from .driveignore
    if os.path.exists(".driveignore"):
        with open(".driveignore", "r") as f:
            patterns = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        for pattern in patterns:
            ignored_files.update(fn for fn in current_files if fnmatch.fnmatch(fn, pattern))

    tracked_files = set(state.keys())
    all_files = set(current_files.keys())
    untracked_files = all_files - tracked_files - ignored_files
    modified_files = {file for file in tracked_files if file in current_files and state[file] != current_files[file]}
    staged_files = {file for file in tracked_files if file not in modified_files}

    # Output status
    print("### Google Drive Status ###")
    if staged_files:
        print("\nStaged files (ready for upload):")
        for file in staged_files:
            print(f"  {file}")

    if modified_files:
        print("\nModified files (not staged):")
        for file in modified_files:
            print(f"  {file}")

    if untracked_files:
        print("\nUntracked files:")
        for file in untracked_files:
            print(f"  {file}")

    if not staged_files and not modified_files and not untracked_files:
        print("\nNothing to commit, working directory is clean.")

@app.command()
def push():
    """Push changes to Google Drive."""
    # Read the configuration
    if not os.path.exists(".driveconfig"):
        print("This folder is not initialized. Run 'init' first.")
        return

    with open(".driveconfig", "r") as f:
        config = json.load(f)

    drive_folder_id = config.get("drive_folder_id")
    if not drive_folder_id:
        print("Drive folder ID missing in configuration. Reinitialize with 'init'.")
        return

    # Authenticate and upload
    creds = authenticate()
    service = get_service(creds)
    local_folder = os.getcwd()

    # Read .driveignore patterns
    ignore_patterns = []
    if os.path.exists(".driveignore"):
        with open(".driveignore", "r") as f:
            ignore_patterns = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    # Collect files to upload
    for root, dirs, files in os.walk(local_folder):
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, local_folder)
            if any(fnmatch.fnmatch(rel_path, pattern) for pattern in ignore_patterns):
                continue
            upload_file(service, file_path, drive_folder_id)
    
    print("Push completed successfully.")


if __name__ == "__main__":
    app()

