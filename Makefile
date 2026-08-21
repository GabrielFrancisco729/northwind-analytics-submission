.PHONY: build analyze dashboard all test clean

build:
	python run_pipeline.py

test:
	python tests/run_tests.py

analyze: build
	python analysis/engagement_recommendation.py
	python analysis/pipeline_forecast.py

dashboard: analyze
	python dashboard/build_dashboard.py

all: dashboard

clean:
	rm -f warehouse/northwind.db
	rm -f outputs/*.csv outputs/*.json outputs/*.txt
	rm -f dashboard/index.html dashboard/screenshots/dashboard_cro.png dashboard/screenshots/dashboard_sales_manager.png
