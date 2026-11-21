"""Shop chatbot application."""

import argparse
import logging
import re
import sqlite3
from pathlib import Path
from typing import Optional

from lark import Lark, UnexpectedInput

from .database import ProductDatabase

def normalize_text(text: str) -> str:
    """Normalize user input by trimming, lowering case, and removing punctuation."""
    text = text.lower().strip()
    text = re.sub(r"[?.!,;:]", "", text)
    return " ".join(text.split())


def configure_logging(log_file: str, log_level: str) -> logging.Logger:
    """Configure logging to a chosen file and level."""
    log_path = Path(log_file)
    if log_path.parent != Path("."):
        log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("talk_shop")
    logger.setLevel(getattr(logging, log_level.upper()))
    logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger


def load_grammar(grammar_path: str) -> Lark:
    """Load the grammar from a separate file."""
    path = Path(grammar_path)

    if not path.exists():
        raise FileNotFoundError(f"Grammar file not found: {grammar_path}")

    try:
        grammar_content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Could not read grammar file: {exc}") from exc

    try:
        return Lark(grammar_content, parser="lalr", start="start")
    except ValueError as exc:
        raise RuntimeError(f"Invalid grammar: {exc}") from exc


def find_item_name(question: str, database: ProductDatabase) -> Optional[str]:
    """Find a product name mentioned in the user's question."""
    text = normalize_text(question)

    for product in database.list_products():
        name = normalize_text(product.name)
        if re.search(rf"\b{re.escape(name)}s?\b", text):
            return product.name

    return None


def answer_question(question: str, grammar: Lark, logger: logging.Logger, database: ProductDatabase,
                    ) -> str:
    """Answer a question about product price or stock."""
    text = normalize_text(question)

    if not text:
        logger.warning("Received empty question.")
        return "Empty question. Please ask about a product price or stock."

    if text == "end":
        logger.info("User ended the conversation.")
        raise ValueError("END")

    try:
        grammar.parse(text)
    except UnexpectedInput:
        logger.warning("Could not parse input: %s", text)
        return (
            "I did not understand the question. Try examples like: "
            "'How much does apple cost?', "
            "'Is milk in stock?', "
            "'How many apples are in stock?'"
        )

    item = find_item_name(text, database)
    if item is None:
        logger.warning("Unrecognized product in question: %s", text)
        return "I could not recognize the product name."

    product = database.find_product(item)
    if product is None:
        return "I could not find that product."

    if "how many" in text:
        result = f"There are {product.stock} {product.name}(s) in stock."
    elif "price" in text or "cost" in text or "how much" in text:
        result = f"{product.name.capitalize()} costs {product.price:.2f} PLN."
    elif "stock" in text or "available" in text or "do we have" in text:
        if product.stock > 0:
            result = (
                f"Yes, {product.name} is in stock. "
                f"There are {product.stock} items available."
            )
        else:
            result = f"No, {product.name} is currently out of stock."
    else:
        result = "I can answer only about price and stock availability."

    logger.info("Question: %s -> Answer: %s", text, result)
    return result

def admin_menu(database: ProductDatabase, logger: logging.Logger) -> None:
    """Manage products from the administrator menu."""
    while True:
        print("\n--- Administrator Menu ---")
        print("1. Add product")
        print("2. Find product")
        print("3. Update product")
        print("4. Delete product")
        print("5. List products")
        print("6. Clear database")
        print("7. Return to chat")

        choice = input("Choose an option: ").strip()

        if choice == "1":
            try:
                name = input("Product name: ").strip()
                price = float(input("Price in PLN: "))
                stock = int(input("Stock quantity: "))
                database.add_product(name, price, stock)
                logger.info("Added product: %s", name)
                print("Product added.")
            except (ValueError, sqlite3.IntegrityError) as exc:
                print(f"Invalid input: {exc}")

        elif choice == "2":
            name = input("Product name: ").strip()
            product = database.find_product(name)

            if product is None:
                print("Product not found.")
            else:
                print(
                    f"{product.name}: {product.price:.2f} PLN, "
                    f"stock: {product.stock}"
                )

        elif choice == "3":
            old_name = input("Current product name: ").strip()
            product = database.find_product(old_name)

            if product is None:
                print("Product not found.")
                continue

            try:
                new_name = input("New product name: ").strip()
                price = float(input("New price in PLN: "))
                stock = int(input("New stock quantity: "))
                changed = database.update_product(
                    old_name, new_name, price, stock
                )

                if changed:
                    logger.info("Updated product: %s", old_name)
                    print("Product updated.")
                else:
                    print("Product not found.")
            except (ValueError, sqlite3.IntegrityError) as exc:
                print(f"Invalid input: {exc}")

        elif choice == "4":
            name = input("Product name to delete: ").strip()
            product = database.find_product(name)

            if product is None:
                print("Product not found.")
                continue

            confirmation = input(
                f"Delete {product.name}? Type YES to confirm: "
            ).strip()

            if confirmation.upper() == "YES":
                database.delete_product(name)
                logger.info("Deleted product: %s", name)
                print("Product deleted.")
            else:
                print("Deletion cancelled.")

        elif choice == "5":
            products = database.list_products()

            if not products:
                print("No products found.")
            else:
                for product in products:
                    print(
                        f"{product.name}: {product.price:.2f} PLN, "
                        f"stock: {product.stock}"
                    )

        elif choice == "6":
            confirmation = input(
                "Clear the entire database? Type YES to confirm: "
            ).strip()

            if confirmation.upper() == "YES":
                database.clear_products()
                logger.info("Cleared the product database.")
                print("Database cleared.")
            else:
                print("Database clearing cancelled.")

        elif choice == "7":
            return

        else:
            print("Invalid option. Choose a number from 1 to 7.")
def main() -> None:
    """Run the chatbot loop."""
    parser = argparse.ArgumentParser(description="Shop chatbot")
    parser.add_argument(
        "-g",
        "--grammar",
        required=True,
        help="Path to the grammar.txt file",
    )
    parser.add_argument(
        "-l",
        "--log-file",
        default="talk_shop.log",
        help="File where logs will be saved (for example: logs/talk_shop.log)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Logging level",
    )
    args = parser.parse_args()

    logger = configure_logging(args.log_file, args.log_level)
    logger.info("Starting Talk Shop application.")
    logger.info("Grammar file: %s", args.grammar)
    logger.info("Log level: %s", args.log_level)

    try:
        grammar = load_grammar(args.grammar)
    except (FileNotFoundError, RuntimeError) as exc:
        logger.error("Failed to load grammar: %s", exc)
        print(f"Error: {exc}")
        return

    database = ProductDatabase(
        Path(__file__).resolve().parents[2] / "talk_shop.db"
    )

    try:
        database.initialize()

        if not database.list_products():
            for name, price, stock in (
                ("apple", 2.99, 12),
                ("bread", 5.49, 4),
                ("milk", 3.25, 0),
                ("coffee", 18.0, 7),
            ):
                database.add_product(name, price, stock)
    except (OSError, ValueError) as exc:
        logger.exception("Failed to initialize the product database.")
        print(f"Error initializing product database: {exc}")
        return

    print("Welcome to Talk Shop!")
    print("Type END to finish the conversation.")

    while True:
        try:
            user_input = input("You: ")
        except EOFError:
            logger.info("Input closed by EOF.")
            print("Input closed. Goodbye!")
            return
        except KeyboardInterrupt:
            logger.info("Program interrupted by user.")
            print("Interrupted. Goodbye!")
            return

        text = user_input.strip()

        if not text:
            logger.warning("User entered empty input.")
            print("Bot: Empty input. Please try again.")
            continue

        if text.lower() == "end":
            logger.info("User chose to end the conversation.")
            print("Bot: Goodbye!")
            break

        if text.lower() == "admin":
            admin_menu(database, logger)
            continue

        logger.info("User asked: %s", text)

        try:
            response = answer_question(text, grammar, logger, database)
        except (ValueError, TypeError, KeyError, OSError):
            logger.exception(
                "Unexpected error while processing question: %s", text
            )
            response = (
                "Something went wrong while processing your question. "
                "Please try again."
            )

        print(f"Bot: {response}")