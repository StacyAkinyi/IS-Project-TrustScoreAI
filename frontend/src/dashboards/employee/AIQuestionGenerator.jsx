import React, { useState } from 'react';
import './AIQuestionGenerator.css';

export default function AIQuestionGenerator() {
  const [employeeId, setEmployeeId] = useState('101');
  const [loanVolumes, setLoanVolumes] = useState(45);
  const [accuracy, setAccuracy] = useState(98.5);
  const [workplan, setWorkplan] = useState(92.0);
  
  const [questions, setQuestions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleGenerate = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setQuestions([]);

    try {
      const response = await fetch(`http://127.0.0.1:8000/api/v1/employees/${employeeId}/generate-questions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          employee_id: parseInt(employeeId),
          loan_volumes: parseInt(loanVolumes),
          transaction_accuracy: parseFloat(accuracy),
          workplan_completion: parseFloat(workplan),
        }),
      });

      if (!response.ok) throw new Error('Failed to generate questions');
      const data = await response.json();
      
      // Split output text into 3 distinct array items (handling line breaks or numbers)
      const parsedQuestions = data.questions
        .split(/(?=\d+\.|\n)/)
        .map(q => q.trim())
        .filter(q => q.length > 5);

      setQuestions(parsedQuestions);
    } catch (err) {
      setError(err.message || 'Error generating questions');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="ai-container">
      <div className="ai-header">
        <span className="badge">AI-Powered</span>
        <h2>Employee Reflection Assistant</h2>
        <p>Generates 3 personalized appraisal reflection prompts based on metrics.</p>
      </div>

      <div className="ai-grid">
        {/* Left Form */}
        <form onSubmit={handleGenerate} className="metrics-card">
          <h3>Employee Performance Profile</h3>

          <div className="input-group">
            <label>Employee ID</label>
            <input 
              type="number" 
              value={employeeId} 
              onChange={(e) => setEmployeeId(e.target.value)} 
              required 
            />
          </div>

          <div className="input-group">
            <label>Loan Volumes Processed</label>
            <input 
              type="number" 
              value={loanVolumes} 
              onChange={(e) => setLoanVolumes(e.target.value)} 
              required 
            />
          </div>

          <div className="input-row">
            <div className="input-group">
              <label>Accuracy (%)</label>
              <input 
                type="number" 
                step="0.1" 
                value={accuracy} 
                onChange={(e) => setAccuracy(e.target.value)} 
                required 
              />
            </div>
            <div className="input-group">
              <label>Workplan Completion (%)</label>
              <input 
                type="number" 
                step="0.1" 
                value={workplan} 
                onChange={(e) => setWorkplan(e.target.value)} 
                required 
              />
            </div>
          </div>

          <button type="submit" className="btn-generate" disabled={loading}>
            {loading ? 'Analyzing Metrics...' : 'Generate 3 Reflection Questions ✨'}
          </button>
        </form>

        {/* Right Output: 3 Separate Question Cards */}
        <div className="output-card">
          <h3>Generated Reflection Prompts</h3>

          {error && <div className="error-box">{error}</div>}

          {questions.length === 0 && !loading && !error && (
            <div className="placeholder-box">
              <p>Adjust the metrics and submit to generate 3 employee-specific questions.</p>
            </div>
          )}

          {loading && (
            <div className="loading-box">
              <div className="pulse-circle"></div>
              <p>Crafting tailored questions for Employee #{employeeId}...</p>
            </div>
          )}

          {questions.length > 0 && !loading && (
            <div className="reflection-cards-list">
              {questions.map((q, index) => (
                <div key={index} className="reflection-card">
                  <span className="question-number">Prompt {index + 1}</span>
                  <p>{q.replace(/^\d+\.\s*/, '')}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}