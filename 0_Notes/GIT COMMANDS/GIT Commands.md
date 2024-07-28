Sure! Here's a comprehensive list of common Git commands, their uses, and examples:

### 1. Configuration Commands

**Set up Git with your name and email:**
```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```
*Use:* Configures your identity so your commits are attributed correctly.
*Example:*
```bash
git config --global user.name "John Doe"
git config --global user.email "john.doe@example.com"
```

**Check current configuration:**
```bash
git config --list
```
*Use:* Displays all the current configuration settings.
*Example:*
```bash
git config --list
```

### 2. Repository Commands

**Initialize a new Git repository:**
```bash
git init
```
*Use:* Sets up a new Git repository in the current directory.
*Example:*
```bash
mkdir my_project
cd my_project
git init
```

**Clone an existing repository:**
```bash
git clone <repository_url>
```
*Use:* Creates a local copy of a remote repository.
*Example:*
```bash
git clone https://github.com/example/repo.git
```

### 3. Working Directory Commands

**Check the status of your files:**
```bash
git status
```
*Use:* Shows the state of the working directory and the staging area.
*Example:*
```bash
git status
```

**Add files to the staging area:**
```bash
git add <file_path>
```
*Use:* Stages specific files for the next commit.
*Example:*
```bash
git add README.md
```

**Add all files to the staging area:**
```bash
git add .
```
*Use:* Stages all changes in the working directory for the next commit.
*Example:*
```bash
git add .
```

**Remove files from the staging area:**
```bash
git reset <file_path>
```
*Use:* Unstages a file while retaining its changes in the working directory.
*Example:*
```bash
git reset README.md
```

**Commit changes with a message:**
```bash
git commit -m "Commit message"
```
*Use:* Records changes in the repository with a descriptive message.
*Example:*
```bash
git commit -m "Add README file"
```

**Amend the last commit:**
```bash
git commit --amend -m "New commit message"
```
*Use:* Modifies the message or content of the most recent commit.
*Example:*
```bash
git commit --amend -m "Correct typo in README file"
```

### 4. Branching and Merging Commands

**List all branches:**
```bash
git branch
```
*Use:* Displays all the branches in the repository.
*Example:*
```bash
git branch
```

**Create a new branch:**
```bash
git branch <branch_name>
```
*Use:* Creates a new branch.
*Example:*
```bash
git branch feature_branch
```

**Switch to a branch:**
```bash
git checkout <branch_name>
```
*Use:* Switches to the specified branch.
*Example:*
```bash
git checkout feature_branch
```

**Create and switch to a new branch:**
```bash
git checkout -b <branch_name>
```
*Use:* Creates a new branch and switches to it.
*Example:*
```bash
git checkout -b new_feature
```

**Merge a branch into the current branch:**
```bash
git merge <branch_name>
```
*Use:* Combines the specified branch into the current branch.
*Example:*
```bash
git merge feature_branch
```

**Delete a branch:**
```bash
git branch -d <branch_name>
```
*Use:* Deletes the specified branch.
*Example:*
```bash
git branch -d feature_branch
```

### 5. Remote Repository Commands

**List all remote repositories:**
```bash
git remote -v
```
*Use:* Displays the URLs of all remotes.
*Example:*
```bash
git remote -v
```

**Add a remote repository:**
```bash
git remote add <remote_name> <repository_url>
```
*Use:* Adds a remote repository.
*Example:*
```bash
git remote add origin https://github.com/example/repo.git
```

**Fetch changes from a remote repository:**
```bash
git fetch <remote_name>
```
*Use:* Downloads objects and refs from another repository.
*Example:*
```bash
git fetch origin
```

**Pull changes from a remote repository and merge:**
```bash
git pull <remote_name> <branch_name>
```
*Use:* Fetches and merges changes from a remote branch into the current branch.
*Example:*
```bash
git pull origin main
```

**Push changes to a remote repository:**
```bash
git push <remote_name> <branch_name>
```
*Use:* Uploads local changes to a remote repository.
*Example:*
```bash
git push origin main
```

### 6. Reset, Revert, and Clean Commands

**Reset your working directory to a specific commit:**
```bash
git reset --hard <commit_hash>
```
*Use:* Resets the current branch to the specified commit, discarding all changes.
*Example:*
```bash
git reset --hard a1b2c3d4
```

**Revert a commit by creating a new commit:**
```bash
git revert <commit_hash>
```
*Use:* Undoes a commit by creating a new commit.
*Example:*
```bash
git revert a1b2c3d4
```

**Remove untracked files from the working directory:**
```bash
git clean -f
```
*Use:* Deletes files that are not tracked by Git.
*Example:*
```bash
git clean -f
```

### 7. Stashing Commands

**Stash changes:**
```bash
git stash
```
*Use:* Temporarily saves changes that are not ready to be committed.
*Example:*
```bash
git stash
```

**Apply stashed changes:**
```bash
git stash apply
```
*Use:* Reapplies stashed changes to the working directory.
*Example:*
```bash
git stash apply
```

**List stashes:**
```bash
git stash list
```
*Use:* Displays a list of all stashed changes.
*Example:*
```bash
git stash list
```

### 8. Viewing History and Diffs

**Show commit history:**
```bash
git log
```
*Use:* Displays the commit history.
*Example:*
```bash
git log
```

**Show commit history with one line per commit:**
```bash
git log --oneline
```
*Use:* Shows a summary of the commit history.
*Example:*
```bash
git log --oneline
```

**Show changes between commits or working directory:**
```bash
git diff
```
*Use:* Displays differences between commits, working directory, and the index.
*Example:*
```bash
git diff
```

**Show changes between the staging area and the latest commit:**
```bash
git diff --cached
```
*Use:* Shows differences between staged changes and the last commit.
*Example:*
```bash
git diff --cached
```

These commands cover the basic and essential Git operations for managing a repository. Each command has various options and parameters for more advanced use cases, which you can explore further in the Git documentation.