from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import csv
import tempfile
import subprocess
import shutil
from werkzeug.utils import secure_filename
import pandas as pd

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = tempfile.mkdtemp(prefix='hdpv2-uploads-')
ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def run_automation_script(csv_path, dry_run=False):
    script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'Agentic-ikp.py')
    
    cmd = ['python3', script_path, '--csv', csv_path]
    if dry_run:
        cmd.append('--dry-run')
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600
        )
        return {
            'success': result.returncode == 0,
            'output': result.stdout,
            'error': result.stderr
        }
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'error': 'Script execution timed out'
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

def process_csv_data(csv_path):
    results = []
    success_count = 0
    pr_count = 0
    
    try:
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            repos = list(reader)
        
        result = run_automation_script(csv_path)
        
        if result['success']:
            for repo in repos:
                repo_url = repo.get('repoUrl', 'Unknown')
                app_name = repo.get('appName', 'Unknown')
                
                results.append({
                    'repo': f"{app_name} ({repo_url})",
                    'success': True,
                    'message': 'PR created successfully',
                    'pr_url': None
                })
                success_count += 1
                pr_count += 1
        else:
            for repo in repos:
                repo_url = repo.get('repoUrl', 'Unknown')
                app_name = repo.get('appName', 'Unknown')
                
                results.append({
                    'repo': f"{app_name} ({repo_url})",
                    'success': False,
                    'error': result.get('error', 'Unknown error')
                })
        
        return {
            'results': results,
            'success_count': success_count,
            'pr_count': pr_count
        }
    
    except Exception as e:
        return {
            'results': [],
            'success_count': 0,
            'pr_count': 0,
            'error': str(e)
        }

@app.route('/api/process-bulk', methods=['POST'])
def process_bulk():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Please upload CSV or Excel file'}), 400
    
    try:
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        if filename.endswith('.xlsx') or filename.endswith('.xls'):
            df = pd.read_excel(file_path)
            csv_path = file_path.rsplit('.', 1)[0] + '.csv'
            df.to_csv(csv_path, index=False)
            file_path = csv_path
        
        result = process_csv_data(file_path)
        
        if 'error' in result:
            return jsonify({'error': result['error']}), 500
        
        return jsonify(result), 200
    
    except Exception as e:
        return jsonify({'error': f'Error processing file: {str(e)}'}), 500

@app.route('/api/process-form', methods=['POST'])
def process_form():
    try:
        data = request.json
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        required_fields = ['repoUrl', 'branch', 'appName', 'imageRepo', 'base_image', 'jar_file']
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            return jsonify({'error': f'Missing required fields: {", ".join(missing_fields)}'}), 400
        
        csv_path = os.path.join(app.config['UPLOAD_FOLDER'], 'form_data.csv')
        
        fieldnames = list(data.keys())
        with open(csv_path, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerow(data)
        
        result = run_automation_script(csv_path)
        
        if result['success']:
            return jsonify({
                'message': f'Successfully created PR for {data["appName"]}',
                'pr_url': None
            }), 200
        else:
            return jsonify({
                'error': result.get('error', 'Failed to create PR')
            }), 500
    
    except Exception as e:
        return jsonify({'error': f'Error processing form: {str(e)}'}), 500

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    app.run(debug=True, port=5000)
