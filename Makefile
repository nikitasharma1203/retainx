.PHONY: up down load profile dbt-build dbt-test test churn backtest clv

up:
	docker compose up -d

down:
	docker compose down

# usage: make load FILE=data/raw/online_retail_II.xlsx
load:
	python scripts/load_raw.py $(FILE)

# usage: make profile FILE=data/raw/online_retail_II.xlsx
profile:
	python scripts/profile_data.py $(FILE)

dbt-build:
	cd dbt && dbt build --profiles-dir .

dbt-test:
	cd dbt && dbt test --profiles-dir .

test:
	pytest -q

churn:
	python -m src.models.churn --train-cutoff 2010-06-01 --test-cutoff 2010-12-01

backtest:
	python -m src.eval.backtest --task churn

clv:
	python -m src.models.clv --calibration-end 2010-12-01 --observation-end 2011-12-01
