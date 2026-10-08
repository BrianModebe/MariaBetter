"""
UAE Finance Pro Chatbot -- web UI.

Run:
    python app.py

Then open http://127.0.0.1:5000 in a browser -- this is static/app.html,
the SimpleBit merchant dashboard (Home/Payments/Payment detail), with Maria
reachable via the header icon as a slide-over panel embedding
static/maria.html. The original plain chat UI (static/index.html) still
exists unchanged, just no longer the default landing page -- open it
directly at /static/index.html. Either page lets you chat with any backend
from a dropdown:
    - "claude" -- rag_chatbot.RAGChatbot, needs ANTHROPIC_API_KEY (.env)
    - "gemini" -- gemini_chatbot.GeminiRAGChatbot, needs GEMINI_API_KEY (.env)
    - "local"  -- local_chatbot.LocalRAGChatbot, needs Ollama running
                  (see main_local.py)

Same retrieval + tool-calling pipeline as the CLI versions, just served
over HTTP. Each browser tab gets its own server-side chatbot instance
(keyed by a session id), so conversation history doesn't leak between
tabs/users. Sessions live in memory only and reset if the server restarts
-- fine for local/personal use, not meant for multi-user production.
"""

import os
import uuid

from flask import Flask, jsonify, request, send_from_directory

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional; env vars can be set another way

import csv_tools
import payments_data
import predictions
import savings_goal
from documents import DocumentStore, UploadError
from rag_chatbot import RAGChatbot
from local_chatbot import LocalRAGChatbot
from gemini_chatbot import GeminiRAGChatbot

app = Flask(__name__, static_folder="static")
# One upload can be up to 25 MB (the per-type limits in documents.py are tighter: 20 MB PDF, 10 MB CSV).
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024

BACKENDS = {"claude", "local", "gemini"}
DEFAULT_LOCAL_MODEL = "uae-finance-bot"

# session_id -> chatbot instance
SESSIONS = {}
# session_id -> the PDF/CSV files uploaded to that chat (in memory only, like SESSIONS)
DOCS = {}


def _check_local_ready(model: str):
    import ollama

    try:
        available = {m["model"] for m in ollama.Client().list()["models"]}
    except Exception as exc:
        return f"Could not reach Ollama ({exc}). Install it from https://ollama.com and make sure it's running."

    if not any(m == model or m.startswith(model + ":") for m in available):
        if model == "uae-finance-bot":
            return "Model 'uae-finance-bot' hasn't been built yet. Run `ollama create uae-finance-bot -f Modelfile` and try again."
        if model == "uae-finance-bot-tuned":
            return (
                "Model 'uae-finance-bot-tuned' hasn't been built yet. Put uae-finance-bot-tuned.gguf in the project "
                "folder and run `ollama create uae-finance-bot-tuned -f Modelfile.tuned` (see finetune/README.md)."
            )
        return f"Model '{model}' isn't pulled yet. Run `ollama pull {model}` and try again."

    return None


def _make_bot(backend: str):
    if backend == "claude":
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Add it to your .env file (see .env.example) to use this backend."
            )
        return RAGChatbot()

    if backend == "gemini":
        if not os.environ.get("GEMINI_API_KEY"):
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Add it to your .env file (see .env.example) to use this backend."
            )
        return GeminiRAGChatbot()

    if backend == "local":
        error = _check_local_ready(DEFAULT_LOCAL_MODEL)
        if error:
            raise RuntimeError(error)
        return LocalRAGChatbot(model=DEFAULT_LOCAL_MODEL)

    raise ValueError(f"Unknown backend '{backend}'")


@app.route("/")
def index():
    # Dashboard mode (Home/Payments/Maria) is the default landing page now --
    # the original plain chat UI is still there unchanged, just no longer at
    # "/": reachable directly at /static/index.html.
    return send_from_directory(app.static_folder, "app.html")


@app.route("/api/session", methods=["POST"])
def new_session():
    data = request.get_json(silent=True) or {}
    backend = data.get("backend", "claude")

    if backend not in BACKENDS:
        return jsonify({"error": f"Unknown backend '{backend}'"}), 400

    try:
        bot = _make_bot(backend)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400

    session_id = str(uuid.uuid4())
    SESSIONS[session_id] = bot
    return jsonify({"session_id": session_id, "backend": backend})


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    message = (data.get("message") or "").strip()

    bot = SESSIONS.get(session_id)
    if bot is None:
        return jsonify({"error": "Session not found -- refresh the page to start a new one."}), 404
    if not message:
        return jsonify({"error": "Empty message."}), 400

    # Charts, totals and rankings for an uploaded CSV are computed by code, not by the model.
    store = DOCS.get(session_id)
    if store:
        result = csv_tools.try_answer(store, message)
        if result:
            bot.history.append({"role": "user", "content": message})
            bot.history.append({"role": "assistant", "content": result.text})
            return jsonify({"answer": result.text, "chart": result.chart})

    # "When will I reach 500,000 saving 1,500 a month at 5%?" -- solved by code, not guessed by the model.
    goal = savings_goal.try_answer(message)
    if goal:
        bot.history.append({"role": "user", "content": message})
        bot.history.append({"role": "assistant", "content": goal.text})
        return jsonify({"answer": goal.text, "chart": goal.chart})

    # "What will inflation be in 2027?" -- an official forecast we hold, or a plain "I don't predict that".
    outlook = predictions.try_answer(message)
    if outlook:
        bot.history.append({"role": "user", "content": message})
        bot.history.append({"role": "assistant", "content": outlook.text})
        return jsonify({"answer": outlook.text, "chart": None})

    try:
        answer = bot.ask(message)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    return jsonify({
        "answer": answer,
        "chart": bot.last_chart,
        "payment_button": bot.last_payment_button,
        "invoice_button": bot.last_invoice_button,
        "quote_button": bot.last_quote_button,
        "schedule_payments_button": bot.last_schedule_payments_button,
        "chase_payment_button": bot.last_chase_payment_button,
        "refund_button": bot.last_refund_button,
        "talk_to_team_button": bot.last_talk_to_team_button,
        "set_reminder_button": bot.last_set_reminder_button,
        "register_business_button": bot.last_register_business_button,
    })


@app.route("/api/reset", methods=["POST"])
def reset():
    data = request.get_json(silent=True) or {}
    bot = SESSIONS.get(data.get("session_id"))
    if bot is not None:
        bot.reset()
    store = DOCS.get(data.get("session_id"))
    if store is not None:
        store.clear()  # a new chat starts without the previous chat's files
    return jsonify({"ok": True})


@app.errorhandler(413)
def too_large(_error):
    return jsonify({"error": "That file is too large (the limit is 25 MB per upload)."}), 413


@app.route("/api/upload", methods=["POST"])
def upload():
    session_id = request.form.get("session_id")
    bot = SESSIONS.get(session_id)
    if bot is None:
        return jsonify({"error": "Session not found -- refresh the page to start a new one."}), 404
    file = request.files.get("file")
    if file is None or not file.filename:
        return jsonify({"error": "No file received."}), 400

    store = DOCS.setdefault(session_id, DocumentStore())
    try:
        added = store.add_upload(file.filename, file.read())   # an Excel workbook adds one document per sheet
    except UploadError as exc:
        return jsonify({"error": str(exc)}), 400
    bot.documents = store
    return jsonify({
        "document": added[0].public_info(),
        "message": "\n".join(doc.summary_text() for doc in added),
        "documents": store.public_list(),
    })


@app.route("/api/documents", methods=["GET"])
def list_documents():
    store = DOCS.get(request.args.get("session_id"))
    return jsonify({"documents": store.public_list() if store else []})


@app.route("/api/documents/<doc_id>", methods=["DELETE"])
def delete_document(doc_id):
    store = DOCS.get(request.args.get("session_id"))
    if store is None or not store.remove(doc_id):
        return jsonify({"error": "That file isn't in this chat."}), 404
    return jsonify({"documents": store.public_list()})


@app.route("/api/home_summary", methods=["GET"])
def home_summary():
    return jsonify(payments_data.home_summary())


@app.route("/api/payments", methods=["GET"])
def list_payments():
    status = request.args.get("status")
    q = request.args.get("q")
    return jsonify(payments_data.list_payments(status=status, q=q))


@app.route("/api/payments/<payment_id>", methods=["GET"])
def get_payment(payment_id):
    payment = payments_data.get_payment(payment_id)
    if payment is None:
        return jsonify({"error": "Payment not found."}), 404
    return jsonify(payment)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
