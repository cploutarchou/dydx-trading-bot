.PHONY: env config

env:
	@echo "Note: Configuration is now managed through config.yaml. The .env file is no longer used."
	@if [ -f .env ]; then \
		read -p ".env file already exists. Do you want to overwrite it? (y/n): " answer; \
		if [ "$$answer"="y" ] || [ "$$answer"="yes" ]; then \
			echo "Creating .env file..."; \
			echo '# This file is kept for backward compatibility' > .env; \
			echo '# Configuration is now managed through config.yaml' >> .env; \
			echo '# Run `make config` to create or update config.yaml' >> .env; \
			echo ".env file created successfully."; \
		else \
			echo "Operation cancelled."; \
		fi; \
	else \
		echo "Creating .env file..."; \
		echo '# This file is kept for backward compatibility' > .env; \
		echo '# Configuration is now managed through config.yaml' >> .env; \
		echo '# Run `make config` to create or update config.yaml' >> .env; \
		echo ".env file created successfully."; \
	fi

create :
	@if [ -d app ]; then \
		CONFIG_DIR="app"; \
	else \
		CONFIG_DIR="."; \
	fi; \
	if [ -f $$CONFIG_DIR/config.yaml ]; then \
		read -p "config.yaml file already exists in $$CONFIG_DIR. Do you want to overwrite it? (y/n): " answer; \
		if [ "$$answer"="y" ] || [ "$$answer"="yes" ]; then \
			echo "Creating config.yaml file..."; \
			echo 'dydx:' > $$CONFIG_DIR/config.yaml; \
			echo '  dydx_chain_address: "dydx1ENTERYOURTESTADDRESS"' >> $$CONFIG_DIR/config.yaml; \
			echo '  dydx_secret_phrase: "word1 word2 word3 word4 word5 word6 word7 word8 word9 word10 word11 word12"' >> $$CONFIG_DIR/config.yaml; \
			echo '  is_testnet: false' >> $$CONFIG_DIR/config.yaml; \
			echo 'telegram:' >> $$CONFIG_DIR/config.yaml; \
			echo '  token: "5860211111:AAGABUQiYet-jI9txy20-hCEgt7NypNwUI"' >> $$CONFIG_DIR/config.yaml; \
			echo '  chat_id: "5236746578"' >> $$CONFIG_DIR/config.yaml; \
			echo 'botSettings:' >> $$CONFIG_DIR/config.yaml; \
			echo '  abortAllPositions: true' >> $$CONFIG_DIR/config.yaml; \
			echo '  findCointegratedPairs: true' >> $$CONFIG_DIR/config.yaml; \
			echo '  manageExits: true' >> $$CONFIG_DIR/config.yaml; \
			echo '  placeTrades: true' >> $$CONFIG_DIR/config.yaml; \
			echo '  resolutionTimeframe: "1HOUR"' >> $$CONFIG_DIR/config.yaml; \
			echo '  strategy: "cointegration"' >> $$CONFIG_DIR/config.yaml; \
			echo '  statsWindow: 21' >> $$CONFIG_DIR/config.yaml; \
			echo '  # Thresholds - Opening' >> $$CONFIG_DIR/config.yaml; \
			echo '  maxHalfLife: 24' >> $$CONFIG_DIR/config.yaml; \
			echo '  ZScoreThreshold: 1.5' >> $$CONFIG_DIR/config.yaml; \
			echo '  usdPerTrade: 10' >> $$CONFIG_DIR/config.yaml; \
			echo '  usdMinCollateral: 100' >> $$CONFIG_DIR/config.yaml; \
			echo '  # Thresholds - Closing' >> $$CONFIG_DIR/config.yaml; \
			echo '  closeAtZscoreCross: true' >> $$CONFIG_DIR/config.yaml; \
			echo '  indexer_endpoint:' >> $$CONFIG_DIR/config.yaml; \
			echo '    testnet: "https://indexer.v4testnet.dydx.exchange"' >> $$CONFIG_DIR/config.yaml; \
			echo '    mainnet: "https://indexer.dydx.trade"' >> $$CONFIG_DIR/config.yaml; \
			echo "config.yaml file created successfully in $$CONFIG_DIR."; \
		else \
			echo "Operation cancelled."; \
		fi; \
	else \
		echo "Creating config.yaml file..."; \
		echo 'dydx:' > $$CONFIG_DIR/config.yaml; \
		echo '  dydx_chain_address: "dydx1ENTERYOURTESTADDRESS"' >> $$CONFIG_DIR/config.yaml; \
		echo '  dydx_secret_phrase: "word1 word2 word3 word4 word5 word6 word7 word8 word9 word10 word11 word12"' >> $$CONFIG_DIR/config.yaml; \
		echo '  is_testnet: false' >> $$CONFIG_DIR/config.yaml; \
		echo 'telegram:' >> $$CONFIG_DIR/config.yaml; \
		echo '  token: "5860211111:AAGABUQiYet-jI9txy20-hCEgt7NypNwUI"' >> $$CONFIG_DIR/config.yaml; \
		echo '  chat_id: "5236746578"' >> $$CONFIG_DIR/config.yaml; \
		echo 'botSettings:' >> $$CONFIG_DIR/config.yaml; \
		echo '  abortAllPositions: true' >> $$CONFIG_DIR/config.yaml; \
		echo '  findCointegratedPairs: true' >> $$CONFIG_DIR/config.yaml; \
		echo '  manageExits: true' >> $$CONFIG_DIR/config.yaml; \
		echo '  placeTrades: true' >> $$CONFIG_DIR/config.yaml; \
		echo '  resolutionTimeframe: "1HOUR"' >> $$CONFIG_DIR/config.yaml; \
		echo '  strategy: "cointegration"' >> $$CONFIG_DIR/config.yaml; \
		echo '  statsWindow: 21' >> $$CONFIG_DIR/config.yaml; \
		echo '  # Thresholds - Opening' >> $$CONFIG_DIR/config.yaml; \
		echo '  maxHalfLife: 24' >> $$CONFIG_DIR/config.yaml; \
		echo '  ZScoreThreshold: 1.5' >> $$CONFIG_DIR/config.yaml; \
		echo '  usdPerTrade: 10' >> $$CONFIG_DIR/config.yaml; \
		echo '  usdMinCollateral: 100' >> $$CONFIG_DIR/config.yaml; \
		echo '  # Thresholds - Closing' >> $$CONFIG_DIR/config.yaml; \
		echo '  closeAtZscoreCross: true' >> $$CONFIG_DIR/config.yaml; \
		echo '  indexer_endpoint:' >> $$CONFIG_DIR/config.yaml; \
		echo '    testnet: "https://indexer.v4testnet.dydx.exchange"' >> $$CONFIG_DIR/config.yaml; \
		echo '    mainnet: "https://indexer.dydx.trade"' >> $$CONFIG_DIR/config.yaml; \
		echo "config.yaml file created successfully in $$CONFIG_DIR."; \
	fi
