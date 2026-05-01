# Harness Commands

This is the canonical command registry for living project workflow docs and deploy configuration.

## Local Commands

Run the app:

```bash
.venv/bin/python main.py
```

Run the full test suite:

```bash
.venv/bin/pytest
```

Run advisory harness diagnostics:

```bash
.venv/bin/python scripts/harness/check_docs.py
```

Run advisory financial invariant diagnostics:

```bash
.venv/bin/python scripts/harness/check_financial_invariants.py
```

Run local CI-equivalent harness verification:

```bash
.venv/bin/python scripts/harness/verify.py --ci
```

## Railway Commands

Railway CI harness command:

```bash
python scripts/harness/verify.py --ci
```

Railway pytest command:

```bash
pytest
```

Railway build command:

```bash
pip install -r requirements.txt && python scripts/harness/verify.py --ci && pytest
```

Railway start command:

```bash
python main.py
```
