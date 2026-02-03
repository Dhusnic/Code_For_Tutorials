from git import Repo
import re
import os
class DiffCollector:
    def __init__(self, repo_path,env_path=".env"):
        self.repo_path = repo_path
        self.env_path = env_path
        self.excluded_dirs = ['.git', 'node_modules', '__pycache__']
        self.excluded_files = ['.DS_Store', 'thumbs.db',".env","*.db","*.sqlite3","*.log","*.pyc","*.json","*.ini","environment.instance.ts","requirements.txt","*.png"]
        self.included_files = ["en.json","hi.json","ar.json"]
    def collect_repo_diff(self):
        """
            Collects file-by-file diffs with:
            - line numbers
            - hunks
            - context lines
            - added/removed lines
        """
        try:
            repo = Repo(self.repo_path)
            diffs = repo.index.diff(None, create_patch=True)
            results = []
            hunk_pattern = re.compile(r"@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@")
            for diff in diffs:
                patch = diff.diff.decode("utf-8", errors="ignore")
                file_changes = {
                    "file": diff.a_path or diff.b_path,
                    "change_type": diff.change_type,
                    "hunks": []
                }
                old_line_no = None
                new_line_no = None
                current_hunk = None
                if not self.is_excluded(file_changes.get("file","")) or os.path.basename(file_changes.get("file","")) in self.included_files:
                    for line in patch.splitlines():
                        # HUNK HEADER
                        if line.startswith("@@"):
                            match = hunk_pattern.search(line)
                            if match:
                                old_start, old_count, new_start, new_count = match.groups()

                                old_line_no = int(old_start)
                                new_line_no = int(new_start)

                                current_hunk = {
                                    "old_start": old_start,
                                    "old_count": old_count or "1",
                                    "new_start": new_start,
                                    "new_count": new_count or "1",
                                    "context": [],
                                    "added": [],
                                    "removed": []
                                }
                                file_changes["hunks"].append(current_hunk)
                            continue

                        # CONTEXT LINE
                        if line.startswith(" ") and current_hunk:
                            current_hunk["context"].append({
                                "line": line[1:],
                                "old_line": old_line_no,
                                "new_line": new_line_no
                            })
                            old_line_no += 1
                            new_line_no += 1

                        # REMOVED LINE
                        elif line.startswith("-") and not line.startswith("---") and current_hunk:
                            current_hunk["removed"].append({
                                "line": line[1:],
                                "old_line": old_line_no
                            })
                            old_line_no += 1

                        # ADDED LINE
                        elif line.startswith("+") and not line.startswith("+++") and current_hunk:
                            current_hunk["added"].append({
                                "line": line[1:],
                                "new_line": new_line_no
                            })
                            new_line_no += 1
                    results.append(file_changes)
            return results
        except Exception as e:
            print(f"Error collecting diffs: {e}")
            return []
        
    def is_excluded(self, file_path):
        for excl_dir in self.excluded_dirs:
            if excl_dir in file_path.split('/'):
                return True
        for excl_file in self.excluded_files:
            if re.fullmatch(excl_file.replace("*", ".*"), os.path.basename(file_path)):
                return True
        return False