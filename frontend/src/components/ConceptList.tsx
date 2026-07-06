import React, { useEffect, useState } from 'react';
import { searchApi, Concept, ConceptDetail } from '../api/client';
import { CONCEPT_TYPES } from '../config/conceptTypes';

const ConceptList: React.FC = () => {
  const [concepts, setConcepts] = useState<Concept[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [selectedConcept, setSelectedConcept] = useState<string | null>(null);
  const [conceptBody, setConceptBody] = useState<string | null>(null);
  const [conceptMeta, setConceptMeta] = useState<Concept['metadata'] | null>(null);

  // Edit state
  const [isEditing, setIsEditing] = useState(false);
  const [editMeta, setEditMeta] = useState<Concept['metadata'] | null>(null);
  const [editBody, setEditBody] = useState('');

  // Delete state
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  const fetchConcepts = async () => {
    setLoading(true);
    try {
      const result = await searchApi.listConcepts({
        type: typeFilter || undefined,
        tag: filter || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        limit: 50,
      });
      // Sort by timestamp descending (newest first)
      const sorted = [...result.concepts].sort(
        (a, b) => new Date(b.metadata.timestamp).getTime() - new Date(a.metadata.timestamp).getTime()
      );
      setConcepts(sorted);
    } catch (err) {
      console.error('Грешка при зареждане на концепции:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchConcepts();
  }, [typeFilter, dateFrom, dateTo]);

  const openConcept = async (path: string) => {
    try {
      const detail = await searchApi.getConcept(path);
      setSelectedConcept(path);
      setConceptBody(detail.body);
      setConceptMeta(detail.metadata);
      setIsEditing(false);
      setConfirmDelete(false);
    } catch (err) {
      console.error('Грешка при отваряне на концепция:', err);
    }
  };

  const closeDetail = () => {
    setSelectedConcept(null);
    setConceptBody(null);
    setConceptMeta(null);
    setIsEditing(false);
    setConfirmDelete(false);
    setEditMeta(null);
    setEditBody('');
  };

  const startEditing = () => {
    if (!conceptMeta || conceptBody === null) return;
    setEditMeta({ ...conceptMeta });
    setEditBody(conceptBody);
    setIsEditing(true);
    setConfirmDelete(false);
  };

  const cancelEditing = () => {
    setIsEditing(false);
    setConfirmDelete(false);
    setEditMeta(null);
    setEditBody('');
  };

  const handleSave = async () => {
    if (!selectedConcept || !editMeta) return;
    setActionLoading(true);
    try {
      const result = await searchApi.updateConcept(selectedConcept, editMeta, editBody);
      if (result.status === 'ok') {
        // Update local state with saved data
        setConceptMeta(result.metadata);
        setConceptBody(result.body);
        setIsEditing(false);
        setEditMeta(null);
        setEditBody('');
        // Refresh the list
        await fetchConcepts();
      }
    } catch (err) {
      console.error('Грешка при запазване на концепция:', err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!selectedConcept) return;
    setActionLoading(true);
    try {
      const result = await searchApi.deleteConcept(selectedConcept);
      if (result.status === 'ok') {
        closeDetail();
        await fetchConcepts();
      }
    } catch (err) {
      console.error('Грешка при изтриване на концепция:', err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleEditMetaChange = (field: string, value: any) => {
    if (!editMeta) return;
    setEditMeta({ ...editMeta, [field]: value });
  };

  const handleEditTagsChange = (value: string) => {
    if (!editMeta) return;
    const tags = value.split(',').map(t => t.trim()).filter(t => t);
    setEditMeta({ ...editMeta, tags });
  };

  return (
    <div className="concept-list">
      <h3>📚 Концепции</h3>
      <div className="filters">
        <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
          <option value="">Всички типове</option>
          {CONCEPT_TYPES.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <input
          type="text"
          placeholder="Филтър по таг..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && fetchConcepts()}
        />
        <input
          type="date"
          value={dateFrom}
          onChange={(e) => setDateFrom(e.target.value)}
          title="От дата"
        />
        <input
          type="date"
          value={dateTo}
          onChange={(e) => setDateTo(e.target.value)}
          title="До дата"
        />
        <button onClick={fetchConcepts} disabled={loading}>
          {loading ? '⏳' : '🔄'}
        </button>
      </div>

      {loading ? (
        <div className="loading">Зареждане...</div>
      ) : concepts.length === 0 ? (
        <div className="empty">Все още няма концепции. Добави първата!</div>
      ) : (
        <div className="concepts-grid">
          {concepts.map((concept) => (
            <div
              key={concept.path}
              className={`concept-card ${selectedConcept === concept.path ? 'selected' : ''}`}
              onClick={() => openConcept(concept.path)}
            >
              <div className="concept-header">
                <span className={`concept-type type-${concept.metadata.type}`}>
                  {concept.metadata.type}
                </span>
                <span className="concept-date">
                  {new Date(concept.metadata.timestamp).toLocaleString('bg-BG')}
                </span>
              </div>
              <h4>{concept.metadata.title}</h4>
              <p>{concept.metadata.description}</p>
              <div className="concept-tags">
                {concept.metadata.tags.map((tag) => (
                  <span key={tag} className="tag">#{tag}</span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {conceptBody && conceptMeta && (
        <div className="concept-detail" onClick={closeDetail}>
          <div className="detail-content" onClick={(e) => e.stopPropagation()}>
            <button className="close-btn" onClick={closeDetail}>✕</button>

            {!isEditing ? (
              <>
                {/* View Mode */}
                <div className="detail-header">
                  <div className="detail-meta">
                    <span className={`concept-type type-${conceptMeta.type}`}>
                      {conceptMeta.type}
                    </span>
                    <span className="concept-date">
                      {new Date(conceptMeta.timestamp).toLocaleString('bg-BG')}
                    </span>
                  </div>
                  <h2>{conceptMeta.title}</h2>
                  {conceptMeta.description && (
                    <p className="detail-description">{conceptMeta.description}</p>
                  )}
                  <div className="concept-tags">
                    {conceptMeta.tags.map((tag) => (
                      <span key={tag} className="tag">#{tag}</span>
                    ))}
                  </div>
                </div>
                <hr className="detail-divider" />
                <pre className="detail-body">{conceptBody}</pre>
                <div className="detail-actions">
                  <button className="edit-btn" onClick={startEditing}>
                    ✏️ Редактирай
                  </button>
                  <button
                    className={`delete-btn ${confirmDelete ? 'confirm' : ''}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      if (confirmDelete) {
                        handleDelete();
                      } else {
                        setConfirmDelete(true);
                      }
                    }}
                    disabled={actionLoading}
                  >
                    {actionLoading ? '⏳' : confirmDelete ? '✅ Сигурен ли си?' : '🗑️ Изтрий'}
                  </button>
                  {confirmDelete && (
                    <button
                      className="cancel-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        setConfirmDelete(false);
                      }}
                    >
                      Отказ
                    </button>
                  )}
                </div>
              </>
            ) : (
              <>
                {/* Edit Mode */}
                <h2>✏️ Редактиране</h2>
                <div className="edit-form">
                  <label>
                    Тип:
                    <select
                      value={editMeta?.type || ''}
                      onChange={(e) => handleEditMetaChange('type', e.target.value)}
                    >
                      {CONCEPT_TYPES.map((t) => (
                        <option key={t} value={t}>{t}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Заглавие:
                    <input
                      type="text"
                      value={editMeta?.title || ''}
                      onChange={(e) => handleEditMetaChange('title', e.target.value)}
                    />
                  </label>
                  <label>
                    Описание:
                    <input
                      type="text"
                      value={editMeta?.description || ''}
                      onChange={(e) => handleEditMetaChange('description', e.target.value)}
                    />
                  </label>
                  <label>
                    Тагове (разделени със запетая):
                    <input
                      type="text"
                      value={editMeta?.tags?.join(', ') || ''}
                      onChange={(e) => handleEditTagsChange(e.target.value)}
                    />
                  </label>
                  <label>
                    Език:
                    <select
                      value={editMeta?.language || 'bg'}
                      onChange={(e) => handleEditMetaChange('language', e.target.value)}
                    >
                      <option value="bg">Български</option>
                      <option value="en">English</option>
                    </select>
                  </label>
                  <label>
                    Съдържание (Markdown):
                    <textarea
                      value={editBody}
                      onChange={(e) => setEditBody(e.target.value)}
                      rows={12}
                    />
                  </label>
                </div>
                <div className="edit-footer">
                  <div className="edit-timestamp">
                    {editMeta?.timestamp && (
                      <span>📅 {new Date(editMeta.timestamp).toLocaleString('bg-BG')}</span>
                    )}
                  </div>
                  <div className="detail-actions">
                    <button
                      className="save-btn"
                      onClick={handleSave}
                      disabled={actionLoading}
                    >
                      {actionLoading ? '⏳ Запазване...' : '💾 Запази'}
                    </button>
                    <button
                      className="cancel-btn"
                      onClick={cancelEditing}
                      disabled={actionLoading}
                    >
                      Отказ
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default ConceptList;