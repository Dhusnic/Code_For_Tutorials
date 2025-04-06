from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackContext,ContextTypes
import requests
from bs4 import BeautifulSoup
from stocks.stocks import stock_list
import os
from forex_python.converter import CurrencyRates
from investment_calculators.investment_calculator import Investment_Calculator

class TelegramBot:
    # Define conversation states
    SELECT_STOCK, SHOW_MARKET = range(2)
    SELECT_INVESTMENT_CALCULATOR,ACTIVATE_CALCULATOR=range(2)
    INVESTMENT_CALC=''
    Investment_Calculator_OPTIONS=Investment_Calculator.INVESTMENT_CALCLATOR_OPTIONS
    Investment_Calculator=Investment_Calculator()
    def __init__(self):
        self.stock_list = stock_list().stock_list
        self.currency_converter = CurrencyRates()
        self.TOKEN = os.getenv("TELEGRAM_TOKEN")  # Use environment variable for security
        self.symbol_to_name_map = self.create_symbol_to_name_map(self.stock_list)
        
    async def start(self, update: Update, context: CallbackContext):
        await update.message.reply_text(
            "Hey there! 👋 Welcome to the Financial Advice Bot! 💰\n\n"
            "Here's what I can do for you:\n"
            "💹 /investment - Investment Tips\n"
            "💵 /savings - Smart Savings Advice\n"
            "🏛 /schemes - Latest Govt Schemes\n"
            "📈 /market - Get Live Market Updates\n"
            "/investment_calculators - Get Investment Calculators"
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
        keyboard = [["Sensex"], ["NIFTY 50"]]
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
        stock_name = update.message.text
        # Find the symbol for the selected stock name
        stock_symbol = None
        for symbol, name in self.symbol_to_name_map.items():
            if name == stock_name:
                stock_symbol = symbol
                break
                
        if not stock_symbol:
            await update.message.reply_text("❌ Stock symbol not found.")
            return ConversationHandler.END
            
        api_key = os.getenv("ALPHAVANTAGE_API_KEY")  # Store API key securely
        url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={stock_symbol}&apikey={api_key}"
        try:
            response = requests.get(url).json()
            stock_price = response.get("Global Quote", {}).get("05. price", "N/A")
            if stock_price == "N/A":
                raise ValueError("Invalid stock symbol or API error.")
            else:
                stock_price = float(stock_price)
                # inr_amount = self.convert_currency("USD", "INR", stock_price)
                message = f"📈 {stock_name} ({stock_symbol}) Stock Price: ₹{stock_price:.2f}"
                await update.message.reply_text(message)
        except Exception as e:
            await update.message.reply_text(f"⚠ Couldn't fetch stock data: {str(e)}")
        return ConversationHandler.END
    
    def create_symbol_to_name_map(self, data):
        """
        Creates a dictionary for quick lookup of stock names based on symbols.
        """
        symbol_to_name = {}
        for index_name, stocks in data.items():
            for pair in stocks:
                for stock in pair:
                    symbol_to_name[stock["symbol"]] = stock["name"]
        return symbol_to_name
    
    def convert_currency(self,from_currency, to_currency, amount):
        params = {
            "function": "CURRENCY_EXCHANGE_RATE",
            "from_currency": from_currency,
            "to_currency": to_currency,
            "apikey": os.getenv("ALPHAVANTAGE_API_KEY")
        }
        BASE_URL = "https://www.alphavantage.co/query"
        try:
            response = requests.get(BASE_URL, params=params)
            data = response.json()
            
            if "Realtime Currency Exchange Rate" in data:
                exchange_rate = float(data["Realtime Currency Exchange Rate"]["5. Exchange Rate"])
                converted_amount = exchange_rate * amount
                return converted_amount
            else:
                return "⚠ Error: Invalid API response. Check your API key or request limit."

        except Exception as e:
            return f"⚠ Error fetching exchange rate: {e}"

    
    
    async def investment_calculators(self,update:Update,context: CallbackContext):
        keyboard = self.create_Keyboard_Options(self.Investment_Calculator_OPTIONS,2)
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        await update.message.reply_text("📊 Choose a stock index:", reply_markup=reply_markup)
        return self.SELECT_INVESTMENT_CALCULATOR
    
    # async def select_investment_calculators(self, update: Update, context: CallbackContext):
    #     user_input = update.message.text  # Assume user selects a calculator
    #     invest_calc_key=self.Investment_Calculator_OPTIONS.get(user_input)
    #     calculator_func = Investment_Calculator.calculators.get(invest_calc_key)

    #     if calculator_func:
    #         context.user_data['active_calc_func'] = calculator_func  # Store function reference
    #         await update.message.reply_text(f"Selected calculator: {user_input}. Now enter values.")
    #         return self.ACTIVATE_CALCULATOR  # Move to the next state
    #     else:
    #         await update.message.reply_text("Invalid selection. Please try again.")
    #         return self.SELECT_INVESTMENT_CALCULATOR
    
    async def select_investment_calculators(self, update, context):
        user_choice = update.message.text
        context.user_data["selected_calculator"] = user_choice  # Store choice
        await update.message.reply_text(f"You selected {user_choice}. Now, please provide input values.")
        return self.ACTIVATE_CALCULATOR
    
    async def dynamic_calculator_handler(self, update, context):
        user_choice = context.user_data.get("selected_calculator")

        # Mapping investment types to functions
        investment_functions = {
            "Simple Intrest": self.calculate_simple_interest,
            "Compound Interest": Investment_Calculator.calculate_compound_interest,
            "ROI": Investment_Calculator.calculate_roi
        }

        if user_choice in investment_functions:
            return investment_functions[user_choice](update, context)  # Call the correct function
        else:
            await update.message.reply_text("Invalid investment type selected. Please choose again.")
            return self.SELECT_INVESTMENT_CALCULATOR
        
        
    async def calculate_simple_interest(self,update: Update, context: CallbackContext):
        user_text = update.message.text
        user_data = context.user_data  # Persistent user data

        if "step" not in user_data:
            user_data["step"] = "ask_principal"
            await update.message.reply_text("Enter the Principal Amount:")
            return self.ACTIVATE_CALCULATOR  # Continue in the same state

        elif user_data["step"] == "ask_principal":
            try:
                user_data["principal"] = float(user_text)
                user_data["step"] = "ask_rate"
                await update.message.reply_text("Enter the Annual Interest Rate (in %):")
            except ValueError:
                await update.message.reply_text("❌ Invalid input. Please enter a numeric value for Principal Amount.")
            return self.ACTIVATE_CALCULATOR  # Keep the conversation active

        elif user_data["step"] == "ask_rate":
            try:
                user_data["rate"] = float(user_text)
                user_data["step"] = "ask_time"
                await update.message.reply_text("Enter the Time Period (in years):")
            except ValueError:
                await update.message.reply_text("❌ Invalid input. Please enter a numeric value for Interest Rate.")
            return self.ACTIVATE_CALCULATOR  

        elif user_data["step"] == "ask_time":
            try:
                user_data["time"] = float(user_text)

                # Calculate simple interest
                principal = user_data["principal"]
                rate = user_data["rate"]
                time = user_data["time"]
                interest = (principal * rate * time) / 100
                total_amount = principal + interest

                # Send results
                result_message = (
                    f"💰 Investment Summary:\n"
                    f"📌 Principal Amount: ₹{principal:.2f}\n"
                    f"📌 Annual Interest Rate: {rate}%\n"
                    f"📌 Time Period: {time} years\n"
                    f"📈 Earned Interest: ₹{interest:.2f}\n"
                    f"💵 Total Amount after {time} years: ₹{total_amount:.2f}"
                )
                await update.message.reply_text(result_message)

                # Reset conversation after response
                user_data.clear()
                return ConversationHandler.END  # End conversation

            except ValueError:
                await update.message.reply_text("❌ Invalid input. Please enter a numeric value for Time Period.")
                return self.ACTIVATE_CALCULATOR    # Exit early

    async def calculate_compound_interest(update: Update, context: CallbackContext):
        user_text = update.message.text
        user_data = context.user_data  # Persistent user data

        if "step" not in user_data:
            user_data["step"] = "ask_principal"
            await update.message.reply_text("Enter the Principal Amount:")
            return

        elif user_data["step"] == "ask_principal":
            try:
                user_data["principal"] = float(user_text)
                user_data["step"] = "ask_rate"
                await update.message.reply_text("Enter the Annual Interest Rate (in %):")
            except ValueError:
                await update.message.reply_text("❌ Invalid input. Please enter a numeric value for Principal Amount.")
                return

        elif user_data["step"] == "ask_rate":
            try:
                user_data["rate"] = float(user_text)
                user_data["step"] = "ask_time"
                await update.message.reply_text("Enter the Time Period (in years):")
            except ValueError:
                await update.message.reply_text("❌ Invalid input. Please enter a numeric value for Interest Rate.")
                return

        elif user_data["step"] == "ask_time":
            try:
                user_data["time"] = float(user_text)
                user_data["step"] = "ask_frequency"
                await update.message.reply_text("Enter the number of times interest is compounded per year:")
            except ValueError:
                await update.message.reply_text("❌ Invalid input. Please enter a numeric value for Time Period.")
                return

        elif user_data["step"] == "ask_frequency":
            try:
                user_data["frequency"] = int(user_text)

                # Calculate compound interest
                principal = user_data["principal"]
                rate = user_data["rate"] / 100
                time = user_data["time"]
                n = user_data["frequency"]
                amount = principal * (1 + (rate / n))**(n * time)
                interest = amount - principal

                # Send results
                result_message = (
                    f"💰 Investment Summary:\n"
                    f"📌 Principal Amount: ₹{principal:.2f}\n"
                    f"📌 Annual Interest Rate: {user_data['rate']}%\n"
                    f"📌 Time Period: {time} years\n"
                    f"📌 Compounded {n} times per year\n"
                    f"📈 Earned Interest: ₹{interest:.2f}\n"
                    f"💵 Total Amount after {time} years: ₹{amount:.2f}"
                )
                await update.message.reply_text(result_message)
                user_data.clear()
                return

            except ValueError:
                await update.message.reply_text("❌ Invalid input. Please enter a numeric value for compounding frequency.")
                return

    async def calculate_roi(update: Update, context: CallbackContext):
        user_text = update.message.text
        user_data = context.user_data  # Persistent user data

        if "step" not in user_data:
            user_data["step"] = "ask_initial_investment"
            await update.message.reply_text("Enter the Initial Investment Amount:")
            return

        elif user_data["step"] == "ask_initial_investment":
            try:
                user_data["initial_investment"] = float(user_text)
                user_data["step"] = "ask_final_value"
                await update.message.reply_text("Enter the Final Investment Value:")
            except ValueError:
                await update.message.reply_text("❌ Invalid input. Please enter a numeric value for Initial Investment.")
                return

        elif user_data["step"] == "ask_final_value":
            try:
                user_data["final_value"] = float(user_text)

                # Calculate ROI
                initial = user_data["initial_investment"]
                final = user_data["final_value"]
                roi = ((final - initial) / initial) * 100

                # Send results
                result_message = (
                    f"📊 Return on Investment (ROI):\n"
                    f"📌 Initial Investment: ₹{initial:.2f}\n"
                    f"📌 Final Value: ₹{final:.2f}\n"
                    f"📈 ROI: {roi:.2f}%"
                )
                await update.message.reply_text(result_message)
                user_data.clear()
                return
            except ValueError:
                await update.message.reply_text("❌ Invalid input. Please enter a numeric value for Final Investment Value.")
                return



    async def cancel(self, update: Update, context: CallbackContext) -> int:
        await update.message.reply_text("Action canceled. Let me know if you need anything else! 😊")
        return ConversationHandler.END
        
    def create_Keyboard_Options(self,data_dict, size):
        keys = list(data_dict.keys())
        nested_list = []
        
        for i in range(0, len(keys), size):
            chunk = keys[i:i + size]
            nested_list.append(chunk)
        
        # If the last chunk is incomplete
        if len(nested_list[-1]) < size:
            nested_list[-1].append("incomplete list")
        
        return nested_list


    def run(self):
        app = Application.builder().token(self.TOKEN).build()
        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(CommandHandler("investment", self.investment))
        app.add_handler(CommandHandler("savings", self.savings))
        app.add_handler(CommandHandler("schemes", self.schemes))
        invest_conv_handler = ConversationHandler(
            entry_points=[CommandHandler('investment_calculators', self.investment_calculators)],
            states={
                self.SELECT_INVESTMENT_CALCULATOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.select_investment_calculators)],
                self.ACTIVATE_CALCULATOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dynamic_calculator_handler)]  # Use a generic function
            },
            fallbacks=[CommandHandler("cancel", self.cancel)]
        )
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("market", self.stock_index)],
            states={
                self.SELECT_STOCK: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.select_stock)],
                self.SHOW_MARKET: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.market)]
            },
            fallbacks=[CommandHandler("cancel", self.cancel)]
        )
        app.add_handler(invest_conv_handler)
        app.add_handler(conv_handler)
        print("📊 Financial Advice Bot is running...")
        app.run_polling()
    
if __name__ == "__main__":
    bot = TelegramBot()
    bot.run()