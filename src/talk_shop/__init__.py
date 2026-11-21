"""Shop chatbot application."""

import argparse
import logging
from pathlib import Path
from typing import Dict, Optional

from lark import Lark, UnexpectedInput

CATALOG: Dict[str, Dict[str, float | int]] = {
    "apple": {"price": 2.99, "stock": 12},
    "bread": {"price": 5.49, "stock": 4},
    "milk": {"price": 3.25, "stock": 0},
    "coffee": {"price": 18.0, "stock": 7},
}


def normalize_text(text: str) -> str:
    """Normalize user input by trimming and lowering case."""
    return " ".join(text.lower().strip().split())


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


def find_item_name(question: str) -> Optional[str]:
    """Find the product name mentioned in the user question."""
    text = normalize_text(question)

    for item in CATALOG:
        if item in text:
            return item

    return None


def answer_question(question: str, grammar: Lark, logger: logging.Logger) -> str:
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
            "'how much does apple cost?', "
            "'is milk in stock?', "
            "'how many apples are in stock?'"
        )

    item = find_item_name(text)
    if item is None:
        logger.warning("Unrecognized product in question: %s", text)
        return "I could not recognize the product name."

    result = "I can answer only about price and stock availability."

    if "price" in text or "cost" in text or "how much" in text:
        result = f"{item.capitalize()} costs {CATALOG[item]['price']:.2f} PLN."
    elif "stock" in text or "in stock" in text or "available" in text or "do we have" in text:
        stock = CATALOG[item]["stock"]
        if stock > 0:
            result = f"Yes, {item} is in stock. There are {stock} items available."
        else:
            result = f"No, {item} is currently out of stock."
    elif "how many" in text:
        result = f"There are {CATALOG[item]['stock']} {item}(s) in stock."

    logger.info("Question: %s -> Answer: %s", text, result)
    return result


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

        logger.info("User asked: %s", text)

        try:
            response = answer_question(text, grammar, logger)
        except (ValueError, TypeError, KeyError, OSError):
            logger.exception("Unexpected error while processing question: %s", text)
            response = "Something went wrong while processing your question. Please try again."

        print(f"Bot: {response}")