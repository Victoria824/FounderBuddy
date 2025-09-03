# Special Report Agent Documentation

## Overview

The Special Report Agent helps users create comprehensive special reports using a structured 3-section process:

1. **Topic Selection**: Choose and refine report topics based on Value Canvas insights
2. **Content Development**: Develop content using 4 thinking styles framework
3. **Report Structure**: Structure content using 7-step article framework

## Architecture

This agent follows the modular architecture pattern established by the Value Canvas agent:

- **Nodes**: Initialize, Router, Generate Reply, Generate Decision, Memory Updater, Implementation
- **Sections**: Modular section handling with individual prompts and data models
- **State Management**: Satisfaction-based progress tracking
- **Memory**: Real-time data persistence with structured extraction

## Section Flow

1. Topic Selection → Content Development → Report Structure → Implementation
2. Each section collects specific data and waits for user satisfaction before proceeding
3. Implementation generates the final 5500-word special report

## Key Features

- Integration with Value Canvas data for personalized content
- 4 thinking styles content development approach
- 7-step article structure framework
- Real-time progress saving and recovery
- Structured data extraction and persistence