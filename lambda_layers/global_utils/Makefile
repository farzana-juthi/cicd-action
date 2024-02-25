build-GlobalUtils:
	echo "Global layers build started"
	pip install --default-timeout=100 -r ./python/requirements.txt -t $(ARTIFACTS_DIR)/python
	echo "Global layers build completed"
	cp -r ./python $(ARTIFACTS_DIR)/