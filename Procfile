web: sh -c "MALLOC_ARENA_MAX=2 uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --limit-concurrency 25 --no-access-log --timeout-keep-alive 5"
