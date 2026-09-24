import logging
from html import escape

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from backend.analyzer import AnalyzerError, analyze_alignment
from backend.config import MAX_RESUMES, TELEGRAM_BOT_TOKEN
from backend.parser import ParseError, extract_text_from_bytes
from backend.scoring import why_this_score

log = logging.getLogger("hirelens.telegram")

sessions: dict[int, dict] = {}

WELCOME = (
    "👋 <b>Welcome to HireLens AI</b>\n\n"
    "Know how well your resume matches the job.\n"
    "I produce JD–resume <b>alignment</b> — not a hiring decision.\n\n"
    "Choose:"
)


def _session(chat_id: int) -> dict:
    if chat_id not in sessions:
        sessions[chat_id] = {"mode": "idle", "jd_text": "", "jd_name": "", "resumes": []}
    return sessions[chat_id]


def _menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📄 Analyze Resume", callback_data="mode_single")],
            [InlineKeyboardButton("📊 Analyze Multiple Resumes", callback_data="mode_multiple")],
            [InlineKeyboardButton("❓ Help", callback_data="help")],
        ]
    )


def format_single(result) -> str:
    matched = "\n".join(f"• {escape(s)}" for s in result.matched_skills) or "• None listed"
    missing = "\n".join(f"• {escape(s)}" for s in result.missing_skills) or "• None listed"
    partial = "\n".join(f"• {escape(s)}" for s in result.partial_skills)
    evidence = "\n".join(
        f"• {escape(e.claim)} — {escape(e.confidence.replace(' Evidence', ''))}" for e in result.evidence[:5]
    ) or "• Not enough claims extracted"
    courses = []
    for i, c in enumerate(result.course_recommendations, 1):
        courses.append(f'{i}. <a href="{escape(c.url, quote=True)}">{escape(c.title)}</a>')
    course_block = "\n".join(courses) if courses else "No missing-skill links needed."

    parts = [
        "🎯 <b>JD-RESUME ALIGNMENT</b>",
        "",
        f"📄 Resume: {escape(result.resume_name)}",
        f"<b>Compatibility: {result.final_score}%</b>",
        "━━━━━━━━━━━━━━━━",
        "",
        "✅ <b>Matched Skills</b>",
        matched,
        "",
        "❌ <b>Missing Skills</b>",
        missing,
    ]
    if partial:
        parts += ["", "⚠️ <b>Partial Skills</b>", partial]
    parts += [
        "",
        "📌 <b>Experience</b>",
        escape(result.experience_alignment or "Not stated clearly."),
        "",
        "🔎 <b>Evidence</b>",
        evidence,
        "",
        "💡 <b>Suggestion</b>",
        escape(result.suggestion or "Add missing skills with concrete project evidence."),
        "",
        "📚 <b>Learn Next</b>",
        course_block,
        "━━━━━━━━━━━━━━━━",
    ]
    return "\n".join(parts)


def format_multiple(results: list, job_title: str) -> str:
    lines = [
        "📊 <b>MULTIPLE RESUME ANALYSIS</b>",
        "",
        f"Job: {escape(job_title or 'Uploaded JD')}",
        "━━━━━━━━━━━━━━━━",
        "",
    ]
    ranked = sorted(results, key=lambda r: r.final_score, reverse=True)
    for result in results:
        lines.append(f"📄 <b>{escape(result.resume_name)}</b>")
        lines.append(f"Compatibility: {result.final_score}%")
        lines.append("Matched: " + (" • ".join(escape(s) for s in result.matched_skills[:5]) or "—"))
        lines.append("Missing: " + (" • ".join(escape(s) for s in result.missing_skills[:5]) or "—"))
        lines.append("━━━━━━━━━━━━━━━━")
        lines.append("")
    best = ranked[0]
    lines.append("💡 <b>Alignment Summary</b>")
    lines.append(
        f"{escape(best.resume_name)} has the strongest alignment ({best.final_score}%). "
        "This is JD–resume alignment only — not a hiring decision. "
        "Review missing requirements and evidence before you act."
    )
    if ranked[0].course_recommendations:
        lines.append("")
        lines.append("📚 <b>Learn Next</b>")
        for i, c in enumerate(ranked[0].course_recommendations, 1):
            lines.append(f'{i}. <a href="{escape(c.url, quote=True)}">{escape(c.title)}</a>')
    return "\n".join(lines)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    sessions[chat_id] = {"mode": "idle", "jd_text": "", "jd_name": "", "resumes": []}
    await update.message.reply_text(WELCOME, parse_mode=ParseMode.HTML, reply_markup=_menu())


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "HireLens AI compares a Job Description with one or more resumes.\n\n"
        "/analyze — single resume\n"
        "/multiple — 2–5 resumes vs one JD\n"
        "/reset — clear session\n"
        "/help — this message\n\n"
        "Send PDF, DOCX, or TXT. After uploads, send /done for multiple mode."
    )


async def reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    sessions[update.effective_chat.id] = {"mode": "idle", "jd_text": "", "jd_name": "", "resumes": []}
    await update.message.reply_text("Session cleared. Send /start to begin again.")


async def analyze_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    sess = _session(update.effective_chat.id)
    sess.update({"mode": "wait_jd_single", "jd_text": "", "jd_name": "", "resumes": []})
    await update.message.reply_text("Please upload the Job Description (PDF, DOCX, TXT, or paste text).")


async def multiple_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    sess = _session(update.effective_chat.id)
    sess.update({"mode": "wait_jd_multi", "jd_text": "", "jd_name": "", "resumes": []})
    await update.message.reply_text(
        "Multiple-resume mode.\nPlease upload the Job Description first (PDF, DOCX, TXT, or paste text)."
    )


async def done_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await run_analysis(update.effective_chat.id, context, update.message)


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    sess = _session(chat_id)

    if query.data == "help":
        await query.message.reply_text(
            "Upload a JD, then one or more resumes. Scores use:\n"
            "40% skills · 25% experience · 15% education · 10% projects · 10% requirements.\n"
            "Evidence confidence is not an honesty check."
        )
        return
    if query.data.startswith("why:"):
        idx = int(query.data.split(":")[1])
        cached = sess.get("last_results") or []
        if 0 <= idx < len(cached):
            r = cached[idx]
            await query.message.reply_text(
                why_this_score(r.component_scores.model_dump(), r.final_score, r.missing_skills),
                parse_mode=ParseMode.HTML,
            )
        return
    if query.data == "mode_single":
        sess.update({"mode": "wait_jd_single", "jd_text": "", "jd_name": "", "resumes": []})
        await query.message.reply_text("Please upload the Job Description.")
        return
    if query.data == "mode_multiple":
        sess.update({"mode": "wait_jd_multi", "jd_text": "", "jd_name": "", "resumes": []})
        await query.message.reply_text("Please upload the Job Description. Then send 2–5 resumes and /done.")


async def on_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    doc = update.message.document
    chat_id = update.effective_chat.id
    file = await context.bot.get_file(doc.file_id)
    data = await file.download_as_bytearray()
    try:
        text = extract_text_from_bytes(doc.file_name or "file.txt", bytes(data))
    except ParseError as exc:
        await update.message.reply_text(str(exc))
        return
    await ingest_text(update, context, text, doc.file_name or "document")


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.text.startswith("/"):
        return
    await ingest_text(update, context, update.message.text, "pasted.txt")


async def ingest_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, name: str) -> None:
    sess = _session(update.effective_chat.id)
    mode = sess.get("mode", "idle")

    if mode in {"wait_jd_single", "wait_jd_multi", "idle"}:
        if mode == "idle":
            sess["mode"] = "wait_jd_single"
        sess["jd_text"] = text
        sess["jd_name"] = name
        if sess["mode"] == "wait_jd_single":
            sess["mode"] = "wait_resume_single"
            await update.message.reply_text("JD received ✅\n\nNow upload your resume.")
        else:
            sess["mode"] = "wait_resumes_multi"
            await update.message.reply_text(
                "JD received ✅\n\nNow send 2–5 resumes, one at a time. Send /done when finished."
            )
        return

    if mode == "wait_resume_single":
        sess["resumes"] = [{"name": name, "text": text}]
        await update.message.reply_text("Analyzing your resume... 🤖")
        await run_analysis(update.effective_chat.id, context, update.message)
        return

    if mode == "wait_resumes_multi":
        if len(sess["resumes"]) >= MAX_RESUMES:
            await update.message.reply_text(f"Maximum {MAX_RESUMES} resumes. Send /done to analyze.")
            return
        sess["resumes"].append({"name": name, "text": text})
        n = len(sess["resumes"])
        await update.message.reply_text(f"✅ Resume {n} received (`{name}`). Send more or /done.")
        return

    await update.message.reply_text("Send /start and pick Analyze Resume or Analyze Multiple Resumes.")


async def run_analysis(chat_id: int, context: ContextTypes.DEFAULT_TYPE, message) -> None:
    sess = _session(chat_id)
    if not sess.get("jd_text"):
        await message.reply_text("No JD yet. Send /start and upload a job description first.")
        return
    if not sess.get("resumes"):
        await message.reply_text("No resumes yet. Upload at least one resume.")
        return

    results = []
    try:
        for item in sess["resumes"]:
            results.append(analyze_alignment(sess["jd_text"], item["text"], item["name"]))
    except AnalyzerError as exc:
        await message.reply_text(str(exc))
        return
    except Exception:
        log.exception("analysis failed")
        await message.reply_text("Analysis failed. Check GEMINI_API_KEY and try /reset.")
        return

    sess["last_results"] = results
    sess["mode"] = "idle"

    if len(results) == 1:
        text = format_single(results[0])
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton(f"🔍 Why {results[0].final_score}%?", callback_data="why:0")]]
        )
        await message.reply_text(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True, reply_markup=keyboard)
        return

    text = format_multiple(results, results[0].job_title)
    buttons = [
        [InlineKeyboardButton(f"🔍 Why {r.final_score}%? ({r.resume_name[:18]})", callback_data=f"why:{i}")]
        for i, r in enumerate(results)
    ]
    await message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup(buttons),
    )


def build_application() -> Application:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing. Add it to .env")
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("analyze", analyze_cmd))
    app.add_handler(CommandHandler("multiple", multiple_cmd))
    app.add_handler(CommandHandler("reset", reset_cmd))
    app.add_handler(CommandHandler("done", done_cmd))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.Document.ALL, on_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    return app


def run_bot() -> None:
    logging.basicConfig(level=logging.INFO)
    app = build_application()
    log.info("HireLens Telegram bot polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
