import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, FileSpreadsheet, X, CheckCircle, AlertCircle, Loader, GitPullRequest } from 'lucide-react';
import axios from 'axios';

function BulkUpload() {
  const [file, setFile] = useState(null);
  const [processing, setProcessing] = useState(false);
  const [status, setStatus] = useState(null);
  const [results, setResults] = useState([]);

  const onDrop = useCallback((acceptedFiles) => {
    if (acceptedFiles.length > 0) {
      setFile(acceptedFiles[0]);
      setStatus(null);
      setResults([]);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/vnd.ms-excel': ['.xls'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'text/csv': ['.csv']
    },
    multiple: false
  });

  const removeFile = () => {
    setFile(null);
    setStatus(null);
    setResults([]);
  };

  const processFile = async () => {
    if (!file) return;

    setProcessing(true);
    setStatus({ type: 'info', message: 'Processing repositories...' });
    setResults([]);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post('/api/process-bulk', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      setResults(response.data.results || []);
      setStatus({
        type: 'success',
        message: `Successfully processed ${response.data.success_count || 0} repositories. ${response.data.pr_count || 0} PRs created.`
      });
    } catch (error) {
      setStatus({
        type: 'error',
        message: error.response?.data?.error || 'Failed to process file. Please try again.'
      });
    } finally {
      setProcessing(false);
    }
  };

  return (
    <div className="upload-section">
      {!file ? (
        <div {...getRootProps()} className={`dropzone ${isDragActive ? 'active' : ''}`}>
          <input {...getInputProps()} />
          <div className="dropzone-content">
            <Upload size={48} className="dropzone-icon" />
            <div className="dropzone-text">
              <h3>Drop your Excel/CSV file here</h3>
              <p>or click to browse (supports .xlsx, .xls, .csv)</p>
            </div>
          </div>
        </div>
      ) : (
        <div className="file-info">
          <div className="file-details">
            <FileSpreadsheet size={24} className="file-icon" />
            <span className="file-name">{file.name}</span>
          </div>
          <button onClick={removeFile} className="remove-file" disabled={processing}>
            <X size={20} />
          </button>
        </div>
      )}

      {file && (
        <button
          onClick={processFile}
          disabled={processing}
          className="process-button"
        >
          {processing ? (
            <>
              <div className="loading-spinner"></div>
              Processing...
            </>
          ) : (
            <>
              <GitPullRequest size={20} />
              Process & Create PRs
            </>
          )}
        </button>
      )}

      {status && (
        <div className={`status-message ${status.type}`}>
          {status.type === 'success' && <CheckCircle size={20} />}
          {status.type === 'error' && <AlertCircle size={20} />}
          {status.type === 'info' && <Loader size={20} />}
          <span>{status.message}</span>
        </div>
      )}

      {results.length > 0 && (
        <div className="repo-list">
          <h3 style={{ marginBottom: '1rem', color: '#333' }}>Processing Results:</h3>
          {results.map((result, index) => (
            <div key={index} className="repo-item">
              <div className="repo-name">{result.repo}</div>
              <div className="repo-status">
                {result.success ? (
                  <span style={{ color: '#059669' }}>✓ {result.message}</span>
                ) : (
                  <span style={{ color: '#dc2626' }}>✗ {result.error}</span>
                )}
              </div>
              {result.pr_url && (
                <a
                  href={result.pr_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ color: '#667eea', fontSize: '0.85rem', textDecoration: 'none' }}
                >
                  View PR →
                </a>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default BulkUpload;
