# Contributing

Thanks for helping improve LocalQuant Assistant.

## Development Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Run checks before opening a pull request:

```powershell
python main.py
pytest
```

## Pull Request Rules

- Keep changes focused and easy to review.
- Do not commit secrets, `.env`, raw data, trained model binaries, logs, caches, or local databases.
- Add or update tests when behavior changes.
- Update README or docs when setup, workflow, or architecture changes.
- Keep trading behavior conservative: the system recommends `BUY`, `SELL`, or `WAIT`; it must not execute real trades.

## Commit Convention

Use Conventional Commits:

```text
<type>(optional-scope): <short summary>
```

Common types:

- `feat`: user-facing feature
- `fix`: bug fix
- `docs`: documentation only
- `test`: tests only
- `refactor`: code change without behavior change
- `chore`: tooling, Git, dependency, or maintenance change

Examples:

```text
feat(agents): add trading orchestrator pipeline
docs(git): document branch workflow
chore(git): initialize repository hygiene
```
