import React, { useState } from 'react';
import { DndContext, closestCenter, KeyboardSensor, PointerSensor, useSensor, useSensors } from '@dnd-kit/core';
import { arrayMove, SortableContext, sortableKeyboardCoordinates, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { GripVertical, X, GitPullRequest, Trash2, CheckCircle, AlertCircle } from 'lucide-react';
import axios from 'axios';

const AVAILABLE_FIELDS = [
  { id: 'repoUrl', label: 'Repository URL', type: 'text', required: true },
  { id: 'branch', label: 'Branch', type: 'text', required: true },
  { id: 'appName', label: 'Application Name', type: 'text', required: true },
  { id: 'namespace', label: 'Namespace', type: 'text', required: false },
  { id: 'ownerEmail', label: 'Owner Email', type: 'email', required: false },
  { id: 'imageRepo', label: 'Image Repository', type: 'text', required: true },
  { id: 'lang', label: 'Language', type: 'select', options: ['jvm', 'python'], required: false },
  { id: 'skipLocalBuild', label: 'Skip Local Build', type: 'select', options: ['TRUE', 'FALSE'], required: false },
  { id: 'eim', label: 'EIM', type: 'text', required: false },
  { id: 'application_version', label: 'Application Version', type: 'text', required: false },
  { id: 'container_image_tag_default', label: 'Container Image Tag Default', type: 'text', required: false },
  { id: 'non_prod_env_default', label: 'Non-Prod Env Default', type: 'text', required: false },
  { id: 'snapshot_default', label: 'Snapshot Default', type: 'text', required: false },
  { id: 'cr_number_default', label: 'CR Number Default', type: 'text', required: false },
  { id: 'jdk_path', label: 'JDK Path', type: 'text', required: false },
  { id: 'maven_path', label: 'Maven Path', type: 'text', required: false },
  { id: 'jira_credential_id', label: 'JIRA Credential ID', type: 'text', required: false },
  { id: 'jira_host', label: 'JIRA Host', type: 'text', required: false },
  { id: 'build_enabled', label: 'Build Enabled', type: 'select', options: ['TRUE', 'FALSE'], required: false },
  { id: 'nexus_id', label: 'Nexus ID', type: 'text', required: false },
  { id: 'nexus_jenkins_cred', label: 'Nexus Jenkins Credential', type: 'text', required: false },
  { id: 'pom_path', label: 'POM Path', type: 'text', required: false },
  { id: 'maven_goal', label: 'Maven Goal', type: 'text', required: false },
  { id: 'container_build_type', label: 'Container Build Type', type: 'text', required: false },
  { id: 'registry_nexus', label: 'Registry Nexus', type: 'text', required: false },
  { id: 'dockerfile_location', label: 'Dockerfile Location', type: 'text', required: false },
  { id: 'application_image_name', label: 'Application Image Name', type: 'text', required: false },
  { id: 'tag_expr', label: 'Tag Expression', type: 'text', required: false },
  { id: 'docker_jenkins_cred', label: 'Docker Jenkins Credential', type: 'text', required: false },
  { id: 'iadp_enabled', label: 'IADP Enabled', type: 'select', options: ['TRUE', 'FALSE'], required: false },
  { id: 'iadp_contracts_path', label: 'IADP Contracts Path', type: 'text', required: false },
  { id: 'publish_to_any_enabled', label: 'Publish to Any Enabled', type: 'select', options: ['TRUE', 'FALSE'], required: false },
  { id: 'apix_enabled', label: 'APIX Enabled', type: 'select', options: ['TRUE', 'FALSE'], required: false },
  { id: 'g3_enabled', label: 'G3 Enabled', type: 'select', options: ['TRUE', 'FALSE'], required: false },
  { id: 'g3_project_area', label: 'G3 Project Area', type: 'text', required: false },
  { id: 'g3_application_name', label: 'G3 Application Name', type: 'text', required: false },
  { id: 'rwi_release_config_id', label: 'RWI Release Config ID', type: 'text', required: false },
  { id: 'base_image', label: 'Base Image', type: 'text', required: true },
  { id: 'jar_file', label: 'JAR File', type: 'text', required: true },
  { id: 'expose_port', label: 'Expose Port', type: 'text', required: false },
];

function SortableField({ field, onRemove, value, onChange }) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id: field.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <div ref={setNodeRef} style={style} className="form-field">
      <div className="form-field-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <div {...attributes} {...listeners} style={{ cursor: 'grab', display: 'flex', alignItems: 'center' }}>
            <GripVertical size={16} color="#9ca3af" />
          </div>
          <label className="form-field-label">
            {field.label} {field.required && <span style={{ color: '#dc2626' }}>*</span>}
          </label>
        </div>
        <button onClick={() => onRemove(field.id)} className="remove-field">
          <X size={16} />
        </button>
      </div>
      {field.type === 'select' ? (
        <select value={value || ''} onChange={(e) => onChange(field.id, e.target.value)}>
          <option value="">Select...</option>
          {field.options.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
      ) : (
        <input
          type={field.type}
          value={value || ''}
          onChange={(e) => onChange(field.id, e.target.value)}
          placeholder={`Enter ${field.label.toLowerCase()}`}
        />
      )}
    </div>
  );
}

function FormBuilder() {
  const [selectedFields, setSelectedFields] = useState([]);
  const [formData, setFormData] = useState({});
  const [status, setStatus] = useState(null);
  const [processing, setProcessing] = useState(false);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const addField = (field) => {
    if (!selectedFields.find((f) => f.id === field.id)) {
      setSelectedFields([...selectedFields, field]);
    }
  };

  const removeField = (fieldId) => {
    setSelectedFields(selectedFields.filter((f) => f.id !== fieldId));
    const newFormData = { ...formData };
    delete newFormData[fieldId];
    setFormData(newFormData);
  };

  const handleDragEnd = (event) => {
    const { active, over } = event;

    if (active.id !== over.id) {
      setSelectedFields((items) => {
        const oldIndex = items.findIndex((item) => item.id === active.id);
        const newIndex = items.findIndex((item) => item.id === over.id);
        return arrayMove(items, oldIndex, newIndex);
      });
    }
  };

  const handleFieldChange = (fieldId, value) => {
    setFormData({ ...formData, [fieldId]: value });
  };

  const clearForm = () => {
    setSelectedFields([]);
    setFormData({});
    setStatus(null);
  };

  const handleSubmit = async () => {
    const requiredFields = selectedFields.filter((f) => f.required);
    const missingFields = requiredFields.filter((f) => !formData[f.id]);

    if (missingFields.length > 0) {
      setStatus({
        type: 'error',
        message: `Please fill in required fields: ${missingFields.map((f) => f.label).join(', ')}`,
      });
      return;
    }

    setProcessing(true);
    setStatus({ type: 'info', message: 'Creating PR...' });

    try {
      const response = await axios.post('/api/process-form', formData);
      setStatus({
        type: 'success',
        message: response.data.message || 'PR created successfully!',
      });
      if (response.data.pr_url) {
        setTimeout(() => {
          window.open(response.data.pr_url, '_blank');
        }, 1000);
      }
    } catch (error) {
      setStatus({
        type: 'error',
        message: error.response?.data?.error || 'Failed to create PR. Please try again.',
      });
    } finally {
      setProcessing(false);
    }
  };

  return (
    <div className="form-builder">
      <div className="fields-panel">
        <h3>Available Fields</h3>
        {AVAILABLE_FIELDS.map((field) => (
          <div
            key={field.id}
            className="field-item"
            onClick={() => addField(field)}
            style={{
              opacity: selectedFields.find((f) => f.id === field.id) ? 0.5 : 1,
              cursor: selectedFields.find((f) => f.id === field.id) ? 'not-allowed' : 'pointer',
            }}
          >
            <GripVertical size={16} className="field-icon" />
            <span className="field-label">
              {field.label} {field.required && <span style={{ color: '#dc2626' }}>*</span>}
            </span>
          </div>
        ))}
      </div>

      <div className="form-canvas">
        <h3>Form Configuration</h3>
        {selectedFields.length === 0 ? (
          <div className="empty-canvas">
            <GripVertical size={48} className="empty-canvas-icon" />
            <p>Click on fields from the left panel to add them to your form</p>
          </div>
        ) : (
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
            <SortableContext items={selectedFields.map((f) => f.id)} strategy={verticalListSortingStrategy}>
              <div className="form-fields">
                {selectedFields.map((field) => (
                  <SortableField
                    key={field.id}
                    field={field}
                    onRemove={removeField}
                    value={formData[field.id]}
                    onChange={handleFieldChange}
                  />
                ))}
              </div>
            </SortableContext>
          </DndContext>
        )}

        {selectedFields.length > 0 && (
          <div className="form-actions">
            <button onClick={clearForm} className="clear-button" disabled={processing}>
              <Trash2 size={18} />
              Clear Form
            </button>
            <button onClick={handleSubmit} className="submit-button" disabled={processing}>
              {processing ? (
                <>
                  <div className="loading-spinner"></div>
                  Creating PR...
                </>
              ) : (
                <>
                  <GitPullRequest size={18} />
                  Create PR
                </>
              )}
            </button>
          </div>
        )}

        {status && (
          <div className={`status-message ${status.type}`}>
            {status.type === 'success' && <CheckCircle size={20} />}
            {status.type === 'error' && <AlertCircle size={20} />}
            <span>{status.message}</span>
          </div>
        )}
      </div>
    </div>
  );
}

export default FormBuilder;
