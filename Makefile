.PHONY: env

env:
	@if [ -f .env ]; then \
		read -p ".env file already exists. Do you want to overwrite it? (y/n): " answer; \
		if [ "$$answer" = "y" ] || [ "$$answer" = "yes" ]; then \
			echo "Creating .env file..."; \
			echo 'DYDX_ADDRESS = "dydx1ENTERYOURTESTADDRESS"' > .env; \
			echo 'SECRET_PHRASE = "word1 word2 word3 word4 word5 word6 word7 word8 word9 word10 word11 word12"' >> .env; \
			echo 'TELEGRAM_TOKEN = "5860211111:AAGABUQiYet-jI9txy20-hCEgt7NypNwUI"' >> .env; \
			echo 'TELEGRAM_CHAT_ID = "5236746578"' >> .env; \
			echo ".env file created successfully."; \
		else \
			echo "Operation cancelled."; \
		fi; \
	else \
		echo "Creating .env file..."; \
		echo 'DYDX_ADDRESS = "dydx1ENTERYOURTESTADDRESS"' > .env; \
		echo 'SECRET_PHRASE = "word1 word2 word3 word4 word5 word6 word7 word8 word9 word10 word11 word12"' >> .env; \
		echo 'TELEGRAM_TOKEN = "5860211111:AAGABUQiYet-jI9txy20-hCEgt7NypNwUI"' >> .env; \
		echo 'TELEGRAM_CHAT_ID = "5236746578"' >> .env; \
		echo ".env file created successfully."; \
	fi