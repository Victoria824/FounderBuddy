# Special Report Sections

This directory contains modular section implementations for the Special Report Agent.

## Section Structure

Each section follows the same pattern:

- `models.py` - Section-specific data models
- `prompts.py` - Section prompts and templates  
- `__init__.py` - Section module initialization

## Available Sections

1. **topic_selection** - Choose and refine report topics
2. **content_development** - Develop content using 4 thinking styles
3. **report_structure** - Structure content using 7-step framework
4. **implementation** - Generate final report

## Base Components

- `base_prompt.py` - Shared base rules and templates
- `__init__.py` - Section registry and exports