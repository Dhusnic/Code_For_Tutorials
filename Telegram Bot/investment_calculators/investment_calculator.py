import math
from telegram import Update
from telegram.ext import CallbackContext, ConversationHandler,MessageHandler,filters,ContextTypes
class Investment_Calculator:
    async def calculate_simple_interest(update: Update, context: CallbackContext):
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
                return  # Exit early

        elif user_data["step"] == "ask_rate":
            try:
                user_data["rate"] = float(user_text)
                user_data["step"] = "ask_time"
                await update.message.reply_text("Enter the Time Period (in years):")
            except ValueError:
                await update.message.reply_text("❌ Invalid input. Please enter a numeric value for Interest Rate.")
                return  # Exit early

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
                return None  # Indicate end of conversation

            except ValueError:
                await update.message.reply_text("❌ Invalid input. Please enter a numeric value for Time Period.")
                return  # Exit early

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

    INVESTMENT_CALCLATOR_OPTIONS={
        "Simple Intrest":"simple_interest",
        "Compound Interest":"compound_interest",
        "ROI" : "roi"
    }
    calculators = {
        "simple_interest": calculate_simple_interest,
        "compound_interest": calculate_compound_interest,
        "roi": calculate_roi,
    }