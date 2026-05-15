# Git Workflow

This project uses a lightweight trunk-based workflow with short-lived branches.

## Branch Strategy

- `main` is always the stable integration branch.
- Create a focused branch for every change.
- Push branches frequently for backup and review.
- Merge back into `main` after checks pass.
- Delete merged branches locally and remotely when no longer needed.

Recommended branch names:

```text
feat/<short-feature-name>
fix/<short-bug-name>
docs/<short-doc-name>
test/<short-test-name>
chore/<short-maintenance-name>
```

Examples:

```text
feat/agent-orchestrator
fix/sqlite-connection-close
docs/git-workflow
chore/repo-hygiene
```

## Commit Convention

Use Conventional Commits:

```text
<type>(optional-scope): <short imperative summary>
```

Examples:

```text
feat(strategy): select strategy from market regime
fix(risk): block signals with low risk reward
docs(readme): add setup instructions
chore(git): configure repository hygiene
```

## Daily Flow

```powershell
git checkout main
git pull origin main
git checkout -b feat/my-change

# Work locally, then commit.
git status
git add .
git commit -m "feat(scope): describe change"

# Push branch for backup/review.
git push -u origin feat/my-change
```

After review and local checks:

```powershell
git checkout main
git pull origin main
git merge --no-ff feat/my-change
git push origin main
git branch -d feat/my-change
git push origin --delete feat/my-change
```

## Protected Files

Never commit:

- `.env` or any real secrets
- raw or processed market data
- local SQLite databases
- model binaries and checkpoints
- logs, caches, virtual environments, or notebook checkpoints

Use `.env.example`, `.gitkeep`, and documentation to preserve structure without leaking local artifacts.
