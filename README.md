# O2FileSearchPlus Enhanced

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Node.js 18+](https://img.shields.io/badge/node.js-18+-green.svg)](https://nodejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-00a393.svg)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-15-black.svg)](https://nextjs.org/)

O2FileSearchPlus Enhanced is a powerful local file search and indexing tool with a web-based interface. It allows users to quickly find files based on various criteria, view detailed metadata, preview text file content, and manage search results efficiently.

## Key Features

- **Fast File Indexing**: Recursively scans specified root directories to build a searchable index of files.
- **Advanced Search**:
    - Filter by file extensions, size range, creation/modification date range.
    - Search by partial or full file names.
    - Search for terms within indexed text file content (supports AND/OR logic for terms).
    - Case-sensitive and case-insensitive search options.
    - Filter by file owner.
    - Identify duplicate files based on content hash.
- **Interactive Results Table**: Displays search results with sortable columns for file name, size, modification date, owner, and type.
- **Enhanced File Preview Modal**:
    - Shows detailed metadata: full path, name, size, extension, creation date, modified date, owner.
    - Displays the text content of recognized text files (up to the first 50KB indexed).
    - Loading indicators and appropriate messages for binary files or content loading errors.
- **Copy to Clipboard**: Easily copy the full file path from the results table or the preview modal.
- **Export Results**: Export current search results to a CSV file.
- **Indexing Status & Statistics**: View progress during indexing, last index date, total files indexed, and overall statistics (total files, text files, total size, top file extensions).

## Technology Stack

- **Backend**:
    - Python 3.x
    - FastAPI (for the REST API)
    - SQLite (for storing the file index)
    - Uvicorn (as the ASGI server)
- **Frontend**:
    - Next.js (React framework v15+)
    - TypeScript
    - Tailwind CSS (for styling)
    - Axios (for API requests)
    - `lucide-react` (for icons)
    - `react-hot-toast` (for notifications)
    - `date-fns` (for date formatting)

## Setup and Running

### Prerequisites

- Python 3.7+ and Pip
- Node.js (v18.x or later recommended) and npm

### 1. Clone the Repository

First, clone the repository to your local machine:
```bash
git clone https://github.com/your-username/O2FileSearchPlus.git
cd O2FileSearchPlus
```
Replace `https://github.com/your-username/O2FileSearchPlus.git` with the actual repository URL.

### 2. Backend Setup

1.  Navigate to the `backend` directory (from the project root after cloning):
    ```bash
    cd backend
    ```
2.  (Recommended) Create and activate a virtual environment:
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```
3.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
4.  Run the backend server:
    ```bash
    python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
    ```
    The backend API will be available at `http://localhost:8000`.
    A SQLite database file (default: `file_index.db`) will be created in this directory upon first run/indexing.

### 3. Frontend Setup

1.  Navigate to the `frontend` directory (from the project root after cloning):
    ```bash
    cd frontend
    ```
2.  Install dependencies:
    ```bash
    npm install
    ```
3.  Run the frontend development server:
    ```bash
    npm run dev
    ```
    The frontend application will typically be available at `http://localhost:3000`. If port 3000 is busy, Next.js will automatically pick the next available port (e.g., 3001).

## Usage

1.  **Start Servers**: Ensure both backend and frontend servers are running.
2.  **Indexing Files**:
    - Open the application in your browser.
    - Navigate to the "Index" tab.
    - Enter the absolute root path of the directory you want to index (e.g., `/home/user/documents`).
    - Click "Start Indexing". You can monitor the progress.
3.  **Searching Files**:
    - Go to the "Search" tab.
    - Use the various input fields and checkboxes to define your search criteria.
    - Click "Search Files".
4.  **Previewing Files**:
    - In the search results table, click the "Preview" (eye icon) button next to a file.
    - The modal will display file metadata. If it's a recognized text file, its content (from the index) will be loaded and displayed.
5.  **Copying File Paths**:
    - Click the "Copy Path" (copy icon) button in the results table or within the preview modal.
6.  **Exporting Results**:
    - After a search, click the "Export CSV" button to download the current results.

## Important Notes for Version Control (e.g., GitHub)

- The SQLite database file (e.g., `file_index.db` in the `backend` directory) stores all the indexed file information. It is recommended **not** to commit this file to version control.
- `node_modules` in the `frontend` directory should not be committed.
- Any Python virtual environment directories (e.g., `venv` in `backend`) should not be committed.
- Next.js build artifacts (typically in `frontend/.next/`) should not be committed.
- Ensure these are listed in your root `.gitignore` file.


   
   The web interface will be available at `http://localhost:3000`

---

## Usage

### Initial Setup

1. **Start both backend and frontend servers**
2. **Open web interface** at `http://localhost:3000`
3. **Navigate to Index tab**
4. **Set root path** (e.g., `/home/username`)
5. **Click "Start Indexing"** and wait for completion

### Searching Files

1. **Navigate to Search tab**
2. **Set your filters**:
   - File extensions (e.g., `txt, py, js, md`)
   - Partial file names (e.g., `config, test, main`)
   - Search terms for content search
   - Size limits and date ranges
3. **Click "Search Files"**
4. **Export results** as CSV if needed

### Managing Index

- **Monitor progress** in the Index tab
- **View statistics** in the Statistics tab
- **Re-index** when adding new files or directories

---

## API Endpoints

### Search
- `POST /api/search` - Search files with filters
- `GET /api/duplicates` - Get duplicate files

### Indexing
- `POST /api/index` - Start indexing a directory
- `GET /api/status` - Get indexing status and progress

### Statistics
- `GET /api/statistics` - Get database statistics

---

## Configuration

### Backend Configuration
The backend automatically configures itself, but you can modify:
- Database path in `main.py`
- Excluded directories in `FileIndexer.should_skip_directory()`
- File size limits and other constraints

### Frontend Configuration
- API endpoint in `next.config.js`
- Styling in `tailwind.config.js`
- Component behavior in React components

---

## Troubleshooting

### Common Issues

1. **Frontend shows "connection refused" or "search failed"**:
   - Make sure the backend server is running (`uvicorn main:app --host 0.0.0.0 --port 8000` in the `backend` directory).
   - Both backend and frontend must be running at the same time.

2. **Backend won't start**:
   - Check Python version (3.8+)
   - Verify virtual environment activation
   - Install missing dependencies

3. **Frontend build errors**:
   - Check Node.js version (18+)
   - Clear node_modules and reinstall
   - Verify TypeScript configuration

4. **Indexing fails**:
   - Check file permissions
   - Verify disk space
   - Review excluded directories

5. **Search returns no results**:
   - Ensure indexing completed successfully
   - Check search criteria
   - Verify database integrity

---

## How to Push This Project to GitHub (Step-by-Step for Beginners)

**1. Create a GitHub account (if you don't have one):**
   - Go to https://github.com and sign up.

**2. Create a new repository on GitHub:**
   - Click the "+" in the top right, then "New repository".
   - Name it (e.g., `O2FileSearchPlus`), add a description, and click "Create repository".

**3. Initialize git in your project (if not already):**
```bash
cd /path/to/O2FileSearchPlus
git init
```

**4. Add all files to git:**
```bash
git add .
```

**5. Commit your changes:**
```bash
git commit -m "Initial commit: working O2FileSearchPlus"
```

**6. Add your GitHub repository as a remote:**
   - Replace `yourusername` with your GitHub username.
```bash
git remote add origin https://github.com/yourusername/O2FileSearchPlus.git
```

**7. Push your code to GitHub:**
```bash
git branch -M main
git push -u origin main
```

**8. Enter your GitHub username and password or token if prompted.**

**That's it! Your code is now on GitHub.**

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built upon the foundation of the original O2FileSearchPlus Streamlit applications
- Inspired by the need for better file search tools in Linux environments
- Uses modern web technologies for enhanced user experience
