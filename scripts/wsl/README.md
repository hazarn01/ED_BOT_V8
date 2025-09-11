# WSL Helpers

Run these inside Ubuntu 22.04 WSL.

- Install ingestion deps:
```
bash scripts/wsl/install_ingestion_deps.sh
```

- Single document ingestion test:
```
bash scripts/wsl/single_ingest_example.sh "/mnt/d/Dev/EDbotv8/docs/STEMI Activation.pdf" protocol
```

- Full corpus seed:
```
bash scripts/wsl/seed_corpus.sh /mnt/d/Dev/EDbotv8/docs 10
```

- Validation only:
```
bash scripts/wsl/validate_only.sh /mnt/d/Dev/EDbotv8/docs
```
