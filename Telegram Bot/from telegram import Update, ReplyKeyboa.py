from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackContext
import requests
from bs4 import BeautifulSoup
from stocks.stocks import stock_list
import os
from forex_python.converter import CurrencyRates




class TelegramBot:
    # Define conversation states
    SELECT_STOCK, SHOW_MARKET = range(2)
    
    def __init__(self):
        self.stock_list = stock_list().stock_list
        currency_converter = CurrencyRates()
        self.TOKEN = os.getenv("TELEGRAM_TOKEN")  # Use environment variable for security
        symbol_to_name_map = self.create_symbol_to_name_map(stock_list)
        
    async def start(self, update: Update, context: CallbackContext):
        await update.message.reply_text(
            "Hey there! 👋 Welcome to the Financial Advice Bot! 💰\n\n"
            "Here’s what I can do for you:\n"
            "💹 /investment - Investment Tips\n"
            "💵 /savings - Smart Savings Advice\n"
            "🏛 /schemes - Latest Govt Schemes\n"
            "📈 /market - Get Live Market Updates\n"
        )

    async def investment(self, update: Update, context: CallbackContext):
        advice = [
            "📌 Diversify your investments to reduce risk.",
            "📌 Start investing early to take advantage of compound interest.",
            "📌 Research before investing in stocks or mutual funds.",
            "📌 Avoid emotional trading and follow a strategy.",
            "📌 Consider index funds for long-term stability."
        ]
        await update.message.reply_text("💡 Investment Tips:\n" + "\n".join(advice))

    async def savings(self, update: Update, context: CallbackContext):
        tips = [
            "💰 Follow the 50/30/20 rule: 50% Needs, 30% Wants, 20% Savings.",
            "📈 Open a high-yield savings account for better returns.",
            "📉 Avoid unnecessary debts and high-interest loans.",
            "📝 Track your expenses regularly using a budget planner.",
            "🔄 Automate savings to ensure consistency."
        ]
        await update.message.reply_text("💰 Smart Savings Tips:\n" + "\n".join(tips))

    async def schemes(self, update: Update, context: CallbackContext):
        url = "https://www.india.gov.in/my-government/schemes"
        try:
            response = requests.get(url)
            soup = BeautifulSoup(response.text, "html.parser")
            scheme_list = soup.find_all("div", class_="views-field-title")
            schemes = [f"📌 {scheme.text.strip()}" for scheme in scheme_list[:5]]
            message = "🔥 Latest Govt Schemes:\n\n" + "\n".join(schemes)
            await update.message.reply_text(message)
        except Exception:
            await update.message.reply_text("⚠ Oops! Couldn't fetch government schemes. Try again later.")

    async def stock_index(self, update: Update, context: CallbackContext) -> int:
        keyboard = [["NASDAQ", "S&P 500"], ["Dow Jones", "NIFTY 50"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        await update.message.reply_text("📊 Choose a stock index:", reply_markup=reply_markup)
        return self.SELECT_STOCK

    async def select_stock(self, update: Update, context: CallbackContext) -> int:
        user_choice = update.message.text
        if user_choice in self.stock_list:
            context.user_data["selected_index"] = user_choice
            stock_buttons = [[stock["name"] for stock in pair] for pair in self.stock_list[user_choice]]
            reply_markup = ReplyKeyboardMarkup(stock_buttons, one_time_keyboard=True)
            await update.message.reply_text(f"📈 Select a stock from {user_choice}:", reply_markup=reply_markup)
            return self.SHOW_MARKET
        else:
            await update.message.reply_text("❌ Invalid selection. Try /market again.")
            return ConversationHandler.END

    async def market(self, update: Update, context: CallbackContext) -> int:
        stock_symbol = update.message.text.upper()
        stock_symbol=symbol_to_name_map.get(stock_symbol, "Symbol not found")
        api_key = os.getenv("ALPHAVANTAGE_API_KEY")  # Store API key securely
        url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={stock_symbol}&apikey={api_key}"
        try:
            response = requests.get(url).json()
            stock_price = response.get("Global Quote", {}).get("05. price", "N/A")
            if stock_price == "N/A":
                raise ValueError("Invalid stock symbol or API error.")
            else:
                currency_converter=CurrencyRates()
                inr_amount = currency_converter.convert('USD', 'INR', stock_price)
            print(f"${stock_price} is approximately ₹{inr_amount:.2f}")
            message = f"📈 {stock_symbol} Stock Price: ₹ {inr_amount}"
            await update.message.reply_text(message)
        except Exception:
            await update.message.reply_text("⚠ Couldn't fetch stock data. Please try again later.")
        return ConversationHandler.END

    async def cancel(self, update: Update, context: CallbackContext) -> int:
        await update.message.reply_text("Action canceled. Let me know if you need anything else! 😊")
        return ConversationHandler.END

    def run(self):
        app = Application.builder().token(self.TOKEN).build()
        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(CommandHandler("investment", self.investment))
        app.add_handler(CommandHandler("savings", self.savings))
        app.add_handler(CommandHandler("schemes", self.schemes))

        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("market", self.stock_index)],
            states={
                self.SELECT_STOCK: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.select_stock)],
                self.SHOW_MARKET: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.market)]
            },
            fallbacks=[CommandHandler("cancel", self.cancel)]
        )
        app.add_handler(conv_handler)

        print("📊 Financial Advice Bot is running...")
        app.run_polling()
        
    def create_symbol_to_name_map(data):
        """
        Creates a dictionary for quick lookup of stock names based on symbols.
        """
        symbol_to_name = {}
        for stocks in data.values():
            for pair in stocks:
                for stock in pair:
                    symbol_to_name[stock["symbol"]] = stock["name"]
        return symbol_to_name
    
if __name__ == "__main__":
    bot = TelegramBot()
    bot.run()