"""
FastAPI application for Upwork job scraping with async task management.
Consolidates all API code into a single file.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, Path, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor
import time
import json
import re

# Import database operations
from backend.database.operations import (
    create_task,
    update_task_status,
    get_task_status,
    get_jobs_by_task,
    get_most_recent_jobs
)
from backend.database.connection import get_connection
from backend.scrape.engine import JobsScraper

# Pydantic Models
class ScrapeRequest(BaseModel):
    query: str = Field(default="python", description="Search query")
    page: int = Field(default=1, ge=1, description="Page number")
    jobs_per_page: int = Field(default=10, le=50, ge=10, description="Jobs per page")
    headless: bool = Field(default=False, description="Run browser headlessly")
    workers: int = Field(default=1, ge=1, le=10, description="Number of workers")
    fast: bool = Field(default=False, description="Fast mode")

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    job_count: Optional[int] = None
    remaining_jobs: Optional[int] = None
    error_message: Optional[str] = None

class JobResponse(BaseModel):
    job_id: Optional[str] = None
    title: str
    description: str
    budget: Optional[str] = None
    currency: Optional[str] = None
    skills: List[str]
    country: Optional[str] = None
    proposals: Optional[str] = None
    posted_date: Optional[int] = None
    scraped_at: str

class PaginatedResponse(BaseModel):
    task_id: str
    total_jobs: int
    page: int
    per_page: int
    total_pages: int
    has_next: bool
    has_prev: bool
    jobs: List[JobResponse]

# TaskManager Class
class TaskManager:
    """Manages async scraping tasks with background execution"""

    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.active_tasks: Dict[str, threading.Thread] = {}
        self.task_lock = threading.Lock()

    def create_task(self, params: Dict[str, Any], query: str) -> str:
        """Create a new scraping task"""
        task_id = str(uuid.uuid4())
        create_task(task_id, query, params)
        return task_id

    def start_scrape_task(self, task_id: str, scraper_params: Dict[str, Any]):
        """Start a scraping task in background thread"""
        update_task_status(task_id, "in_progress")
        thread = self.executor.submit(self._scrape_worker, task_id, scraper_params)
        with self.task_lock:
            self.active_tasks[task_id] = thread

    def _scrape_worker(self, task_id: str, scraper_params: Dict[str, Any]):
        """Background worker that executes scraping"""
        try:
            # Extract parameters
            query = scraper_params.get('query', 'python')
            page = scraper_params.get('page', 1)
            jobs_per_page = scraper_params.get('jobs_per_page', 10)
            headless = scraper_params.get('headless', False)
            workers = scraper_params.get('workers', 1)
            fast = scraper_params.get('fast', False)

            # Calculate pages to scrape (using page parameter as starting page)
            pages_to_scrape = page

            # Initialize scraper with task_id
            scraper = JobsScraper(
                search_query=query,
                jobs_per_page=jobs_per_page,
                pages_to_scrape=pages_to_scrape,
                save_path='',  # Don't save to file, save to DB
                headless=headless,
                workers=workers,
                fast=fast,
                retries=3,
                task_id=task_id
            )

            # Scrape jobs
            all_jobs = scraper.scrape_jobs()

            # Mark task as completed
            if all_jobs:
                update_task_status(task_id, "completed", job_count=len(all_jobs))
            else:
                update_task_status(task_id, "completed", job_count=0)

        except Exception as e:
            # Mark task as failed
            error_msg = str(e)
            update_task_status(task_id, "failed", error_message=error_msg)
        finally:
            # Remove from active tasks
            with self.task_lock:
                if task_id in self.active_tasks:
                    del self.active_tasks[task_id]

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task status from database"""
        return get_task_status(task_id)

# Create FastAPI application
app = FastAPI(
    title="Upwork Scraping API",
    description="REST API for programmatic Upwork job scraping",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize TaskManager
task_manager = TaskManager()

# API Endpoints

@app.post("/api/upwork/start_scrape", status_code=201)
async def start_scrape(request: ScrapeRequest):
    """Start an async scraping task"""
    try:
        # Create task
        task_id = task_manager.create_task(
            params=request.dict(),
            query=request.query
        )

        # Start background task
        task_manager.start_scrape_task(task_id, request.dict())

        return {
            "task_id": task_id,
            "status": "started",
            "message": "Scraping started successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/upwork/scraping_status/{task_id}")
async def get_scraping_status(task_id: str):
    """Check scraping progress"""
    try:
        status = task_manager.get_task_status(task_id)

        if not status:
            raise HTTPException(status_code=404, detail="Task not found")

        # Format response
        response = {
            "task_id": status["task_id"],
            "status": status["status"],
        }

        # Add optional fields based on status
        if status["status"] == "completed" and status["job_count"]:
            response["job_count"] = status["job_count"]
        elif status["status"] == "in_progress" and status["remaining_jobs"] is not None:
            response["remaining_jobs"] = status["remaining_jobs"]
        elif status["status"] == "failed" and status["error_message"]:
            response["error_message"] = status["error_message"]

        return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/upwork/get_scraping_results/{task_id}")
async def get_scraping_results(
    task_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, le=100, description="Items per page")
):
    """Retrieve scraped job data with pagination"""
    try:
        # Check if task exists and is completed
        status = task_manager.get_task_status(task_id)

        if not status:
            raise HTTPException(status_code=404, detail="Task not found")

        if status["status"] != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Task is not completed. Current status: {status['status']}"
            )

        # Get jobs from database
        jobs, total = get_jobs_by_task(task_id, page, per_page)

        # Calculate pagination metadata
        total_pages = (total + per_page - 1) // per_page

        # Convert to JobResponse format
        job_responses = []
        for job in jobs:
            job_resp = JobResponse(
                job_id=job.get('job_id'),
                title=job.get('title', ''),
                description=job.get('description', ''),
                budget=job.get('budget'),
                currency=job.get('currency', 'USD'),
                skills=job.get('skills', []),
                country=job.get('client_location'),
                proposals=job.get('proposals'),
                posted_date=job.get('time'),
                scraped_at=job.get('scraped_at', '')
            )
            job_responses.append(job_resp)

        return {
            "task_id": task_id,
            "total_jobs": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
            "jobs": job_responses
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/upwork/most_recent_jobs")
async def most_recent_jobs_endpoint(query: Optional[str] = Query(None, description="Search query to filter jobs")):
    """Get the 5 most recent jobs from the database"""
    try:
        # Validate query parameter
        if query and len(query) > 100:
            raise HTTPException(status_code=400, detail="Query parameter too long (max 100 characters)")

        # Get jobs from database
        jobs = get_most_recent_jobs(query=query, limit=5)

        # Format response using existing JobResponse model
        job_responses = []
        for job in jobs:
            job_resp = JobResponse(
                job_id=job.get('job_id'),
                title=job.get('title', ''),
                description=job.get('description', ''),
                budget=job.get('budget'),
                currency='USD',
                skills=job.get('skills', []),
                country=job.get('client_location'),
                proposals=job.get('proposals'),
                posted_date=job.get('time'),
                scraped_at=job.get('scraped_at', '')
            )
            job_responses.append(job_resp)

        return {
            "jobs": job_responses,
            "count": len(job_responses),
            "query": query
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
