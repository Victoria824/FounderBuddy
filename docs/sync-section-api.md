# Section Sync API Documentation

## Overview

The Section Sync API allows you to synchronize LangGraph state with manually edited section content from the database. This is useful when users edit section content directly in the frontend, and you need to update the agent's structured state to reflect those changes.

## Problem Statement

In the Value Canvas agent:
- **Database stores**: Tiptap format (rich text JSON)
- **LangGraph state stores**: Structured Pydantic models (InterviewData, ICPData, etc.)

When users manually edit a section in the UI:
1. The edited content is saved to the database as Tiptap JSON
2. The LangGraph state becomes out of sync
3. The agent's structured data (canvas_data) doesn't reflect the user's changes

## Solution

The `/sync_section` endpoint uses an **LLM-based extraction** approach to:
1. Fetch the latest Tiptap content from the database
2. Convert Tiptap to plain text
3. Use LLM to extract structured data from the edited text
4. Update both `canvas_data` and `section_states` in LangGraph
5. Persist changes via checkpoint

## API Endpoint

### POST `/sync_section/{agent_id}/{section_id}`

Sync LangGraph state with manually edited section content.

#### Parameters

**Path Parameters:**
- `agent_id` (string): Agent identifier (currently only `"value-canvas"` is supported)
- `section_id` (string): Section identifier (e.g., `"interview"`, `"icp"`, `"pain"`)

**Query Parameters:**
- `user_id` (integer): User identifier
- `thread_id` (string): Thread/conversation identifier (required)

#### Request Example

```bash
curl -X POST "http://localhost:8080/sync_section/value-canvas/interview?user_id=1&thread_id=abc-123-def-456" \
  -H "Content-Type: application/json"
```

#### Response Example

**Success (200 OK):**
```json
{
  "success": true,
  "section_id": "interview",
  "user_id": 1,
  "thread_id": "abc-123-def-456",
  "extracted_fields": [
    "client_name",
    "company_name",
    "industry",
    "specialty",
    "career_highlight"
  ],
  "content_length": 342
}
```

**Error Responses:**

- **422 Unprocessable Entity**: Invalid parameters
```json
{
  "detail": "Missing required parameter: thread_id"
}
```

- **404 Not Found**: Agent not found
```json
{
  "detail": "Agent not found: invalid-agent"
}
```

- **500 Internal Server Error**: Sync failed
```json
{
  "detail": "Sync failed: DentApp API is not configured"
}
```

## Workflow

### User Editing Flow

1. **User edits section content** in the frontend UI
2. **Frontend saves** edited content to DentApp database (Tiptap format)
3. **Frontend calls** `/sync_section` API to trigger state synchronization
4. **Backend processes**:
   - Fetches latest content from database
   - Converts Tiptap → plain text
   - Uses LLM to extract structured data
   - Updates LangGraph state
   - Persists via checkpoint
5. **LangGraph state** is now synchronized with user's edits

### Frontend Integration Example

```javascript
// After user saves their edits to the database
async function handleSectionEdit(sectionId, userId, threadId) {
  try {
    // 1. Save edited content to database (your existing save logic)
    await saveSectionToDatabase(sectionId, editedContent);

    // 2. Trigger state sync
    const response = await fetch(
      `/sync_section/value-canvas/${sectionId}?user_id=${userId}&thread_id=${threadId}`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        }
      }
    );

    if (!response.ok) {
      throw new Error('Sync failed');
    }

    const result = await response.json();
    console.log('State synced successfully:', result.extracted_fields);

  } catch (error) {
    console.error('Failed to sync section:', error);
    // Handle error (show notification to user, etc.)
  }
}
```

## Supported Sections

The following sections are currently supported for sync:

| Section ID | Model Class | Description |
|-----------|-------------|-------------|
| `interview` | `InterviewData` | Initial interview information |
| `icp` | `ICPData` | Ideal Client Persona |
| `icp_stress_test` | `ICPData` | ICP Stress Test (saves to ICP) |
| `pain` | `PainData` | Pain points (3 pain points) |
| `deep_fear` | `DeepFearData` | Deep Fear analysis |
| `payoffs` | `PayoffsData` | Payoffs (3 payoffs) |
| `signature_method` | `SignatureMethodData` | Signature Method with principles |
| `mistakes` | `MistakesData` | Common mistakes |
| `prize` | `PrizeData` | Prize/transformation statement |

## Technical Details

### LLM Extraction Process

The sync process uses LangChain's **structured output** feature:

1. **Input**: Plain text from edited Tiptap content
2. **Prompt**: Extract structured data according to the section's Pydantic model
3. **Output**: Pydantic model instance with extracted fields

Example for Interview section:
```python
# Input text (from user's edit)
"John Smith (preferred: Johnny), CEO of TechCorp in the software industry..."

# Extracted data
InterviewData(
    client_name="John Smith",
    preferred_name="Johnny",
    company_name="TechCorp",
    industry="software",
    ...
)
```

### State Update Mechanism

The sync uses LangGraph's `aupdate_state()` method:

```python
await agent.aupdate_state(
    config=config,
    values={
        "canvas_data": updated_canvas_data_dict,
        "section_states": updated_section_states_dict
    }
)
```

This ensures:
- ✅ Atomic state update
- ✅ Checkpoint persistence
- ✅ Thread isolation (updates only affect the specified thread)

## Best Practices

### When to Call Sync API

✅ **DO call** `/sync_section` when:
- User manually edits section content in the UI
- User imports data from external source
- User uses a "quick edit" or "bulk edit" feature

❌ **DON'T call** `/sync_section` when:
- Agent is actively creating content (use normal chat flow)
- Content hasn't actually changed
- You're just reading section data (use `/invoke` or `/stream` instead)

### Error Handling

Always handle potential errors:
- **Network failures**: Retry with exponential backoff
- **Validation errors (422)**: Show user-friendly error message
- **Server errors (500)**: Log error and notify user

### Performance Considerations

- **LLM extraction** may take 2-5 seconds depending on content length
- Consider showing a loading indicator to users
- For batch edits, call sync once after all edits are complete (not after each field)

## Limitations

1. **Currently only supports `value-canvas` agent**
   - Other agents (mission-pitch, social-pitch, etc.) will return 422 error
   - Support for other agents can be added in the future

2. **Requires DentApp API to be enabled**
   - Check `USE_DENTAPP_API` setting
   - Ensure `DENTAPP_API_URL` is configured

3. **Thread ID is required**
   - Cannot sync without a valid thread_id
   - Edits must be associated with a conversation thread

## Future Enhancements

Potential improvements:
- [ ] Support for other agents (social-pitch, mission-pitch, etc.)
- [ ] Batch sync multiple sections at once
- [ ] Conflict resolution when both user and agent edit simultaneously
- [ ] Diff-based sync to show what changed
- [ ] Webhook notifications when sync completes

## Troubleshooting

### Common Issues

**Issue: "Missing required parameter: thread_id"**
- Solution: Ensure you're passing `thread_id` as a query parameter

**Issue: "Sync not yet supported for agent: X"**
- Solution: Currently only `value-canvas` is supported. Use `agent_id=value-canvas`

**Issue: "Section has no content to sync"**
- Solution: The section in the database is empty. User must save content first

**Issue: "DentApp API is not configured"**
- Solution: Check `.env` file has `USE_DENTAPP_API=true` and valid `DENTAPP_API_URL`

### Debug Logging

Enable debug logging to troubleshoot sync issues:

```bash
# In .env
LOG_LEVEL=DEBUG
```

Look for log entries with prefix:
- `SYNC_SECTION_REQUEST`: Initial sync request
- `SYNC_EXTRACT`: LLM extraction process
- `SYNC_SECTION_SUCCESS`: Successful sync completion
- `SYNC_SECTION_ERROR`: Sync failures

## See Also

- [Value Canvas Agent Documentation](../src/agents/value_canvas/docs/)
- [DentApp API Integration](../src/integrations/dentapp/)
- [LangGraph State Management](https://langchain-ai.github.io/langgraph/concepts/persistence/)
