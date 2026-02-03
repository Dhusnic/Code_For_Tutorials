from git_manager.diff_collector import DiffCollector
from review_manager.ai_reviewer import AIReviewer
from azure_manager.azure_manager import AzureDevOpsClient
from comman import CommonUtils
import os
class AgenticAICodeReviewCLI(CommonUtils):
    def __init__(self):
        self.repo_path = os.path.abspath("D:\\Product\\Infraon")
        
        self.ai_model = "gpt-4o-mini"
        self.max_tokens = 30000
        
        self.env_path = os.path.abspath("agentic_ai_code_review/config/.env")
        
        self.organization = "infraon"
        self.project = "Infraon"
        self.repository_name = "Infraon"
        self.pull_request_id = "16863"
        self.azure_pat = self.get_env_value(env_path=self.env_path, key="AZURE_DEVOPS_PAT", default="")
        
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
        # diffs = self.diff_collector.collect_repo_diff()
        diffs  = self.azure_manager.get_pr_content_changes(
            repository_name=self.repository_name,
            pull_request_id=int(self.pull_request_id),
            instruction="Get full diff with line numbers and hunks."
        )
        
        print("Reviewing diffs with AI...")
        conversation = [
            {"role": "system", "content": "You are a code review assistant."},
            {"role": "user", "content": f"Please review the following diffs:\n{diffs}"}
        ]
        
        review = self.ai_reviewer.get_ai_response(
            conversation=conversation,
            model=self.ai_model,
            max_output_tokens=512
        )
        
        print("AI Review:")
        print(review)
        
        

if __name__ == "__main__":
    cli = AgenticAICodeReviewCLI()
    cli.main()
