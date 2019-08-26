install: in_virtual_env
	# use latest pip
	pip install --upgrade pip

	# install requirements
	pip install -r requirements.txt -c constraints.txt --src ./src --upgrade-strategy=eager

	# install custom extra requirements if present
	test -e extras.txt && pip install -r extras.txt -c constraints.txt --src ./src --upgrade-strategy=eager || true

	# remove install artifacts
	test -e src/pip-delete-this-directory.txt && rm src/pip-delete-this-directory.txt || true

	# fetch docs
	test -e docs/.git || git clone https://github.com/onegov/onegov-docs docs

	# ensure required folder structure
	mkdir -p ./profiles

	# gather eggs
	rm -rf ./eggs
	scrambler --target eggs

update: in_virtual_env if_all_committed if_all_on_master_branch

	# update sources
	find src -type d -maxdepth 1 -exec echo ""\; -exec echo "{}" \; -exec git --git-dir={}/.git --work-tree={} pull \;

	# update docs
	cd docs && git pull

	# updating all dependencies
	pip list --outdated --format=freeze |  sed 's/==/>/g' | pip install --upgrade -r /dev/stdin -c constraints.txt

	# install all dependencies, applying constraints
	make install

in_virtual_env:
	@if python -c 'import sys; (hasattr(sys, "real_prefix") or (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix)) and sys.exit(1) or sys.exit(0)'; then \
		echo "An active virtual environment is required"; exit 1; \
		else true; fi

if_all_committed:
	@ # pip has the nasty habit of overriding local changes when updating
	@ if uncommitted -nu src | grep -q Git; then \
		echo "Commit and push all your changes before updating"; exit 1; \
		else true; fi

if_all_on_master_branch:
	@ # pip will muck with the branches other than master in weird ways
	@ for repository in src/*; do \
    	if git -C "$${repository}" rev-parse --abbrev-ref HEAD | grep -vq master; then\
    		echo "$${repository} is not on the master branch";\
    		echo "Make sure all repositories are on the master branch before updating";\
    		exit 1;\
		fi; done

test: in_virtual_env
	find src -type d -maxdepth 1 \
		-not \( -path src/onegov-testing -prune \) \
		-not \( -path src/onegov.applications -prune \) \
		-print0 | xargs -n 1 -0 py.test
