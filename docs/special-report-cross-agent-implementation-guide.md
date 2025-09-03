# Special Report Cross-Agent Implementation Guide

## Overview

The Special Report agent is designed as the **final synthesis step** that combines data from all previous agents to create a comprehensive business report. It requires completed data from multiple agents to function properly.

## Agent Dependencies

The Special Report agent depends on data from these agents in this order:

```
1. Value Canvas Agent (ID: 2/1) → Foundation business model
2. Social Pitch Agent (ID: 3) → Social media positioning  
3. Mission Pitch Agent (ID: 4) → Company mission and vision
4. Signature Pitch Agent (ID: 5) → Unique value proposition
5. Special Report Agent (ID: 6) → Final synthesis report
```

## Required Data Flow

### 1. Value Canvas Data (Foundation)
**Agent ID**: 2 (GSD) / 1 (DentApp AI Builder)
**Required Sections**:
- `icp` - Ideal Client Profile
- `pain` - Pain Points
- `prize` - Desired Outcome  
- `signature_method` - Unique Method
- `payoffs` - Benefits
- `deep_fear` - Core Fears
- `mistakes` - Common Mistakes

**Usage in Special Report**:
- Personalized headlines generation
- Target audience definition
- Problem/solution framework

### 2. Social Pitch Data (Positioning)
**Agent ID**: 3
**Required Sections**:
- `name` - Personal/Business Name
- `same` - What makes you similar
- `fame` - What makes you famous
- `sp_pain` - Social pitch pain point
- `aim` - What you're aiming for
- `game` - Your unique game/approach

**Usage in Special Report**:
- Author credibility section
- Social proof elements
- Market positioning context

### 3. Mission Pitch Data (Vision)
**Agent ID**: 4
**Required Sections**:
- `hidden_theme` - Underlying theme
- `personal_origin` - Personal story
- `business_origin` - Business origin story
- `mission` - Core mission
- `three_year_vision` - 3-year vision
- `big_vision` - Long-term vision
- `implementation` - Implementation strategy

**Usage in Special Report**:
- Executive summary
- Company background
- Future outlook sections

### 4. Signature Pitch Data (Value Prop)
**Agent ID**: 5
**Required Sections**:
- `active_change` - The change you create
- `specific_who` - Specific target audience
- `outcome_prize` - Specific outcome
- `core_credibility` - Core credibility
- `story_spark` - Origin story spark
- `signature_line` - Signature line

**Usage in Special Report**:
- Methodology sections
- Credibility building
- Call-to-action elements

## Implementation Strategy

### Phase 1: Agent Completion Validation

Before Special Report can work, implement validation:

```python
@tool
async def validate_prerequisites(
    user_id: int,
    thread_id: str
) -> dict[str, Any]:
    """Validate that all prerequisite agents have sufficient data."""
    
    prerequisites = {
        "value_canvas": {
            "agent_id": VALUE_CANVAS_AGENT_ID,
            "required_sections": ["icp", "pain", "prize", "signature_method"],
            "completion_score": 3  # Minimum score required
        },
        "social_pitch": {
            "agent_id": SOCIAL_PITCH_AGENT_ID, 
            "required_sections": ["name", "fame", "aim"],
            "completion_score": 3
        },
        "mission_pitch": {
            "agent_id": MISSION_PITCH_AGENT_ID,
            "required_sections": ["mission", "three_year_vision"],
            "completion_score": 3
        },
        "signature_pitch": {
            "agent_id": SIGNATURE_PITCH_AGENT_ID,
            "required_sections": ["active_change", "outcome_prize"],
            "completion_score": 3
        }
    }
    
    validation_results = {}
    
    for agent_name, config in prerequisites.items():
        agent_status = await check_agent_completion(
            user_id, 
            config["agent_id"], 
            config["required_sections"],
            config["completion_score"]
        )
        validation_results[agent_name] = agent_status
    
    return validation_results
```

### Phase 2: Cross-Agent Data Aggregation

Create a comprehensive data fetching system:

```python
@tool
async def get_all_agent_data(
    user_id: int,
    thread_id: str
) -> dict[str, Any]:
    """Fetch data from all prerequisite agents."""
    
    # Check prerequisites first
    validation = await validate_prerequisites(user_id, thread_id)
    
    if not all(v["ready"] for v in validation.values()):
        return {
            "ready": False,
            "missing_agents": [k for k, v in validation.items() if not v["ready"]],
            "validation_results": validation
        }
    
    # Fetch data from all agents
    aggregated_data = {
        "value_canvas": await fetch_agent_sections(user_id, VALUE_CANVAS_AGENT_ID, VC_SECTIONS),
        "social_pitch": await fetch_agent_sections(user_id, SOCIAL_PITCH_AGENT_ID, SP_SECTIONS), 
        "mission_pitch": await fetch_agent_sections(user_id, MISSION_PITCH_AGENT_ID, MP_SECTIONS),
        "signature_pitch": await fetch_agent_sections(user_id, SIGNATURE_PITCH_AGENT_ID, SIG_SECTIONS)
    }
    
    return {
        "ready": True,
        "data": aggregated_data,
        "validation_results": validation
    }
```

### Phase 3: Report Template System

Create modular report sections:

```python
def generate_report_sections(all_data: dict) -> dict[str, str]:
    """Generate all report sections from aggregated data."""
    
    vc_data = all_data["value_canvas"]
    sp_data = all_data["social_pitch"] 
    mp_data = all_data["mission_pitch"]
    sig_data = all_data["signature_pitch"]
    
    sections = {
        "executive_summary": generate_executive_summary(mp_data, sig_data),
        "market_analysis": generate_market_analysis(vc_data, sp_data),
        "methodology": generate_methodology(sig_data, vc_data),
        "implementation_plan": generate_implementation_plan(mp_data, vc_data),
        "author_credibility": generate_credibility_section(sp_data, sig_data),
        "call_to_action": generate_cta_section(vc_data, sig_data)
    }
    
    return sections
```

## User Experience Flow

### 1. Guided Agent Completion
```
User Journey:
1. Complete Value Canvas (foundation)
2. Complete Social Pitch (positioning)  
3. Complete Mission Pitch (vision)
4. Complete Signature Pitch (value prop)
5. Access Special Report (synthesis)
```

### 2. Progressive Unlocking
```python
async def check_special_report_access(user_id: int) -> dict:
    """Check if user can access Special Report."""
    
    completion_status = await get_agent_completion_status(user_id)
    
    required_agents = ["value_canvas", "social_pitch", "mission_pitch", "signature_pitch"]
    completed_agents = [agent for agent, status in completion_status.items() if status["complete"]]
    
    can_access = all(agent in completed_agents for agent in required_agents)
    
    if not can_access:
        missing = [agent for agent in required_agents if agent not in completed_agents]
        return {
            "can_access": False,
            "message": f"Complete these agents first: {', '.join(missing)}",
            "missing_agents": missing,
            "completion_percentage": len(completed_agents) / len(required_agents) * 100
        }
    
    return {"can_access": True, "message": "Ready to create your Special Report!"}
```

### 3. Dynamic Content Generation

Each Special Report section adapts based on available data:

```python
def generate_personalized_headlines(all_data: dict) -> str:
    """Generate headlines using data from multiple agents."""
    
    vc_data = all_data["value_canvas"]
    sp_data = all_data["social_pitch"]
    sig_data = all_data["signature_pitch"]
    
    headlines = []
    
    # Use Value Canvas for problem/solution headlines
    if vc_data.get("prize") and vc_data.get("icp"):
        headlines.extend(generate_prize_headlines(vc_data))
    
    # Use Social Pitch for credibility headlines  
    if sp_data.get("fame") and sp_data.get("name"):
        headlines.extend(generate_authority_headlines(sp_data))
    
    # Use Signature Pitch for method headlines
    if sig_data.get("active_change") and sig_data.get("outcome_prize"):
        headlines.extend(generate_method_headlines(sig_data))
    
    return format_headlines_list(headlines)
```

## Database Schema Requirements

### Agent Completion Tracking
```sql
CREATE TABLE agent_completion_status (
    user_id INT,
    agent_id INT,
    completion_percentage FLOAT,
    last_updated TIMESTAMP,
    is_complete BOOLEAN,
    minimum_score_met BOOLEAN
);
```

### Cross-Agent References
```sql
CREATE TABLE cross_agent_data (
    user_id INT,
    special_report_id INT,
    source_agent_id INT,
    source_section_id INT,
    data_snapshot TEXT,
    created_at TIMESTAMP
);
```

## Error Handling & Fallbacks

### 1. Missing Data Scenarios
```python
async def handle_incomplete_data(validation_results: dict) -> str:
    """Provide helpful guidance when data is missing."""
    
    missing_agents = [k for k, v in validation_results.items() if not v["ready"]]
    
    guidance_map = {
        "value_canvas": "Define your ideal client and core business model first",
        "social_pitch": "Create your social media positioning strategy", 
        "mission_pitch": "Establish your company mission and vision",
        "signature_pitch": "Develop your unique value proposition"
    }
    
    guidance = []
    for agent in missing_agents:
        guidance.append(f"📋 {guidance_map[agent]}")
    
    return f"""
    To create your Special Report, please complete these steps first:
    
    {chr(10).join(guidance)}
    
    Your progress: {len(validation_results) - len(missing_agents)}/4 agents complete
    """
```

### 2. Partial Data Generation
```python
def generate_partial_report(available_data: dict) -> dict:
    """Generate report sections with available data only."""
    
    sections = {}
    
    if "value_canvas" in available_data:
        sections["market_analysis"] = generate_market_analysis(available_data["value_canvas"])
    
    if "signature_pitch" in available_data:
        sections["methodology"] = generate_methodology(available_data["signature_pitch"])
    
    # Add placeholders for missing sections
    missing_sections = set(ALL_SECTIONS) - set(sections.keys())
    for section in missing_sections:
        sections[section] = f"[Complete {get_required_agent(section)} to generate this section]"
    
    return sections
```

## Testing Strategy

### 1. Sequential Agent Testing
```bash
# Test each agent in order
npm run test:value-canvas
npm run test:social-pitch  
npm run test:mission-pitch
npm run test:signature-pitch
npm run test:special-report
```

### 2. Integration Testing
```python
async def test_full_user_journey():
    """Test complete user journey through all agents."""
    
    test_user_id = create_test_user()
    
    # Complete each agent with test data
    await complete_value_canvas(test_user_id, TEST_VC_DATA)
    await complete_social_pitch(test_user_id, TEST_SP_DATA) 
    await complete_mission_pitch(test_user_id, TEST_MP_DATA)
    await complete_signature_pitch(test_user_id, TEST_SIG_DATA)
    
    # Generate special report
    report = await generate_special_report(test_user_id)
    
    # Validate all sections are populated
    assert all(section != "" for section in report.sections.values())
    assert "personalized headlines" in report.content
    assert test_user_id in report.metadata
```

## Deployment Checklist

- [ ] All 4 prerequisite agents are stable and save data correctly
- [ ] DentApp API endpoints work for all agent IDs
- [ ] Section ID mappings are correct for environment  
- [ ] Cross-agent data retrieval functions are implemented
- [ ] Validation logic prevents access without prerequisites
- [ ] Error messages guide users to complete missing agents
- [ ] Report generation handles partial/missing data gracefully
- [ ] User interface shows progress and requirements clearly

---

**Key Insight**: The Special Report agent is not a standalone feature—it's a synthesis tool that requires a complete ecosystem of other agents to function properly.