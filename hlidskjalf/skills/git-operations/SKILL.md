---
name: git-operations
description: Perform common Git operations including commits, branching, merging,
  handling merge conflicts, and rebasing.
version: 1.0.0
author: Norns
tags:
- git
- version control
- commits
- branches
- merging
- conflicts
- rebase
triggers:
- git operations
- handle git
- manage branches
- resolve conflicts
---

## Git Operations

This skill provides a comprehensive guide to performing common Git operations, including creating commits, managing branches, merging, resolving merge conflicts, and performing rebases.

### Committing Changes

1. **Stage Changes**: Use `git add <file>` to stage changes. Use `git add .` to stage all changes.
2. **Commit Changes**: Use `git commit -m "Your commit message"` to commit staged changes.

### Branching

1. **Create a New Branch**: Use `git branch <branch-name>` to create a new branch.
2. **Switch to a Branch**: Use `git checkout <branch-name>` or `git switch <branch-name>` to switch to an existing branch.
3. **List Branches**: Use `git branch` to list all branches.

### Merging

1. **Merge a Branch**: Switch to the branch you want to merge into, then use `git merge <branch-name>` to merge another branch into it.
2. **Abort a Merge**: If a merge goes wrong, use `git merge --abort` to stop it and revert to the pre-merge state.

### Handling Merge Conflicts

1. **Identify Conflicts**: After attempting a merge, Git will mark conflicts in files.
2. **Resolve Conflicts**: Manually edit the files to resolve conflicts, then stage the resolved files using `git add <file>`.
3. **Complete the Merge**: After resolving conflicts and staging the changes, complete the merge with `git commit`.

### Rebasing

1. **Start a Rebase**: Use `git rebase <branch-name>` to rebase the current branch onto another branch.
2. **Resolving Conflicts During Rebase**: Resolve conflicts as you would during a merge, then use `git rebase --continue`.
3. **Abort a Rebase**: Use `git rebase --abort` to stop the rebase and return to the original state.

### Additional Tips
- **Check Status**: Use `git status` regularly to check the state of your repository.
- **View Commit History**: Use `git log` to view the commit history.

This guide is useful for developers familiar with Git basics who need a quick reference for more advanced operations.
