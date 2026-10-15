"""Git skill-check items."""

from __future__ import annotations

MCQ: dict[str, list[tuple[str, tuple[str, ...], int]]] = {
    "vcs_idea": [
        (
            "Version control mainly lets you:",
            (
                "track and undo changes over time",
                "run code faster",
                "store passwords",
                "deploy websites",
            ),
            0,
        ),
        (
            "A commit is:",
            ("a saved snapshot of the project", "a branch", "a remote server", "a merge conflict"),
            0,
        ),
    ],
    "git_config": [
        (
            "Set the name on your commits:",
            (
                'git config --global user.name "Asha"',
                "git name Asha",
                "git set user Asha",
                "git user --name Asha",
            ),
            0,
        ),
        (
            "--global config applies to:",
            ("every repository for your user", "only this repo", "only this commit", "the remote"),
            0,
        ),
    ],
    "init_clone": [
        (
            "Copy a GitHub repository to your machine:",
            ("git clone <url>", "git init <url>", "git pull <url> --new", "git copy <url>"),
            0,
        ),
        (
            "git init creates:",
            ("a new empty repository", "a commit", "a branch on GitHub", "a remote"),
            0,
        ),
    ],
    "stage_commit": [
        (
            "Stage a file for the next commit:",
            ("git add file.py", "git commit file.py", "git push file.py", "git stage --all"),
            0,
        ),
        (
            "git commit -m 'msg' saves:",
            (
                "the staged changes",
                "every file in the folder",
                "only unstaged changes",
                "the remote",
            ),
            0,
        ),
    ],
    "log_diff": [
        (
            "See unstaged changes line by line:",
            ("git diff", "git log", "git status -v", "git show"),
            0,
        ),
        (
            "git log --oneline shows:",
            ("one line per commit", "the diff", "branches only", "remote URLs"),
            0,
        ),
    ],
    "gitignore": [
        (
            "A .gitignore line *.csv means:",
            (
                "CSV files are not tracked",
                "only CSV files are tracked",
                "CSV files are deleted",
                "CSV is a branch",
            ),
            0,
        ),
        (
            ".gitignore does NOT untrack a file that is:",
            ("already committed", "new", "in a subfolder", "a .csv"),
            0,
        ),
    ],
    "branches": [
        (
            "Create and switch to a new branch:",
            (
                "git switch -c feature",
                "git branch -m feature",
                "git checkout feature --new",
                "git merge feature",
            ),
            0,
        ),
        (
            "A branch is:",
            ("a movable pointer to a commit", "a copy of the folder", "a remote", "a tag"),
            0,
        ),
    ],
    "merge": [
        (
            "Bring feature into main (while on main):",
            ("git merge feature", "git merge main", "git push feature", "git rebase main feature"),
            0,
        ),
        (
            "A fast-forward merge happens when:",
            (
                "main has no new commits since feature branched",
                "both changed the same line",
                "there is a conflict",
                "the branch is deleted",
            ),
            0,
        ),
    ],
    "merge_conflicts": [
        (
            "A conflict happens when both branches:",
            (
                "changed the same lines differently",
                "added different files",
                "have the same name",
                "were pushed",
            ),
            0,
        ),
        (
            "After fixing conflict markers you:",
            (
                "git add the file and commit",
                "git push --force",
                "git reset --hard",
                "delete the branch",
            ),
            0,
        ),
    ],
    "remotes": [
        (
            "origin usually means:",
            (
                "the remote you cloned from",
                "your first commit",
                "the main branch",
                "your local folder",
            ),
            0,
        ),
        (
            "List remotes with their URLs:",
            ("git remote -v", "git origin", "git branch -r -v", "git url"),
            0,
        ),
    ],
    "push_pull": [
        ("git pull is:", ("fetch + merge", "push + fetch", "clone + commit", "add + commit"), 0),
        (
            "Your push is rejected because the remote has new commits. You first:",
            (
                "pull (or fetch and merge)",
                "push --force always",
                "delete the remote",
                "make a new repo",
            ),
            0,
        ),
    ],
    "pull_requests": [
        (
            "A pull request asks reviewers to:",
            (
                "review and merge your branch",
                "download your repo",
                "delete a branch",
                "create a remote",
            ),
            0,
        ),
        (
            "Small, focused pull requests are easier to:",
            ("review", "write slowly", "hide bugs in", "merge without tests"),
            0,
        ),
    ],
    "undo": [
        (
            "Undo a pushed commit safely for others:",
            (
                "git revert <commit>",
                "git reset --hard and push --force",
                "delete .git",
                "git checkout <commit>",
            ),
            0,
        ),
        (
            "Unstage a file but keep its edits:",
            ("git restore --staged file", "git reset --hard", "git rm file", "git clean -f"),
            0,
        ),
    ],
}

TASK: dict[str, tuple[str, str]] = {
    "stage_commit": (
        "Which git command saves staged changes as a snapshot? (one word after git)",
        "commit",
    ),
    "push_pull": ("Which git command is fetch + merge in one step? (one word after git)", "pull"),
}
