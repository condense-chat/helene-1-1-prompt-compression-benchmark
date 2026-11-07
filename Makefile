.PHONY: all results figures clean

all: results figures

results:
	python scripts/reproduce.py

figures: results
	python scripts/make_figures.py

clean:
	rm -f results/*.csv results/*.json results/RESULTS.md
