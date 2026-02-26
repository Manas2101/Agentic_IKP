from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import csv
import tempfile
import subprocess
import shutil
from werkzeug.utils import secure_filename
import pandas as pd
import requests
import json
import re
import time
import urllib3

# Disable SSL warnings when using verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = tempfile.mkdtemp(prefix='hdpv2-uploads-')
ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def parse_github_url(repo_url):
    """Extract owner and repo name from GitHub URL"""
    parts = repo_url.rstrip('/').split('/')
    owner = parts[-2]
    repo = parts[-1].replace('.git', '')
    return owner, repo

def create_github_pr(repo_url, branch, new_branch, title, body):
    """Create a PR using GitHub API"""
    if not GITHUB_TOKEN:
        return {'success': False, 'error': 'GitHub token not configured'}
    
    owner, repo = parse_github_url(repo_url)
    
    # Determine GitHub API base URL (support enterprise GitHub)
    if 'github.com' in repo_url:
        api_base = 'https://api.github.com'
    else:
        # Extract domain for enterprise GitHub (e.g., alm-github.systems.uk.hsbc)
        domain_match = re.search(r'https?://([^/]+)', repo_url)
        if domain_match:
            domain = domain_match.group(1)
            api_base = f'https://{domain}/api/v3'
        else:
            api_base = 'https://api.github.com'
    
    api_url = f'{api_base}/repos/{owner}/{repo}/pulls'
    
    # Support both old (token) and new (Bearer) GitHub auth formats
    auth_header = f'Bearer {GITHUB_TOKEN}' if GITHUB_TOKEN.startswith(('ghp_', 'github_pat_')) else f'token {GITHUB_TOKEN}'
    
    headers = {
        'Authorization': auth_header,
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'hdpv2-automation-tool',
        'X-GitHub-Api-Version': '2022-11-28'
    }
    
    data = {
        'title': title,
        'body': body,
        'head': new_branch,
        'base': branch
    }
    
    try:
        response = requests.post(api_url, headers=headers, json=data, verify=False)
        if response.status_code == 201:
            pr_data = response.json()
            return {
                'success': True,
                'pr_url': pr_data.get('html_url'),
                'pr_number': pr_data.get('number')
            }
        else:
            return {
                'success': False,
                'error': f'GitHub API error: {response.status_code} - {response.text}'
            }
    except Exception as e:
        return {'success': False, 'error': str(e)}

def run_automation_script(csv_path, dry_run=False):
    # Backend is in agent-templates/Backend/, script is in agent-templates/
    backend_dir = os.path.dirname(os.path.abspath(__file__))  # .../Backend/
    agent_templates_dir = os.path.dirname(backend_dir)  # .../agent-templates/
    script_path = os.path.join(agent_templates_dir, 'agent-apply.py')
    
    # Check if script exists
    if not os.path.exists(script_path):
        return {
            'success': False,
            'error': f'Script not found at: {script_path}. Please ensure agent-apply.py exists in {agent_templates_dir}'
        }
    
    # Use 'python' on Windows, 'python3' on Unix
    python_cmd = 'python' if os.name == 'nt' else 'python3'
    
    cmd = [python_cmd, script_path, '--csv', csv_path]
    if dry_run:
        cmd.append('--dry-run')
    
    try:
        # Use Popen for better compatibility across Python versions
        # Don't set cwd - let the script handle its own directory resolution
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate(timeout=600)
        
        # Decode bytes to string
        stdout_str = stdout.decode('utf-8') if isinstance(stdout, bytes) else stdout
        stderr_str = stderr.decode('utf-8') if isinstance(stderr, bytes) else stderr
        
        return {
            'success': process.returncode == 0,
            'output': stdout_str,
            'error': stderr_str
        }
    except subprocess.TimeoutExpired:
        process.kill()
        return {
            'success': False,
            'error': 'Script execution timed out'
        }
    except FileNotFoundError as e:
        return {
            'success': False,
            'error': f'Python executable not found. Please ensure Python is installed and in PATH. Error: {str(e)}'
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Execution error: {str(e)}'
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
            # Wait a bit for GitHub to propagate the pushed branches
            time.sleep(3)
            
            for repo in repos:
                repo_url = repo.get('repoUrl', 'Unknown')
                app_name = repo.get('appName', 'Unknown')
                branch = repo.get('branch', 'main')
                new_branch = f'automation/hdpv2-templates/{app_name}'
                
                pr_result = create_github_pr(
                    repo_url=repo_url,
                    branch=branch,
                    new_branch=new_branch,
                    title=f'chore: add HDPV2/IKP templates for {app_name}',
                    body=f'Automated PR to add HDPV2 pipeline templates for {app_name}'
                )
                
                if pr_result['success']:
                    results.append({
                        'repo': f"{app_name} ({repo_url})",
                        'success': True,
                        'message': f'PR #{pr_result.get("pr_number")} created successfully',
                        'pr_url': pr_result.get('pr_url')
                    })
                    success_count += 1
                    pr_count += 1
                else:
                    results.append({
                        'repo': f"{app_name} ({repo_url})",
                        'success': False,
                        'error': pr_result.get('error', 'Failed to create PR')
                    })
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
            # Wait for GitHub to propagate the pushed branch
            time.sleep(3)
            
            app_name = data['appName']
            branch = data['branch']
            new_branch = f'automation/hdpv2-templates/{app_name}'
            
            pr_result = create_github_pr(
                repo_url=data['repoUrl'],
                branch=branch,
                new_branch=new_branch,
                title=f'chore: add HDPV2/IKP templates for {app_name}',
                body=f'Automated PR to add HDPV2 pipeline templates for {app_name}'
            )
            
            if pr_result['success']:
                return jsonify({
                    'message': f'Successfully created PR #{pr_result.get("pr_number")} for {app_name}',
                    'pr_url': pr_result.get('pr_url')
                }), 200
            else:
                return jsonify({
                    'error': pr_result.get('error', 'Failed to create PR')
                }), 500
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
