# Value Canvas Agent - API Documentation

This document provides comprehensive technical guidance for integrating with the `@value_canvas` agent, which is designed to guide users through the creation of a Value Canvas. The agent operates as a standalone service, communicating with the front-end via an HTTP API and interacting with application data through a dedicated back-end API. 

## Table of Contents
1.  **Interacting with the Agent: A Front-end Guide**
    *   [High-Level Conversational Flow](#high-level-conversational-flow)
    *   [API for Agent Interaction](#api-for-agent-interaction)
        *   [Core Interaction Pattern with IDs](#core-interaction-pattern-with-ids)
        *   [API Endpoints](#api-endpoints)
    *   [Agent-UI Collaboration: Database as the Single Source of Truth](#agent-ui-collaboration-database-as-the-single-source-of-truth)
    *   [Future Enhancement: Structured UI Interactions](#future-enhancement-structured-ui-interactions)
2.  **Agent's Internal Logic: Database Interaction**
    *   [Collaboration with the Backend Team](#collaboration-with-the-backend-team)
    *   [Database Operations for Data Interaction](#api-endpoints-for-database-interaction)
        *   [Key Identifiers (`user_id`, `doc_id`)](#key-identifiers-user_id-doc_id)
3.  **AI-Driven Dynamic Testing Framework**
    *   [Core Capabilities of the 'AI Examiner'](#core-capabilities-of-the-ai-examiner)
    *   [Traceable Test Reports](#traceable-test-reports)
    *   [Framework Value: Beyond the Ideal Scenario](#framework-value-beyond-the-ideal-scenario)
4.  **Appendix**
    *   [Understanding the Core Concepts: The Thread and `thread_id`](#appendix-understanding-the-core-concepts-the-thread-and-thread_id)

---

## 1. Interacting with the Agent: A Front-end Guide

This section provides a direct guide to building a user interface that communicates with the Value Canvas agent's back-end API.

### <a id="high-level-conversational-flow"></a>High-Level Conversational Flow

The agent guides the user through a structured, multi-step process to build their Value Canvas. The conversation is broken down into distinct sections:
1.  Initial Interview
2.  Ideal Customer Persona (ICP)
3.  The Pain (x3)
4.  The Deep Fear
5.  The Payoffs (x3)
6.  Signature Method
7.  The Mistakes
8.  The Prize

### <a id="api-for-agent-interaction"></a>API for Agent Interaction

The front-end interacts with this agent service via HTTP endpoints. The entire interaction pattern is built around the `user_id` and `thread_id`. For a conceptual understanding of how the agent manages conversations and threads, please refer to the [Appendix](#appendix-understanding-the-core-concepts-the-thread-and-thread_id).

#### <a id="core-interaction-pattern-with-ids"></a>Core Interaction Pattern with IDs
This is the fundamental lifecycle for handling  `user_id` and `thread_id` between the front-end and the various agent services:
1.  **Get it**: The front-end receives the `thread_id` from the API response after its first `invoke` call to the agent, which starts a new working session.
2.  **Store it**: The front-end should then save the new `thread_id` and associate it with the current user's project data in the database.
3.  **Use it**: For any subsequent message in a session, the front-end must include **both the `user_id` and the `thread_id`** when calling this agent service.

#### <a id="api-endpoints"></a>API Endpoints

**1. Getting a Single Response (`/value-canvas/invoke`)**

This endpoint handles both sending messages to an existing conversation and starting a new one. To start a new thread, send the first message with a `user_id` but **omit the `thread_id`**. The agent service will create a new thread and return its unique `thread_id` in the response. For all subsequent messages in that thread, include the `thread_id` you received.

-   **Endpoint**: `POST /value-canvas/invoke`
-   **Request Body (`UserInput`)**:
    ```json
    {
      "message": "I'm a consultant for tech startups.",
      "user_id": "some-unique-user-id",
      "thread_id": "optional-thread-uuid-for-an-existing-thread"
    }
    ```
-   **Success Response (200 OK) (`InvokeResponse`)**:
    ```json
    {
      "output": {
        "type": "ai",
        "content": "Hello! Let's begin by gathering some information for your Value Canvas. What's your full name, and what would you like me to call you during our conversation?",
        "tool_calls": [],
        "tool_call_id": null,
        "run_id": "c66481a3-c7d9-441e-9f96-8a522babf5ec",
        "response_metadata": {},
        "custom_data": {}
      },
      "thread_id": "15442997-03b4-40e3-b3f6-27bd41a10ab1",
      "user_id": "b6c48d70-c44f-446f-99e1-8423a7dbd7c2"
    }
    ```

**2. Streaming a Response (`/value-canvas/stream`)**

-   **Endpoint**: `POST /value-canvas/stream`
-   **Request Body (`StreamInput`)**: Same as `/value-canvas/invoke`.
-   **Success Response (200 OK)**: A stream of `text/event-stream` data.

**3. Retrieving a Specific Thread's History (`/history`)**

-   **Endpoint**: `POST /history`
-   **Request Body (`ChatHistoryInput`)**:
    ```json
    {
      "thread_id": "thread-uuid-1"
    }
    ```
-   **Success Response (200 OK) (`ChatHistory`)**:
    ```json
    {
      "messages": [
        { "type": "human", "content": "Hi!" },
        { "type": "ai", "content": "Hello! How can I help you?" }
      ]
    }
    ```

**4. Section State Notification (`/section_states/{agent_id}/{section_id}`)**

-   **Endpoint**: `GET /section_states/{agent_id}/{section_id}`
-   **Description**: Notify the agent that the specified section was updated and trigger a minimal sync run. Returns one AI message plus the latest section status and draft.

-   **Path Parameters**:
    -   `agent_id`: The agent identifier (e.g., `value-canvas`)
    -   `section_id`: The section identifier (e.g., `interview`)

-   **Query Parameters**:
    -   `user_id`: User identifier (required)
    -   `thread_id`: Thread identifier (required)
    
-   **Success Response (200 OK)**:
    ```json
    { "success": true }
    ```

### <a id="agent-ui-collaboration-database-as-the-single-source-of-truth"></a>Agent-UI Collaboration: Database as the Single Source of Truth

To ensure seamless collaboration between the user and the agent, the system employs a decoupled architecture where the database serves as the **single source of truth** for all generated content, especially for drafts displayed in a rich-text editor. This design avoids direct API calls from the agent to the front-end, leading to a more robust and scalable interaction model.

The collaboration workflow is as follows:

1.  **Agent Generates Content**: When the agent generates a draft or makes updates, it does **not** send this content directly back to the front-end via an API response. Instead, its sole action is to save the new data directly into the database using the backend APIs documented below (e.g., the save-section functionality).

2.  **Front-end Listens for Changes**: The front-end's responsibility is to actively monitor the database for any changes to the content. This can be achieved using real-time subscription services (e.g., Supabase Realtime, Laravel Broadcasting) or by polling relevant endpoints. When a change is detected, the front-end fetches the latest content and re-renders the rich-text editor to display it.

3.  **User Edits and Saves**: When the user edits the draft in the rich-text editor, their changes are saved back to the **same location in the database** via the application's backend. This ensures the database always holds the most current version of the content.

4.  **Agent Stays Synchronized**: Before performing its next action, the agent will read the latest state from the database using the backend APIs (e.g., the get-context functionality). This allows it to work with the user's most recent edits, ensuring both parties are always synchronized.

This database-centric approach guarantees data consistency and allows the front-end and the agent to operate independently, communicating asynchronously through the shared database state.

### <a id="future-enhancement-structured-ui-interactions"></a>Future Enhancement: Structured UI Interactions

While the current implementation relies on text-based `message` exchanges, the agent's underlying design document outlines a more advanced interaction model using structured UI components like buttons and predefined choices. This functionality is planned as a future, non-core enhancement.

The envisioned implementation will follow a front-end/agent contract:

1.  **Agent-side**: The agent will send a response in a specific, agreed-upon format (e.g., a JSON object within the `ChatMessage`'s `custom_data` field) that describes the UI elements to be displayed.
    ```json
    {
      "type": "ai",
      "content": "What's your name? Or should I just call you Master of the Universe?",
      "custom_data": {
        "ui_elements": [
          { "type": "button", "label": "Yes, that's right", "payload": "confirm_name" },
          { "type": "button", "label": "Needs correction", "payload": "correct_name" }
        ]
      }
    }
    ```

2.  **Front-end-side**: The front-end will be responsible for parsing this structured response and dynamically rendering the appropriate UI components (e.g., buttons). When a user clicks a button, the front-end will send the associated `payload` back to the agent as a standard `message` to continue the conversation.

This approach will allow for a richer, more guided user experience. However, for the initial version, all interactions are handled through the simple `message` field in the `UserInput` and `InvokeResponse` objects.

---

## 2. Agent's Internal Logic: Database Interaction

### <a id="collaboration-with-the-backend-team"></a>Collaboration with the Backend Team

To support the agent's functionality, the agent directly integrates with Supabase as the backend database. The agent uses internal database tools and functions to read and write user data, which allows direct database access while maintaining proper data structure and validation.

The collaboration involves the following areas:
1.  **Database Credentials for Conversation State**: To enable conversation persistence, the agent's environment requires Supabase connection variables (URL, API keys). The underlying `LangGraph` framework will automatically create and manage its own tables for thread history, so the provided credentials should have permissions for these operations.
2.  **Supabase Database Schema**: The agent requires specific database tables and functions to store and retrieve Value Canvas data. The database operations are handled internally by the agent through Supabase client libraries.


### <a id="api-endpoints-for-database-interaction"></a>Database Operations for Data Interaction

#### <a id="key-identifiers-user_id-doc_id"></a>Key Identifiers (`user_id`, `doc_id`)

To ensure data is correctly scoped, all API calls use two primary identifiers:

-   `user_id`: Identifies **who** is making the request. Crucial for authentication.
-   `doc_id`: The **unique key** to a specific document project. All of a document's configuration, sections, and content are tied to this ID in the database. The backend is responsible for managing all the business logic associated with this `doc_id`.

**Example:** A user (`user_id: "joe"`) might have multiple, distinct document projects:
-   A Value Canvas for a client: `doc_id: "doc_123"`
-   A Mission Pitch for another project: `doc_id: "doc_456"`

**1. Get Context for a Section**

-   **Description**: Retrieves all necessary data for the agent to work on a specific section of a document. The agent uses the Supabase database to fetch the correct set of prompts, rules, and existing draft content.
-   **Database Operation**: Supabase RPC call or table query via the agent's internal database tools

-   **Request Body Fields**:
    -   `user_id` (string, required): The user's unique identifier.
    -   `doc_id` (string, required): The unique identifier for the document project.
    -   `section_id` (string, required): The identifier for the specific section (e.g., "icp", "pain_1").
    -   `canvas_data` (object, optional): Key-value pairs of already completed sections' data. Used for personalizing prompts.

-   **Success Response (200 OK) Fields**:
    -   `section_id`, `status`, `system_prompt`, `validation_rules`, `required_fields`: Self-descriptive fields providing the agent with rules and instructions.
    -   `draft` (object | null): The user's previously saved work for this section.
        -   `draft.content` (object): A structured Tiptap JSON object for UI rendering.
        -   `draft.plain_text` (string): A plain text version for the agent's processing.


**2. Save Section Content**

-   **Description**: Saves the results of a specific section of a document.
-   **Database Operation**: Supabase table insert/update via the agent's internal database tools

-   **Request Body Fields**:
    -   `user_id`, `doc_id`, `section_id`: Identifiers for user, document, and section.
    -   `content` (object, required): The Tiptap JSON content to be saved.
    -   `score` (integer, optional): User-provided satisfaction score.
    -   `status` (string, required): New completion status (e.g., "done").

-   **Success Response (200 OK)**: Returns the complete, updated state of the section.


**3. Get All Sections Status**

-   **Description**: Retrieves a progress overview for a specific document.
-   **Database Operation**: Supabase table query via the agent's internal database tools

-   **Request Body Fields**:
    -   `user_id`, `doc_id`: Identifiers for the user and document.

-   **Success Response (200 OK)**: An array of objects, one for each section defined for that document.


**4. Export Value Canvas Data**

-   **Description**: Triggers the final export process for a completed document.
-   **Database Operation**: Supabase table query and data aggregation via the agent's internal database tools

-   **Request Body Fields**:
    -   `user_id`, `doc_id`: Identifiers for the user and document.
    -   `canvas_data` (object, required): A complete snapshot of all sections' data for generating the export.

-   **Success/Failure Responses**: As previously defined, indicating the result of the export process.


---
## <a id="ai-driven-dynamic-testing-framework"></a>AI-Driven Dynamic Testing Framework

To address the complexity and variability of real-world conversations, we employ a dynamic testing model based on an **'AI Examiner'** to complement the limitations of traditional, script-based testing in simulating authentic user interactions.

**Core Concept: Using one AI (the Examiner) to intelligently test our asset agents (e.g., the Value Canvas Agent).**

### <a id="core-capabilities-of-the-ai-examiner"></a>Core Capabilities of the 'AI Examiner'

Our specialized **AI Examiner** possesses the following key capabilities:

1.  **Rules Proficiency**: The Examiner is well-versed in the business agent's design documents and predefined instructions, serving as the gold standard for judging its compliance. For instance, it loads and comprehends the entire `value_canvas_agent_docs.md` file to master every ideal step of the process, from the initial interview to the final Value Canvas generation.
2.  **Realistic Simulation**: The Examiner is assigned a complete and consistent user persona, enabling it to engage in natural, logical conversations as a real client would.
3.  **Customized Edge Case Testing**: A key advantage of our framework is the ability to configure the AI Examiner to proactively simulate challenging scenarios. This tests the business agent's robustness against various edge cases.
4.  **Real-Time Evaluation**: In every turn of the conversation, the Examiner assesses the business agent's performance against the predefined workflow in real-time and logs any deviations.
   
### <a id="traceable-test-reports"></a>Traceable Test Reports

We believe in the value of transparency. Every dynamic test automatically generates a detailed, timestamped report in Markdown format. This report documents the **complete conversation** between the AI Examiner and the business agent, and includes a **flow compliance analysis** for each turn. Clients can review these reports at any time for a clear understanding of the agent's performance in various scenarios, ensuring the entire testing process is fully transparent and traceable.

You can view a sample test report here: [Sample Test Report Demo](https://hackmd.io/@QycwKnwqQoWdQHCbGzCSdg/rk4nHNr_xg).


### <a id="framework-value-beyond-the-ideal-scenario"></a>Framework Value: Beyond the Ideal Scenario

By simulating these complex, non-ideal scenarios, we can thoroughly inspect the business agent's **robustness** and **fault tolerance**. This ensures our AI not only excels in the 'happy path' but can also gracefully handle real-world unpredictability, delivering a truly reliable and intelligent service.

Furthermore, this process creates an invaluable feedback loop for prompt engineering. By analyzing the detailed logs where the agent deviates or fails, we can make precise, data-driven adjustments to its underlying prompts. This allows us to systematically refine the agent's performance, ensuring continuous improvement and alignment with business goals.


---
## Appendix

### <a id="appendix-understanding-the-core-concepts-the-thread-and-thread_id"></a>Understanding the Core Concepts: The Thread and `thread_id`

*   **What a Thread Is**: A Thread is the complete record of one working session to create a Value Canvas. It's not the final project file itself, but rather the **entire conversation history and the agent's internal state** (like its memory and progress) throughout that creation process. Each Thread is identified by a unique `thread_id`.

*   **`user_id` vs. `thread_id`**: It's crucial to understand the role of both identifiers.
    *   The `thread_id` identifies **which specific working session** to load.
    *   The `user_id` identifies **who is making the request**.
    *   The back-end uses the `user_id` for **security and authorization**, ensuring that a user can only access their own threads. Therefore, both identifiers are required in most API calls.

*   **Benefits of Multiple Threads for a User**: The system is designed for a user to have many threads. This is powerful because it allows them to:
    *   **Manage different projects**: Create separate Value Canvasses for different products or clients. Each project is a unique thread.
    *   **Restart without losing history**: Start a new thread to begin a project from scratch, while the old thread is preserved as a record.
