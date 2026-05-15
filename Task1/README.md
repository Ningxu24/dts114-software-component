# Task 1 — AI-Assisted Meta Software Development System

**Module**: DTS114TC Software Component  
**Live URL**: https://dts114-software-component.onrender.com  
**Repository**: https://github.com/Ningxu24/dts114-software-component

---

## Overview

This project demonstrates a **meta software development system**: rather than building the application by hand, a single Jupyter Notebook (`generate.ipynb`) orchestrates an LLM (GPT-class model via APIFree) to produce all artefacts of a fully-functional software system automatically — source code, tests, documentation, UML diagrams, CI/CD configuration, and an AI-generated hero image.

The resulting deliverable is a **Book Catalogue REST API** with a browser-accessible front-end, deployed continuously to Render via GitHub Actions.

---

## Quick Start

### Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.10+ |
| Conda (or venv) | any |
| Git | any |

### 1. Clone and set up environment

```bash
git clone https://github.com/Ningxu24/dts114-software-component.git
cd dts114-software-component
conda env create -f ai_in_se_cw.yml
conda activate ai_in_se_cw
```

### 2. Configure API key

Create a `.env` file in the project root:

```
OPENAI_API_KEY=<your-apifree-key>
```

### 3. Run the notebook (regenerate all artefacts)

Open `Task1/generate.ipynb` in Jupyter and run all cells.  
The notebook will:
- Generate Flask application code via LLM
- Generate pytest test suite
- Render UML diagrams (use-case, class, sequence) as PNG
- Produce an AI-generated hero banner image (ByteDance Seedream-4.5 via APIFree)
- Write all output files into `Task1/app/` and `Task1/docs/`

### 4. Run the app locally

```bash
cd Task1/app
pip install -r requirements.txt
flask run
# → http://127.0.0.1:5000
```

### 5. Run tests

```bash
cd Task1
pytest tests/ -v
```

---

## API Reference

Base URL (production): `https://dts114-software-component.onrender.com`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Rendered HTML front-end |
| `GET` | `/api/items` | List all items; supports `?category=` and `?search=` |
| `GET` | `/api/items/<id>` | Get a single item by ID |
| `POST` | `/api/items` | Add a new item (JSON body required) |
| `DELETE` | `/api/items/<id>` | Delete an item |
| `PATCH` | `/api/items/<id>` | Partially update an item |
| `GET` | `/api/categories` | List all distinct genres/categories |

### POST /api/items — request body

```json
{
  "title": "Clean Architecture",
  "genre": "Software Engineering",
  "price": 34.99,
  "description": "A guide to structuring software for long-term maintainability."
}
```

All four fields are required. Returns `201 Created` with the new item and a `Location` header.

### Rate limiting

API routes are rate-limited to **120 requests/minute per IP**. Exceeding this returns `429 Too Many Requests`.

---

## Project Structure

```
Task1/
├── generate.ipynb          # Master notebook — generates all artefacts via LLM
├── app/
│   ├── app.py              # Flask REST API (LLM-generated)
│   ├── requirements.txt    # Python dependencies
│   ├── static/images/
│   │   └── generated.png   # AI-generated hero banner (Seedream-4.5)
│   └── templates/
│       └── index.html      # Front-end HTML (LLM-generated)
├── docs/
│   ├── requirements.md     # Software requirements (LLM-generated)
│   └── uml/
│       ├── use_case_diagram.puml / .png
│       ├── class_diagram.puml    / .png
│       └── sequence_diagram.puml / .png
└── tests/
    └── test_app.py         # pytest suite (LLM-generated)
```

---

## CI/CD Pipeline

Every push to `main` triggers the **GitHub Actions** workflow (`.github/workflows/ci.yml`):

1. **Run Tests** — installs dependencies, runs `pytest tests/` (12 s avg)
2. **Deploy to Render** — on test success, fires the Render deploy webhook via `curl`

The live service is automatically updated within ~1–2 minutes of every successful push.

---

## AI Artefact Generation

All major artefacts were produced by prompting an LLM (openai/gpt-5.2 via APIFree):

| Artefact | Model | Notes |
|----------|-------|-------|
| Flask app (`app.py`) | GPT-class LLM | REST API with rate limiting, CORS, validation |
| Front-end (`index.html`) | GPT-class LLM | Responsive HTML/CSS/JS |
| Requirements doc | GPT-class LLM | Functional + non-functional requirements |
| UML diagrams | GPT-class LLM → PlantUML | Use-case, class, sequence |
| pytest suite | GPT-class LLM | 100 % endpoint coverage |
| CI/CD YAML | GPT-class LLM | GitHub Actions with Render deploy hook |
| Hero image | ByteDance Seedream-4.5 (APIFree) | Text-to-image via `/v1/chat/completions` |

---

## Meta-System Philosophy

The goal of this project is not simply to produce a book catalogue — it is to demonstrate that **the same notebook-based pipeline can generate any CRUD-style software system** by changing the domain description fed to the LLM.

Replacing the input prompt (e.g. "book catalogue" → "course management system") re-runs the same generation, test, and deploy chain and produces a fully different but structurally identical deployable application. This is the essence of a *meta* software development system.

---

## Limitations

- Data is stored in-memory; the catalogue resets on each server restart (Render free tier spins down after inactivity).
- The Render free instance may take up to 50 seconds to respond on cold start.
- LLM output is non-deterministic; re-running the notebook may produce slightly different but functionally equivalent code.
