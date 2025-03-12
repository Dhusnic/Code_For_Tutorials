from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext, MessageHandler, filters
import requests
from bs4 import BeautifulSoup

# ✅ Start Command
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "📊 Welcome to the Financial Advice Bot! 💰\n\n"
        "Use the following commands:\n"
        "💹 /investment - Investment Tips\n"
        "💵 /savings - Savings Advice\n"
        "🏛 /schemes - Govt Schemes\n"
        "📈 /market - Latest Market Updates\n"
    )

# ✅ Investment Advice
async def investment(update: Update, context: CallbackContext):
    advice = [
        "📌 Diversify your investments to reduce risk.",
        "📌 Start investing early to take advantage of compound interest.",
        "📌 Research before investing in stocks or mutual funds.",
        "📌 Avoid emotional trading and follow a strategy.",
        "📌 Consider index funds for long-term stability."
    ]
    await update.message.reply_text("\n".join(advice))

# ✅ Savings Tips
async def savings(update: Update, context: CallbackContext):
    tips = [
        "💰 Follow the 50/30/20 rule: 50% Needs, 30% Wants, 20% Savings.",
        "📈 Open a high-yield savings account for better returns.",
        "📉 Avoid unnecessary debts and high-interest loans.",
        "📝 Track your expenses regularly using a budget planner.",
        "🔄 Automate savings to ensure you save consistently."
    ]
    await update.message.reply_text("\n".join(tips))

# ✅ Govt Schemes (Web Scraping)
async def schemes(update: Update, context: CallbackContext):
    url = "https://www.india.gov.in/my-government/schemes"
    
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")

        scheme_list = soup.find_all("div", class_="views-field-title")
        schemes = [f"📌 {scheme.text.strip()}" for scheme in scheme_list[:5]]

        message = "🔥 Top Govt Schemes:\n\n" + "\n".join(schemes)
        await update.message.reply_text(message)
    except Exception as e:
        await update.message.reply_text("⚠ Error fetching government schemes. Please try again later.")

# ✅ Stock Market Updates (API)
async def market(update: Update, context: CallbackContext):
    stock_symbol = "TSLA"  # Change this for different stocks
    api_key = "YOUR_ALPHA_VANTAGE_API_KEY"  # Replace with your API key
    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={stock_symbol}&apikey={api_key}"
    
    try:
        response = requests.get(url).json()
        stock_price = response["Global Quote"]["05. price"]

        message = f"📈 {stock_symbol} Stock Price: ${stock_price}"
        await update.message.reply_text(message)
    except Exception as e:
        await update.message.reply_text("⚠ Error fetching stock market data. Please try again later.")

# ✅ Bot Setup
def main():
    TOKEN = "7554312899:AAGn7a8oWjw5P1ehaCO7__4iMolRd8ffoT4"  # Replace with your Telegram bot token

    # Create bot application
    app = Application.builder().token(TOKEN).build()

    # Register command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("investment", investment))
    app.add_handler(CommandHandler("savings", savings))
    app.add_handler(CommandHandler("schemes", schemes))
    app.add_handler(CommandHandler("market", market))

    print("📊 Financial Advice Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    main()
