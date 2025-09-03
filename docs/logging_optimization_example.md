# Internal Data Extraction Stream Leak Fix Summary

## Problem
Internal LLM calls for structured data extraction were leaking their output to the user stream, causing field names and JSON data to briefly appear in the UI before disappearing.

## Root Cause
When the agent nodes called `structured_llm.ainvoke()` to extract structured data from conversation summaries, these internal LLM responses were being picked up by the streaming system and sent to users.

## Solution Implementation

### 1. Non-Streaming Configuration for Internal Calls
Added `RunnableConfig` with non-streaming flags and tags to all internal structured output calls:

#### memory_updater.py (lines 171-174)
```python
non_streaming_config = RunnableConfig(
    configurable={"stream": False},
    tags=["internal_extraction", "do_not_stream"]
)
extracted_data = await structured_llm.ainvoke(extraction_prompt, config=non_streaming_config)
```

#### generate_decision.py (lines 90-97)
```python
non_streaming_config = RunnableConfig(
    configurable={"stream": False},
    tags=["internal_decision", "do_not_stream"],
    callbacks=[]
)
decision = await structured_llm.ainvoke(decision_prompt, config=non_streaming_config)
```

#### social_pitch/agent.py (2 locations)
- Decision generation (lines 421-427)
- Data extraction (lines 708-715)

### 2. Comprehensive Field Name Filtering in service.py

#### Tuple Field Filtering (lines 456-492)
Filters out field names that might appear as tuples in the stream:
- Interview fields (client_name, company_name, etc.)
- ICP fields (icp_nickname, icp_role_identity, etc.)
- Pain fields (pain1_symptom, pain1_struggle, etc.)
- Deep Fear fields (deep_fear, golden_insight)
- Payoffs fields (payoff1_objective, payoff1_desire, etc.)
- Signature Method fields (method_name, sequenced_principles, etc.)
- Mistakes fields
- Prize fields
- Social Pitch fields (user_name, business_category, etc.)

#### AIMessage Content Filtering (lines 530-559)
Checks AIMessage content for extraction field names and skips messages containing them.

### 3. Tag-Based Message Filtering (lines 583-587)
Enhanced the messages stream mode to filter out messages with internal tags:
```python
tags = metadata.get("tags", [])
if any(tag in tags for tag in ["skip_stream", "internal_extraction", "do_not_stream", "internal_decision"]):
    logger.debug(f"Skipping message with internal tags: {tags}")
    continue
```

## Files Modified
1. `/src/agents/value_canvas/nodes/memory_updater.py` - Added non-streaming config with tags
2. `/src/agents/value_canvas/nodes/generate_decision.py` - Added non-streaming config with tags
3. `/src/agents/social_pitch/agent.py` - Added non-streaming config to 2 structured output calls
4. `/src/service/service.py` - Added comprehensive field filtering and tag-based filtering

## Testing Recommendations
1. Run a Value Canvas conversation through Interview, ICP, and Pain sections
2. Verify no field names appear in the user stream when the agent says "Ok before I add that into memory"
3. Check that conversation responses still work correctly
4. Verify data is still being saved to the database properly
5. Test Social Pitch agent similarly to ensure no extraction data leaks

## Result
Internal structured data extraction now happens silently in the background without leaking to the user stream, while preserving all normal agent functionality.