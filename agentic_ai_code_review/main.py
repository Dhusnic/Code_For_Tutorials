from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
import sys

# Add parent directory to path to import your modules
sys.path.append(os.path.abspath(".."))

from git_manager.diff_collector import DiffCollector
from review_manager.ai_reviewer import AIReviewer
from azure_manager.azure_manager import AzureDevOpsClient
from comman import CommonUtils
from config import prompts

from cli import AgenticAICodeReviewCLI

app = FastAPI(title="Agentic AI Code Review API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
# app.mount("D:\\Code for tutorials\\agentic_ai_code_review\\ui", StaticFiles(directory="ui"), name="ui")

# Global instance
review_service = None

class ConfigModel(BaseModel):
    repo_path: str
    ai_model: str = "gpt-4o-mini"
    max_tokens: int = 30000
    organization: str
    project: str
    repository_name: str
    pull_request_id: str
    azure_pat: Optional[str] = None
    is_local: Optional[bool] = False
    review : Optional[str] = ""

class ApplyChangesModel(BaseModel):
    file_path: str
    new_content: str
    repo_path: str
    line_number: int
    new_start_line_number: int
    number_of_lines_removed_from_old: int
    number_of_lines_added_in_new: int
    old_start_line_number: int
    old_content: str

# class ReviewService(CommonUtils):
#     def __init__(self, config: ConfigModel):
#         self.repo_path = os.path.abspath(config.repo_path)
#         self.ai_model = config.ai_model
#         self.max_tokens = config.max_tokens
#         self.env_path = os.path.abspath("agentic_ai_code_review/config/.env")
        
#         self.organization = config.organization
#         self.project = config.project
#         self.repository_name = config.repository_name
#         self.pull_request_id = config.pull_request_id
#         self.azure_pat = config.azure_pat or self.get_env_value(
#             env_path=self.env_path, 
#             key="AZURE_DEVOPS_PAT", 
#             default=""
#         )
        
#         self.diff_collector = DiffCollector(self.repo_path, env_path=self.env_path)
#         self.ai_reviewer = AIReviewer(
#             model_name=self.ai_model, 
#             max_tokens=self.max_tokens, 
#             env_path=self.env_path
#         )
#         self.azure_manager = AzureDevOpsClient(
#             organization=self.organization, 
#             project=self.project, 
#             pat_token=self.azure_pat
#         )
        
#         self.diffs = None
#         self.review = None
#         self.code_changes = None
#         self.token_estimate = 0

#     def collect_diffs(self):
#         """Collect diffs from Azure DevOps PR"""
#         self.diffs = self.azure_manager.get_pr_content_changes(
#             repository_name=self.repository_name,
#             pull_request_id=int(self.pull_request_id),
#             instruction="Get full diff with line numbers and hunks."
#         )
#         self.token_estimate = self.ai_reviewer.estimate_tokens(str(self.diffs))
#         return self.diffs

#     def perform_review(self):
#         """Perform AI code review"""
#         if not self.diffs:
#             self.collect_diffs()
        
#         conversation = [
#             {"role": "system", "content": "You are a code review assistant."},
#             {"role": "user", "content": prompts.Review_prompt + f"\n\nDiffs to review:\n{self.diffs}"}
#         ]
        
#         self.review = self.ai_reviewer.get_ai_response(
#             conversation=conversation,
#             model=self.ai_model,
#             max_output_tokens=512
#         )
#         return self.review

#     def generate_code_changes(self):
#         """Generate code change suggestions"""
#         if not self.review:
#             self.perform_review()
        
#         conversation_code_change = [
#             {"role": "system", "content": "You are a senior Angular + Django developer."},
#             {"role": "user", "content": prompts.Code_corrections_prompt + 
#                 f"\n\nDiffs:\n{self.diffs}\n\nReview Comment:\n{self.review}"}
#         ]
        
#         code_change = self.ai_reviewer.get_ai_response(
#             conversation=conversation_code_change,
#             model=self.ai_model,
#             max_output_tokens=512
#         )
        
#         try:
#             self.code_changes = self.extract_json_from_ai_output(code_change)
#         except Exception as e:
#             self.code_changes = {"error": str(e), "raw_output": code_change}
        
#         self.ai_reviewer.last_review = self.review
#         self.ai_reviewer.last_code_change = self.code_changes
        
#         return self.code_changes

@app.get("/")
async def read_root():
    return FileResponse("D:\\Code for tutorials\\agentic_ai_code_review\\ui\\index.html")

# @app.post("/api/initialize")
# async def initialize(config: ConfigModel):
#     """Initialize the review service with configuration"""
#     global review_service
#     try:
#         review_service = ReviewService(config)
#         return {
#             "status": "success",
#             "message": "Service initialized successfully",
#             "config": {
#                 "repo_path": config.repo_path,
#                 "ai_model": config.ai_model,
#                 "max_tokens": config.max_tokens,
#                 "organization": config.organization,
#                 "project": config.project,
#                 "repository_name": config.repository_name,
#                 "pull_request_id": config.pull_request_id
#             }
#         }
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# @app.get("/api/config/defaults")
# async def get_default_config():
#     """Get default configuration values"""
#     return {
#         "repo_path": "D:\\Product\\Infraon",
#         "ai_model": "gpt-4o-mini",
#         "max_tokens": 30000,
#         "organization": "infraon",
#         "project": "Infraon",
#         "repository_name": "Infraon",
#         "pull_request_id": "17070"
#     }

@app.post("/api/review-diffs")
async def review_diffs(config: ConfigModel):
    """Collect diffs from the PR"""
    # if not review_service:
    #     raise HTTPException(status_code=400, detail="Service not initialized. Please configure first.")
    
    try:
        controller = AgenticAICodeReviewCLI(config)
        diffs = controller.review_diffs()
        return diffs
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/api/generate-changes")
async def generate_changes(config: ConfigModel):
    """Generate code change suggestions"""
    controller = AgenticAICodeReviewCLI(config=config)
    
    try:
        code_changes = controller.generate_changes(review=config.review)
        return code_changes
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/review")
async def perform_review():
    """Perform AI code review"""
    if not review_service:
        raise HTTPException(status_code=400, detail="Service not initialized. Please configure first.")
    
    try:
        review = review_service.perform_review()
        return {
            "status": "success",
            "review": review
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/run-full-review")
async def run_full_review():
    """Run complete review process"""
    if not review_service:
        raise HTTPException(status_code=400, detail="Service not initialized. Please configure first.")
    
    try:
        # Collect diffs
        diffs = review_service.collect_diffs()
        
        # Perform review
        review = review_service.perform_review()
        
        # Generate code changes
        code_changes = review_service.generate_code_changes()
        
        return {
            "status": "success",
            "diffs": diffs,
            "token_estimate": review_service.token_estimate,
            "review": review,
            "code_changes": code_changes
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@app.post("/api/apply-changes")
async def apply_changes(change: ApplyChangesModel):
    try:
        file_path = change.file_path.lstrip("/\\")
        repo_path = os.path.abspath(change.repo_path)
        file_path = (
            os.path.join(repo_path, file_path)
            if not os.path.isabs(file_path) else file_path
        )
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")

        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        backup_path = file_path + ".backup"
        with open(backup_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        old_start = change.old_start_line_number - 1
        old_end = old_start + change.number_of_lines_removed_from_old

        if old_start < 0 or old_end > len(lines):
            raise HTTPException(status_code=400, detail="Invalid line range")

        # old_block = "".join(lines[old_start:old_end]).rstrip("\n")
        # expected_old = change.old_content.rstrip("\n")
        # def normalize(s: str) -> str:
        #     return " ".join(s.split())

        # if normalize(old_block) != normalize(expected_old):
        #     raise HTTPException(
        #         status_code=409,
        #         detail="Old content mismatch; file may have changed"
        #     )

        new_lines = [
            line + "\n" if not line.endswith("\n") else line
            for line in change.new_content.splitlines()
        ]

        lines[old_start:old_end] = new_lines

        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        return {
            "status": "success",
            "message": f"Changes applied at line {change.old_start_line_number}",
            "backup_path": backup_path
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service_initialized": review_service is not None
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
