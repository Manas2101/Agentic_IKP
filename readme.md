# HDPV2 Pipeline Automation UI

A modern web application for automating the adoption of HDPV2 pipeline files across multiple repositories.

## Features

### 🚀 Bulk Excel Upload
- Upload CSV/Excel files containing multiple repository configurations
- Process multiple repositories in one go
- Automatic PR creation for each repository
- Real-time processing status and results

### 📝 Form Builder
- Drag-and-drop interface for field selection
- All CSV fields available as draggable components
- Dynamic form creation with only the fields you need
- Single repository PR creation

## Project Structure

```
Agentic_IKP/
├── frontend/                 # React frontend application
│   ├── public/
│   ├── src/
│   │   ├── components/
│   │   │   ├── BulkUpload.js
│   │   │   └── FormBuilder.js
│   │   ├── App.js
│   │   ├── index.js
│   │   └── index.css
│   └── package.json
├── backend/                  # Flask backend API
│   ├── app.py
│   └── requirements.txt
├── Agentic-ikp.py           # Core automation script
├── info.csv                 # Sample CSV configuration
└── README.md
```

## Installation

### Prerequisites
- Python 3.8+
- Node.js 16+
- Git CLI
- GitHub CLI (`gh`) - for PR creation

### Backend Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the Flask server:
```bash
python app.py
```

The backend will start on `http://localhost:5000`

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm start
```

The frontend will start on `http://localhost:3000`

## Usage

### Bulk Upload Mode

1. Click on the "Bulk Excel Upload" tab
2. Drag and drop your CSV/Excel file or click to browse
3. Click "Process & Create PRs"
4. Monitor the progress and view results for each repository

### Form Builder Mode

1. Click on the "Form Builder" tab
2. Click on fields from the left panel to add them to your form
3. Drag fields to reorder them
4. Fill in the required information
5. Click "Create PR" to generate a pull request

## CSV Format

Your CSV file should contain the following columns (required fields marked with *):

- `repoUrl` * - Repository URL
- `branch` * - Target branch
- `appName` * - Application name
- `imageRepo` * - Image repository
- `base_image` * - Base Docker image
- `jar_file` * - JAR file name
- `namespace` - Kubernetes namespace
- `ownerEmail` - Owner email
- `lang` - Language (jvm/python)
- `expose_port` - Port to expose
- And many more optional fields...

See `info.csv` for a complete example.

## Technologies Used

### Frontend
- **React** - UI framework
- **@dnd-kit** - Drag and drop functionality
- **Lucide React** - Icon library
- **Axios** - HTTP client
- **React Dropzone** - File upload

### Backend
- **Flask** - Web framework
- **Flask-CORS** - Cross-origin resource sharing
- **Pandas** - Data processing
- **OpenPyXL** - Excel file handling

## API Endpoints

- `POST /api/process-bulk` - Process bulk CSV/Excel upload
- `POST /api/process-form` - Process single form submission
- `GET /api/health` - Health check endpoint

## Development

To run both frontend and backend simultaneously:

1. Terminal 1 (Backend):
```bash
cd backend
source venv/bin/activate
python app.py
```

2. Terminal 2 (Frontend):
```bash
cd frontend
npm start
```

## Building for Production

### Frontend
```bash
cd frontend
npm run build
```

The optimized production build will be in `frontend/build/`

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is internal to HSBC and follows company guidelines.

## Support

For issues or questions, please contact the development team.
