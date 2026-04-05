# Upwork Job Proposal Automation & Analysis (FYP_v2.0)

A comprehensive Python-based tool for scraping Upwork job listings, performing data analysis, and generating AI-powered insights to optimize job proposals.

## Project Overview

This project provides a modular backend for automated Upwork job scraping and data-driven analysis. It features a dual-package system with both legacy support and a modern, API-driven modular architecture.

### Key Features

- **Advanced Scraping Engine**: Selenium-based scraper with Cloudflare bypass (SeleniumBase + undetected Chrome).
- **Data Analysis Engine**: Generates statistical insights and visualizations (budget distributions, skill correlations, country-wise stats).
- **FastAPI Integration**: RESTful API endpoints for managing scraping tasks and querying the database.
- **Real-time Monitoring**: Continuous job detection with webhook notifications (Slack/Discord).
- **AI Insights**: AI-powered report generation using Minimax AI.
- **Database Support**: SQLite and JSON storage for job data and task management.

---

## Project Structure

```text
├── backend/                    # New modular backend (Python 3.7+)
│   ├── scrape/                # Web scraping engine
│   ├── analysis/              # Data analysis engine
│   ├── ai/                    # AI-powered insights
│   ├── api/                   # FastAPI REST endpoints
│   ├── database/              # Database layer (SQLite/JSON)
│   ├── models/                # Data models
│   └── monitoring/             # Real-time monitoring
├── upwork_analysis/            # Legacy package (backward compatible)
├── frontend/                   # React frontend (future)
├── docs/                      # Documentation
├── requirements.txt            # Python dependencies
└── pyproject.toml             # Build configuration
```

---

## Installation

### Prerequisites

- Python 3.7 or later (3.11+ recommended)
- Google Chrome/Chromium browser

### Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-username/FYP_v2.0.git
   cd FYP_v2.0
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Install in development mode**:
   ```bash
   pip install -e .
   ```

4. **Environment Variables**:
   Create a `.env` file in the root directory:
   ```env
   MINIMAX_API_KEY=your_api_key_here
   DATABASE_URL=sqlite:///./jobs.db
   ```

---

## Usage

### Backend CLI

**Scrape Jobs:**
```bash
python -m backend.cli scrape -q "Python Developer" -o jobs.json --headless
```

**Analyze Data:**
```bash
python -m backend.cli analyze jobs.json -o analysis_output --show
```

**Database Stats:**
```bash
python -m backend.cli db stats
```

### API Server

Start the FastAPI server:
```bash
uvicorn backend.api.upwork:app --reload
```
Access the API documentation at `http://localhost:8000/docs`.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
