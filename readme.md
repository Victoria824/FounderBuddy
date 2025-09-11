# Dent AI Agent Service

AI-powered conversational agent service built with LangGraph and FastAPI, helping users create powerful business marketing frameworks through structured dialogue.

## 🚀 Quick Start

### Install Dependencies

```bash
# Requires Python 3.11+ and UV package manager
uv sync
```

### Run Service

Configure `.env` file with required API keys and settings, then:

```bash
uv run python src/run_service.py
```

Visit https://docs.google.com/document/d/1VSSQNFfUVMR6bjdUSaBWqrPI74aCCHMFwDAMnOTycrI/edit?tab=t.0#heading=h.wu3vaz3k8s22 for API documentation

## 🏗️ Architecture Overview

### Tech Stack
- **Web Framework**: FastAPI - High-performance async web framework
- **Agent Orchestration**: LangGraph - State graph-driven agent flow control with built-in thread management
- **LLM Framework**: LangChain - Unified LLM interface abstraction

### Agent Architecture

All 5 agents in the project share the same LangGraph StateGraph architecture with multi-node design for clear separation of concerns:

```
START → initialize → router → generate_reply → generate_decision → memory_updater → router (loop)
                        ↓
                  implementation → END
```

**Core Nodes**:
- `initialize`: Sets up conversation state and validates required fields
- `router`: Manages section transitions and loads context for each section
- `generate_reply`: Creates conversational responses with streaming support
- `generate_decision`: Analyzes conversation and determines next actions
- `memory_updater`: Saves user data via DentApp API and updates conversation memory
- `implementation`: Generates final checklist when all sections are complete

> Note: While all agents share this architecture, Value Canvas uses a modular file structure that other agents are being migrated to.

## 📡 API Endpoints

### Core Endpoints

- `POST /invoke` or `/{agent_id}/invoke` - Synchronous agent invocation
- `POST /stream` or `/{agent_id}/stream` - Streaming response (SSE)
- `POST /history` - Get conversation history
- `POST /feedback` - Submit user feedback

### Service Endpoints

- `GET /info` - Get service info and available agents
- `GET /health` - Health check


## 🧪 Testing

This project utilizes a multi-faceted approach to testing, including end-to-end (E2E) tests and a dedicated frontend for interactive testing.

### Interactive Testing

A dedicated web frontend is available for quick, interactive testing of agent configurations and conversations.

- **URL**: [https://dent-langgraph-frontend.vercel.app/](https://dent-langgraph-frontend.vercel.app/)

### End-to-End (E2E) Testing

Our E2E tests are managed using Cypress within the frontend project. These tests simulate a full conversation by using an LLM with a predefined persona to interact with the agent.

- **Watch a Demo**: [E2E Test Demo Video](https://www.loom.com/share/a3787c75471c49eeb625a61c512caf57)


## 🌐 Deployment

### Production

- **Platform**: Heroku (EU Region)
- **URL**: https://dent-global-langgraph-17819f2ad14c.herokuapp.com


## 📝 License

Copyright © 2025 Dent Global. All rights reserved. Proprietary and confidential.