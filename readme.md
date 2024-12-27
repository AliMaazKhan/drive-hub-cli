# Drive Hub CLI

A simple command-line tool to manage files on Google Drive. This tool allows you to interact with Google Drive directly from your terminal, providing functionalities similar to `git`, such as staging, uploading, and checking the status of files in a project folder.

## Features

- **Authenticate with Google Drive**: Authenticate your Google account and access your Drive files.
- **Stage Files**: Select and stage files for uploading.
- **Push Files**: Upload staged files to a specific folder on Google Drive.
- **Status**: Check the status of files (staged, uploaded, ignored).
- **Drive Folder Management**: Create folders on Google Drive for organizing your files.
- **Ignore Files**: Use `.driveignore` to specify which files should be ignored during the upload process (similar to `.gitignore`).

## Requirements

- Python 3.x
- Google API Python Client
- Google OAuth2 credentials

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/drive-hub-cli.git
   cd drive-hub-cli
   ```
