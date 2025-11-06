'use client';

interface Section {
  database_id: number;
  name: string;
  status: string;
}

interface ProgressSidebarProps {
  currentSection: Section | null;
  selectedAgent: string;
}

// Define all sections for founder-buddy
const FOUNDER_BUDDY_SECTIONS = [
  { id: 'mission', name: 'Mission', displayName: 'Mission' },
  { id: 'idea', name: 'Idea', displayName: 'Idea' },
  { id: 'team_traction', name: 'Team & Traction', displayName: 'Team & Traction' },
  { id: 'invest_plan', name: 'Investment Plan', displayName: 'Investment Plan' }
];

export default function ProgressSidebar({ currentSection, selectedAgent }: ProgressSidebarProps) {

  // Get status for a section
  const getSectionStatus = (sectionId: string): 'pending' | 'in_progress' | 'completed' => {
    if (!currentSection) return 'pending';
    
    // Match by section name (case-insensitive)
    const currentSectionName = currentSection.name.toLowerCase();
    const sectionName = sectionId.toLowerCase();
    
    // Check if this is the current section
    if (currentSectionName.includes(sectionName) || sectionName.includes(currentSectionName)) {
      if (currentSection.status === 'completed' || currentSection.status === 'done') {
        return 'completed';
      }
      return 'in_progress';
    }
    
    // Check if sections before this one are completed
    const currentIndex = FOUNDER_BUDDY_SECTIONS.findIndex(s => 
      currentSectionName.includes(s.id) || currentSectionName.includes(s.name.toLowerCase())
    );
    const sectionIndex = FOUNDER_BUDDY_SECTIONS.findIndex(s => s.id === sectionId);
    
    if (currentIndex > sectionIndex) {
      return 'completed';
    }
    
    return 'pending';
  };

  const getStatusColor = (status: 'pending' | 'in_progress' | 'completed') => {
    switch (status) {
      case 'completed':
        return '#10b981'; // green
      case 'in_progress':
        return '#6366f1'; // purple
      default:
        return '#94a3b8'; // gray
    }
  };

  const getStatusText = (status: 'pending' | 'in_progress' | 'completed') => {
    switch (status) {
      case 'completed':
        return 'Done';
      case 'in_progress':
        return 'In Progress';
      default:
        return 'Pending';
    }
  };

  // For founder-buddy, show vertical list of all sections
  if (selectedAgent === 'founder-buddy') {
    return (
      <div style={{
        width: '100%',
        display: 'flex',
        flexDirection: 'column',
        gap: '8px'
      }}>
        <div style={{
          fontSize: '14px',
          fontWeight: '700',
          color: '#1e293b',
          marginBottom: '4px',
          padding: '0 4px'
        }}>
          Progress
        </div>
        {FOUNDER_BUDDY_SECTIONS.map((section, index) => {
          const status = getSectionStatus(section.id);
          const isCurrent = currentSection && (
            currentSection.name.toLowerCase().includes(section.id) ||
            currentSection.name.toLowerCase().includes(section.name.toLowerCase())
          );

          return (
            <div
              key={section.id}
              style={{
                padding: '14px 16px',
                backgroundColor: isCurrent ? '#f0f9ff' : '#ffffff',
                border: isCurrent ? '2px solid #6366f1' : '1px solid #e2e8f0',
                borderRadius: '8px',
                display: 'flex',
                flexDirection: 'column',
                gap: '6px',
                transition: 'all 0.2s ease',
                boxShadow: isCurrent ? '0 2px 8px rgba(99, 102, 241, 0.15)' : 'none',
                transform: isCurrent ? 'scale(1.02)' : 'scale(1)'
              }}
            >
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '12px'
              }}>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  flex: 1
                }}>
                  <div style={{
                    width: '10px',
                    height: '10px',
                    borderRadius: '50%',
                    backgroundColor: getStatusColor(status),
                    flexShrink: 0,
                    boxShadow: isCurrent ? `0 0 8px ${getStatusColor(status)}` : 'none'
                  }}></div>
                  <span style={{
                    fontSize: '14px',
                    fontWeight: isCurrent ? '700' : '600',
                    color: isCurrent ? '#6366f1' : '#1e293b',
                    letterSpacing: '-0.01em'
                  }}>
                    {section.displayName}
                  </span>
                </div>
                <span style={{
                  fontSize: '11px',
                  color: getStatusColor(status),
                  fontWeight: '600',
                  padding: '2px 8px',
                  backgroundColor: status === 'completed' ? '#d1fae5' : 
                                 status === 'in_progress' ? '#e0e7ff' : '#f1f5f9',
                  borderRadius: '12px',
                  whiteSpace: 'nowrap'
                }}>
                  {getStatusText(status)}
                </span>
              </div>
              {isCurrent && currentSection && (
                <div style={{
                  fontSize: '11px',
                  color: '#64748b',
                  marginTop: '2px',
                  paddingLeft: '20px',
                  fontStyle: 'italic'
                }}>
                  Currently working on this section
                </div>
              )}
            </div>
          );
        })}
      </div>
    );
  }

  // For other agents, show simple display
  return (
    <div style={{
      display: 'flex',
      gap: '12px',
      alignItems: 'center'
    }}>
      {currentSection ? (
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <div style={{
            padding: '6px 12px',
            backgroundColor: '#f8fafc',
            borderRadius: '6px',
            border: '1px solid #e2e8f0',
            fontSize: '12px',
            color: '#1e293b',
            fontWeight: '500'
          }}>
            #{currentSection.database_id}
          </div>
          <div style={{
            padding: '6px 12px',
            backgroundColor: '#f8fafc',
            borderRadius: '6px',
            border: '1px solid #e2e8f0',
            fontSize: '12px',
            color: '#1e293b',
            fontWeight: '500'
          }}>
            {currentSection.name}
          </div>
        </div>
      ) : (
        <div style={{
          fontSize: '12px',
          color: '#94a3b8',
          fontStyle: 'italic'
        }}>
          Start a conversation to see progress
        </div>
      )}
    </div>
  );
}