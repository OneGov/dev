install: in_virtual_env
	# install requirements
	pip install -r requirements.txt -c constraints.txt --src ./src

	# install custom extra requirements if present
	test -e extras.txt && pip install -r extras.txt -c constraints.txt --src ./src || true

	# remove install artifacts
	test -e src/pip-delete-this-directory.txt && rm src/pip-delete-this-directory.txt || true

	# fetch docs
	test -e docs/.git || git clone https://github.com/onegov/onegov-docs docs

	# ensure folder structure
	mkdir -p ./depot-storage
	mkdir -p ./file-storage
	mkdir -p ./profiles

	# gather eggs
	scrambler --target eggs

update: in_virtual_env
	# update sources
	find src -type d -depth 1 -exec git --git-dir={}/.git --work-tree={} pull origin master \;

	# update docs
	cd docs && git pull

	# updating all dependencies, ignoring constraints
	pip-review --auto

	# install all dependencies, applying constraints
	make install

in_virtual_env:
	@if python -c 'import sys; hasattr(sys, "real_prefix") and sys.exit(1) or sys.exit(0)'; then \
		echo "An active virtual environment is required"; exit 1; \
		else true; fi

test: in_virtual_env
	find src -type d -depth 1 \
		-not \( -path src/onegov-testing -prune \) \
		-not \( -path src/onegov.applications -prune \) \
		-print0 | xargs -n 1 -0 py.test
