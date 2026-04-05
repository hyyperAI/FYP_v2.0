"""
backend/api/database.py

Essential REST API endpoints for database operations.
"""

from fastapi import FastAPI, HTTPException, Query, Body
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from backend.database import operations


class SearchRequest(BaseModel):
    query: str
    job_type: Optional[str] = None
    experience_level: Optional[str] = None


class JobCreateRequest(BaseModel):
    job_id: str
    title: str
    description: Optional[str] = None
    job_url: str
    type: Optional[str] = None
    skills: Optional[List[str]] = None
    experience_level: Optional[str] = None
    budget: Optional[str] = None
    search_query: Optional[str] = None
    client_location: Optional[str] = None
    client_hire_rate: Optional[str] = None
    client_company_size: Optional[str] = None
    member_since: Optional[str] = None
    client_total_spent: Optional[str] = None
    client_hours: Optional[int] = None
    client_jobs_posted: Optional[int] = None


class JobUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    skills: Optional[List[str]] = None
    experience_level: Optional[str] = None
    budget: Optional[str] = None
    client_location: Optional[str] = None
    client_hire_rate: Optional[str] = None
    client_company_size: Optional[str] = None
    member_since: Optional[str] = None
    client_total_spent: Optional[str] = None
    client_hours: Optional[int] = None
    client_jobs_posted: Optional[int] = None

router = FastAPI(
    title="Upwork Jobs Database API",
    description="API for querying scraped job data from SQLite database",
    version="1.0.0"
)


@router.get("/api/jobs")
async def list_jobs(
    job_type: Optional[str] = Query(None, alias="job_type", description="Filter by job type (Hourly/Fixed)"),
    search_query: Optional[str] = Query(None, alias="search_query", description="Filter by search query"),
    budget: Optional[str] = Query(None, description="Filter by budget"),
    client_location: Optional[str] = Query(None, alias="client_location", description="Filter by client location"),
    limit: int = Query(100, description="Maximum number of jobs to return"),
    offset: int = Query(0, description="Offset for pagination")
) -> Dict[str, Any]:
    """
    List jobs with optional filters.
    """
    filters = {}
    if job_type:
        filters['type'] = job_type
    if search_query:
        filters['search_query'] = search_query
    if budget:
        filters['budget'] = budget
    if client_location:
        filters['client_location'] = client_location

    filters['limit'] = limit
    filters['offset'] = offset

    try:
        jobs = operations.get_jobs(filters)
        total_count = len(jobs)
        return {
            "jobs": jobs,
            "total": len(jobs),
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve jobs: {str(e)}")


@router.get("/api/stats")
async def get_database_stats() -> Dict[str, Any]:
    """
    Get database statistics.
    """
    try:
        stats = operations.get_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")


@router.get("/api/search")
async def search_jobs(
    query: str = Query(..., description="Search query string"),
    job_type: Optional[str] = Query(None, description="Filter by job type"),
    experience_level: Optional[str] = Query(None, description="Filter by experience level")
) -> Dict[str, Any]:
    """
    Search jobs by query string with optional filters.
    """
    filters = {}
    if job_type:
        filters['type'] = job_type
    if experience_level:
        filters['experience_level'] = experience_level

    try:
        jobs = operations.search_jobs(query, filters)
        return {
            "jobs": jobs,
            "total": len(jobs),
            "query": query
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/api/jobs/{job_id}")
async def get_job_by_id(job_id: int) -> Dict[str, Any]:
    """
    Get a single job by database ID.
    """
    try:
        job = operations.get_job_by_id(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job with ID {job_id} not found")
        return job
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve job: {str(e)}")


@router.delete("/api/jobs/{job_id}")
async def delete_job(job_id: int) -> Dict[str, str]:
    """
    Delete a job by database ID.
    """
    try:
        success = operations.delete_job(job_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Job with ID {job_id} not found")
        return {"message": f"Job {job_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete job: {str(e)}")


@router.post("/api/jobs")
async def create_job(request: JobCreateRequest) -> Dict[str, Any]:
    """
    Create a new job.
    """
    try:
        job_data = request.dict()
        job_id = operations.save_job(job_data)
        created_job = operations.get_job_by_id(job_id)
        return {
            "message": "Job created successfully",
            "job": created_job
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create job: {str(e)}")


@router.put("/api/jobs/{job_id}")
async def update_job(job_id: int, request: JobUpdateRequest) -> Dict[str, Any]:
    """
    Update an existing job.
    """
    try:
        existing_job = operations.get_job_by_id(job_id)
        if not existing_job:
            raise HTTPException(status_code=404, detail=f"Job with ID {job_id} not found")

        update_data = request.dict(exclude_unset=True)
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")

        update_data['job_id'] = existing_job['job_id']
        update_data['job_url'] = existing_job['job_url']
        update_data['search_query'] = existing_job.get('search_query')

        operations.save_job(update_data)
        updated_job = operations.get_job_by_id(job_id)

        return {
            "message": f"Job {job_id} updated successfully",
            "job": updated_job
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update job: {str(e)}")


app = router


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
