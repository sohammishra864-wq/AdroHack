.PHONY: setup models smoke test eval calibrate heads arena bench demo api
setup:
	pip install -r requirements.txt
models:
	python scripts/setup/download_models.py
smoke:
	python scripts/smoke_bedrock.py
test:
	pytest -q
eval:
	python scripts/eval.py --out reports/eval_latest.md
calibrate:
	python scripts/eval.py --calibrate --out reports/eval_latest.md
heads:
	python scripts/train_heads.py
arena:
	python -m claimshield.arena.run
bench:
	python scripts/bench.py --files data/bench --runs 20 --out reports/latency_latest.md
demo:
	streamlit run claimshield/ui/app.py
api:
	uvicorn claimshield.api:app --port 8000
