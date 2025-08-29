# Value Canvas Sections Structure

This directory contains the modularized sections of the Value Canvas framework.

## Directory Structure

```
sections/
├── base.py                 # Base rules and shared logic
├── interview/              # Initial interview section
│   ├── models.py          # InterviewData model
│   └── prompts.py         # Interview prompts and templates
├── icp/                   # Ideal Client Persona section
│   ├── models.py          # ICPData model
│   └── prompts.py         # ICP prompts and templates
├── pain/                  # Pain points section
│   ├── models.py          # PainData, PainPoint models
│   └── prompts.py         # Pain prompts and templates
├── deep_fear/             # Deep Fear section
│   ├── models.py          # DeepFearData model
│   └── prompts.py         # Deep Fear prompts and templates
├── payoffs/               # Payoffs section
│   ├── models.py          # PayoffsData, PayoffPoint models
│   └── prompts.py         # Payoffs prompts and templates
├── signature_method/      # Signature Method section
│   ├── models.py          # SignatureMethodData, Principle models
│   └── prompts.py         # Signature Method prompts and templates
├── mistakes/              # Mistakes section
│   ├── models.py          # MistakesData, Mistake models
│   └── prompts.py         # Mistakes prompts and templates
├── prize/                 # Prize section
│   ├── models.py          # PrizeData model
│   └── prompts.py         # Prize prompts and templates
└── implementation/        # Implementation section
    ├── models.py          # ImplementationData model (if needed)
    └── prompts.py         # Implementation prompts and templates
```

## Usage

Each section module exports:
- Data models specific to that section
- Prompt templates and system prompts
- Section configuration

Example:
```python
from src.agents.value_canvas.sections.interview import InterviewData, INTERVIEW_TEMPLATE
from src.agents.value_canvas.sections.icp import ICPData, ICP_TEMPLATE
```

## Backward Compatibility

The main `prompts.py` and `models.py` files at the parent level maintain backward compatibility by re-exporting all section content.