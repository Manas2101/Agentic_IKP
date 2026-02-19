import React, { useState } from 'react';
import { Upload, FormInput } from 'lucide-react';
import BulkUpload from './components/BulkUpload';
import FormBuilder from './components/FormBuilder';

function App() {
  const [activeTab, setActiveTab] = useState('bulk');

  return (
    <div className="app-container">
      <header className="header">
        <h1>HDPV2 Pipeline Automation</h1>
        <p>Automate adoption of HDPV2 pipeline files across repositories</p>
      </header>

      <div className="tabs">
        <button
          className={`tab-button ${activeTab === 'bulk' ? 'active' : ''}`}
          onClick={() => setActiveTab('bulk')}
        >
          <Upload size={20} />
          Bulk Excel Upload
        </button>
        <button
          className={`tab-button ${activeTab === 'form' ? 'active' : ''}`}
          onClick={() => setActiveTab('form')}
        >
          <FormInput size={20} />
          Form Builder
        </button>
      </div>

      <div className="content-card">
        {activeTab === 'bulk' ? <BulkUpload /> : <FormBuilder />}
      </div>
    </div>
  );
}

export default App;
