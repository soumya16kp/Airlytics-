import React, { useEffect, useState } from 'react';

const STATUS_COLORS = {
  Excellent: '#059669', Good: '#10b981', Moderate: '#f59e0b', Poor: '#f97316', Hazardous: '#ef4444'
};

const getRiskLevel = (statusLabel, group) => {
  const matrix = {
    Excellent: { children: 'None', elderly: 'None', adults: 'None', respiratory: 'None' },
    Good: { children: 'None', elderly: 'None', adults: 'None', respiratory: 'Low' },
    Moderate: { children: 'Low', elderly: 'Low', adults: 'None', respiratory: 'Moderate' },
    Poor: { children: 'Moderate', elderly: 'High', adults: 'Low', respiratory: 'High' },
    Hazardous: { children: 'High', elderly: 'High', adults: 'High', respiratory: 'Critical' }
  };
  return matrix[statusLabel]?.[group] || 'Unknown';
};

const getOutdoorAdvice = (statusLabel) => {
  const matrix = {
    Excellent: { text: '✅ SAFE FOR ALL OUTDOOR EXERCISE', color: '#10b981' },
    Good: { text: '✅ OUTDOOR ACTIVITIES RECOMMENDED', color: '#10b981' },
    Moderate: { text: '⚠️ REDUCE STRENUOUS ACTIVITY', color: '#f59e0b' },
    Poor: { text: '🚫 AVOID OUTDOOR EXPOSURE', color: '#f97316' },
    Hazardous: { text: '🚨 STAY INDOORS IMMEDIATELY', color: '#ef4444' }
  };
  return matrix[statusLabel] || matrix['Moderate'];
};

export default function AiReport({ aiInsight, currentValue, whoStatus, whoLimit = 1.0, pollutantType }) {
  const [progress, setProgress] = useState(0);
  
  // Safe limits fallback (ideally from props/config)
  const ratio = Math.min((currentValue / whoLimit) * 100, 100);
  const ratioMultiplier = (currentValue / whoLimit).toFixed(1);

  const statusColor = STATUS_COLORS[whoStatus?.label] || '#64748b';
  const outdoor = getOutdoorAdvice(whoStatus?.label);

  // Section 1 Entrance Animation
  useEffect(() => {
    const timer = setTimeout(() => setProgress(ratio), 100);
    return () => clearTimeout(timer);
  }, [ratio]);

  // Edge case: String response fallback
  if (typeof aiInsight === 'string') {
    return (
      <div className="ai-report-container ai-hero-enter">
        <div style={{ color: '#334155', lineHeight: 1.7 }}>{aiInsight}</div>
      </div>
    );
  }

  const summary = aiInsight?.summary || aiInsight?.short_term_effects || "Analysis partially unavailable.";

  return (
    <div className="ai-report-container">
      
      {/* SECTION 1: Overall Status (Hero) */}
      <div className="ai-section ai-hero-enter">
        <div style={{ textAlign: 'center', marginBottom: '24px' }}>
          <div style={{
            display: 'inline-block',
            borderRadius: '100px',
            padding: '12px 40px',
            fontSize: '28px',
            fontWeight: 900,
            color: statusColor,
            background: `${statusColor}26`, // 15% opacity hex
            border: `2px solid ${statusColor}4D`, // 30% opacity hex
            textTransform: 'uppercase'
          }}>
            {whoStatus?.label || 'Unknown'}
          </div>
          
          <div style={{ marginTop: '16px', fontSize: '15px', fontWeight: 600 }}>
            {pollutantType} is at {ratioMultiplier}× the WHO safe limit
          </div>

          {/* WHO Progress Bar */}
          <div style={{ position: 'relative', marginTop: '12px', height: '8px', background: '#e2e8f0', borderRadius: '4px', overflow: 'hidden' }}>
            <div style={{ 
              width: `${progress}%`, height: '100%', background: ratio >= 100 ? '#ef4444' : statusColor,
              transition: 'width 0.8s cubic-bezier(0.16, 1, 0.3, 1)' 
            }} />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginTop: '4px', color: 'var(--text-muted)' }}>
            <span>0</span>
            <span style={{ position: 'absolute', left: `${progress}%`, transform: 'translateX(-50%)' }}>▲ WHO Limit</span>
          </div>
        </div>
      </div>

      {/* SECTION 2: Summary */}
      {summary && (
        <div className="ai-section ai-section-enter" style={{ animationDelay: '80ms' }}>
          <h5 style={{ fontSize: '13px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted)', marginBottom: '8px' }}>📋 Summary</h5>
          <div style={{ fontSize: '15px', lineHeight: 1.7, color: '#334155' }}>{summary}</div>
        </div>
      )}

      {/* SECTION 3: Health Effects */}
      <div className="ai-section ai-section-enter" style={{ animationDelay: '160ms' }}>
        <h5 style={{ fontSize: '13px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted)', marginBottom: '16px' }}>🫀 Health Effects</h5>
        
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
          {[
            { icon: '👧', name: 'Children', risk: getRiskLevel(whoStatus?.label, 'children') },
            { icon: '👴', name: 'Elderly', risk: getRiskLevel(whoStatus?.label, 'elderly') },
            { icon: '🏃', name: 'Adults', risk: getRiskLevel(whoStatus?.label, 'adults') },
            { icon: '🫁', name: 'Respiratory', risk: getRiskLevel(whoStatus?.label, 'respiratory') }
          ].map((group, i) => (
            <div key={i} style={{ padding: '16px', borderRadius: '16px', border: '1px solid var(--border-subtle)', background: '#fff', display: 'flex', alignItems: 'center', gap: '12px' }}>
              <span style={{ fontSize: '24px' }}>{group.icon}</span>
              <div>
                <div style={{ fontSize: '12px', fontWeight: 700, textTransform: 'uppercase' }}>{group.name}</div>
                <div style={{ fontSize: '11px', color: group.risk === 'None' ? '#10b981' : (group.risk.includes('High') || group.risk === 'Critical' ? '#ef4444' : '#f59e0b') }}>{group.risk} Risk</div>
              </div>
            </div>
          ))}
        </div>

        <div style={{ fontSize: '14px', lineHeight: 1.6, color: '#334155' }}>
          {aiInsight?.short_term_effects && <div style={{ marginBottom: '8px' }}><b style={{ color: 'var(--warning)' }}>Short-term:</b> {aiInsight.short_term_effects}</div>}
          {aiInsight?.long_term_effects && <div><b style={{ color: 'var(--error)' }}>Long-term:</b> {aiInsight.long_term_effects}</div>}
        </div>
      </div>

      {/* SECTION 4: Precautions */}
      {aiInsight?.action_plan?.length > 0 && (
        <div className="ai-section ai-section-enter" style={{ animationDelay: '240ms' }}>
          <h5 style={{ fontSize: '13px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted)', marginBottom: '16px' }}>🛡 Recommended Precautions</h5>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {aiInsight.action_plan.map((action, i) => {
              // Extract title (first few words) if structured loosely
              const words = action.split(' ');
              const title = words.slice(0, 3).join(' ');
              const desc = words.slice(3).join(' ');

              return (
                <div key={i} style={{ display: 'flex', gap: '12px' }}>
                  <div style={{ width: '40px', height: '40px', borderRadius: '50%', background: `${statusColor}1A`, color: statusColor, display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, flexShrink: 0 }}>{i + 1}</div>
                  <div>
                    <div style={{ fontSize: '14px', fontWeight: 700 }}>{title}</div>
                    <div style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: 1.5 }}>{desc || action}</div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* SECTION 5: Outdoor Advice */}
      <div className="ai-section ai-section-enter" style={{ animationDelay: '320ms' }}>
        <h5 style={{ fontSize: '13px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted)', marginBottom: '16px' }}>🏃 Outdoor Activity</h5>
        <div style={{
          background: `${outdoor.color}1A`,
          borderLeft: `4px solid ${outdoor.color}`,
          borderRadius: '0 12px 12px 0',
          padding: '16px 20px',
          fontWeight: 800,
          color: outdoor.color
        }}>
          {outdoor.text}
        </div>
      </div>

      {/* SECTION 6: Sensitive Groups */}
      {aiInsight?.vulnerable_groups && (
        <div className="ai-section ai-section-enter" style={{ animationDelay: '400ms' }}>
          <h5 style={{ fontSize: '13px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted)', marginBottom: '16px' }}>⚠️ Sensitive Groups</h5>
          <div style={{ background: 'rgba(245, 158, 11, 0.05)', borderLeft: '4px solid var(--warning)', borderRadius: '0 12px 12px 0', padding: '16px 20px', fontSize: '14px', lineHeight: 1.6, color: '#475569' }}>
            {aiInsight.vulnerable_groups}
          </div>
        </div>
      )}

      {/* SECTION 7: Scientific Facts */}
      {aiInsight?.scientific_fact && (
        <div className="ai-section ai-section-enter" style={{ animationDelay: '480ms' }}>
          <h5 style={{ fontSize: '13px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted)', marginBottom: '16px' }}>💡 Pollution Insights</h5>
          <div style={{ border: '1px dashed #cbd5e1', background: '#f8fafc', borderRadius: '10px', padding: '12px 16px', fontStyle: 'italic', fontSize: '14px', color: '#475569' }}>
            📊 {aiInsight.scientific_fact}
          </div>
        </div>
      )}

      {/* SECTION 8: Environment */}
      {aiInsight?.environmental_impact && (
        <div className="ai-section ai-section-enter" style={{ animationDelay: '560ms' }}>
          <h5 style={{ fontSize: '13px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted)', marginBottom: '16px' }}>🌿 Environmental Awareness</h5>
          <div style={{ background: 'rgba(16, 185, 129, 0.05)', borderLeft: '4px solid #10b981', borderRadius: '0 12px 12px 0', padding: '16px 20px', fontSize: '14px', lineHeight: 1.6, color: '#475569' }}>
            {aiInsight.environmental_impact}
          </div>
        </div>
      )}

    </div>
  );
}
