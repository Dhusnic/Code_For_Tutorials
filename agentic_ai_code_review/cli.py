from git_manager.diff_collector import DiffCollector
from review_manager.ai_reviewer import AIReviewer
from azure_manager.azure_manager import AzureDevOpsClient
from comman import CommonUtils
import os
from config import prompts
class AgenticAICodeReviewCLI(CommonUtils):
    def __init__(self, config=None):
        if config is None:
            self.env_path = os.path.abspath("agentic_ai_code_review/config/.env")
            self.repo_path = os.path.abspath("D:\\Product\\Infraon")
            self.ai_model = "gpt-4o-mini"
            self.env_path = os.path.abspath("agentic_ai_code_review/config/.env")
            self.organization = "infraon"
            self.project = "Infraon"
            self.repository_name = "Infraon"
            self.pull_request_id = "17070"
            self.azure_pat = self.get_env_value(env_path=self.env_path, key="AZURE_DEVOPS_PAT", default="")
            self.is_local = False
            
        else:
            self.env_path = os.path.abspath("agentic_ai_code_review/config/.env")
            self.repo_path = os.path.abspath(config.repo_path)
            self.ai_model = config.ai_model if hasattr(config, 'ai_model') else "gpt-4o-mini"
            self.max_tokens = config.max_tokens if hasattr(config, 'max_tokens') else 30000
            self.organization = config.organization
            self.project = config.project
            self.repository_name = config.repository_name
            self.pull_request_id = config.pull_request_id
            self.is_local = False if not hasattr(config, 'is_local') else config.is_local
            self.azure_pat = config.azure_pat or self.get_env_value(env_path=self.env_path, key="AZURE_DEVOPS_PAT", default="")
        
        # self.env_path = os.path.abspath("agentic_ai_code_review/config/.env")
        self.diff_collector = DiffCollector(self.repo_path,env_path=self.env_path)
        self.ai_reviewer = AIReviewer(model_name=self.ai_model, max_tokens=self.max_tokens, env_path=self.env_path)
        self.azure_manager = AzureDevOpsClient(organization=self.organization, project=self.project, pat_token=self.azure_pat)
    def show_diffs(self):
        diffs = self.diff_collector.collect_repo_diff()
        for change in diffs:
            print(diffs)
            print(f"File: {change['file']}, Change Type: {change['change_type']}")
        
        print("The estimated token usage is :",self.ai_reviewer.estimate_tokens(str(diffs)))
        
    def main(self):
        print("Collecting diffs...")
        tokens_used = 0
        if self.is_local:
            diffs = self.diff_collector.collect_repo_diff()
        else:
            diffs  = self.azure_manager.get_pr_content_changes(
                repository_name=self.repository_name,
                pull_request_id=int(self.pull_request_id),
                instruction="Get full diff with line numbers and hunks."
            )
        
        threads = self.azure_manager.get_pr_comments(repository_name=self.repository_name, pull_request_id=int(self.pull_request_id))
        if threads:
            print(f"Found {len(threads)} comment threads in the PR. Including them in the review.")
            review = [comment.get("content", "") for thread in threads for comment in thread.get("comments", []) if comment is not None and comment.get("content", "") != ""]
            review = "\n\n".join(review)
        else:
            print("Reviewing diffs with AI...")
            conversation = [
                {"role": "system", "content": "You are a code review assistant."},
                {"role": "user", "content": prompts.Review_prompt + f"\n\nDiffs to review:\n{diffs}"}
            ]
            
            review_data = self.ai_reviewer.get_ai_response(
                conversation=conversation,
                model=self.ai_model,
                max_output_tokens=20000
            )
            
            review = review_data["response"]
            tokens_used = review_data["tokens_used"]
        
            print("AI Review:")
        print(review)
        
        code_change_prompt = {
            "diffs": diffs,
            "review_comment": review,
            "Code_change_prompt": prompts.Code_corrections_prompt
        }
        
        conversation_code_change = [
            {"role": "system", "content": "You are a senior Angular + Django developer."},
            {"role": "user", "content": prompts.Code_corrections_prompt + f"\n\nDiffs:\n{diffs}\n\nReview Comment:\n{review}"}
        ]
        
        code_change_data = self.ai_reviewer.get_ai_response(
            conversation=conversation_code_change,
            model=self.ai_model,
            max_output_tokens=20000
        )
        
        code_change = code_change_data["response"]
        tokens_used += code_change_data["tokens_used"]
        print(code_change)
        try:
            extracted_json = self.extract_json_from_ai_output(code_change)
        except Exception as e:
            print(f"Failed to extract JSON from AI output: {e}")
        if extracted_json.get("diffs",None) is not None:
           extracted_json = extracted_json["diffs"]
           
           extracted_json = self.merge_consecutive_diffs(extracted_json)
        
        return {
            "review": review,
            "code_changes": extracted_json,
            "tokens_used": tokens_used
            
        }
        # show code changes in a UI if user click apply the code changes then apply those changes and show the whole and if cancel then do nothing. 
        
    def review_diffs(self):
        print("Collecting diffs...")
        tokens_used = 0
        if self.is_local:
            diffs = self.diff_collector.collect_repo_diff()
        else:
            diffs  = self.azure_manager.get_pr_content_changes(
                repository_name=self.repository_name,
                pull_request_id=int(self.pull_request_id),
                instruction="Get full diff with line numbers and hunks."
            )
        
        threads = self.azure_manager.get_pr_comments(repository_name=self.repository_name, pull_request_id=int(self.pull_request_id))
        if threads:
            print(f"Found {len(threads)} comment threads in the PR. Including them in the review.")
            review = [comment.get("content", "") for thread in threads for comment in thread.get("comments", []) if comment is not None and comment.get("content", "") != ""]
            review = "\n\n".join(review)
        else:
            print("Reviewing diffs with AI...")
            conversation = [
                {"role": "system", "content": "You are a code review assistant."},
                {"role": "user", "content": prompts.Review_prompt + f"\n\nDiffs to review:\n{diffs}"}
            ]
            
            review_data = self.ai_reviewer.get_ai_response(
                conversation=conversation,
                model=self.ai_model,
                max_output_tokens=20000
            )
            
            review = review_data["response"]
            tokens_used = review_data["tokens_used"]
        
            print("AI Review:")
        print(review)
        return {
            "review": review,
            "tokens_used": tokens_used,
            "ok": True
        }
    
    def generate_changes(self, review=""):
        print("Generating code changes...")
        tokens_used = 0
        if self.is_local:
            diffs = self.diff_collector.collect_repo_diff()
        else:
            diffs  = self.azure_manager.get_pr_content_changes(
                repository_name=self.repository_name,
                pull_request_id=int(self.pull_request_id),
                instruction="Get full diff with line numbers and hunks."
            )
        conversation_code_change = [
            {"role": "system", "content": "You are a senior Angular + Django developer."},
            {"role": "user", "content": prompts.Code_corrections_prompt + f"\n\nDiffs:\n{diffs}\n\nReview Comment:\n{review}"}
        ]
        
        code_change_data = self.ai_reviewer.get_ai_response(
            conversation=conversation_code_change,
            model=self.ai_model,
            max_output_tokens=20000
        )
        
        code_change = code_change_data["response"]
        tokens_used += code_change_data["tokens_used"]
        print(code_change)
        try:
            extracted_json = self.extract_json_from_ai_output(code_change)
        except Exception as e:
            print(f"Failed to extract JSON from AI output: {e}")
        if extracted_json.get("diffs",None) is not None:
           extracted_json = extracted_json["diffs"]
           
           extracted_json = self.merge_consecutive_diffs(extracted_json)
        
        return {
            "review": review,
            "code_changes": extracted_json,
            "tokens_used": tokens_used
        }

if __name__ == "__main__":
    cli = AgenticAICodeReviewCLI()
    cli.main()
