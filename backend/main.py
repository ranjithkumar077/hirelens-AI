from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.analyzer import AnalyzerError, analyze_alignment
from backend.config import ALLOWED_EXTENSIONS, MAX_FILE_BYTES, MAX_RESUMES, ROOT_DIR
from backend.models import AnalysisResult
from backend.parser import ParseError, extract_text_from_bytes

app = FastAPI(title="HireLens AI", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

frontend_dir = ROOT_DIR / "frontend"


@app.get("/")
def index():
    index_path = frontend_dir / "index.html"
    if not index_path.exists():
        return {"app": "HireLens AI", "docs": "/docs"}
    return FileResponse(index_path)


@app.get("/health")
def health():
    return {"status": "ok", "app": "HireLens AI"}


def _read_upload(file: UploadFile) -> tuple[str, str]:
    name = file.filename or "upload.txt"
    suffix = ("." + name.rsplit(".", 1)[-1].lower()) if "." in name else ""
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, "Unsupported file type. Use PDF, DOCX, or TXT.")
    data = file.file.read()
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(400, "File too large.")
    try:
        return name, extract_text_from_bytes(name, data)
    except ParseError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/analyze", response_model=AnalysisResult)
async def analyze_single(
    jd: UploadFile | None = File(default=None),
    resume: UploadFile | None = File(default=None),
    jd_text: str = Form(default=""),
    resume_text: str = Form(default=""),
    resume_name: str = Form(default="resume"),
):
    try:
        jd_content = jd_text
        if jd and jd.filename:
            _, jd_content = _read_upload(jd)
        res_content = resume_text
        name = resume_name
        if resume and resume.filename:
            name, res_content = _read_upload(resume)
        return analyze_alignment(jd_content, res_content, name)
    except AnalyzerError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/analyze-multiple")
async def analyze_multiple(
    jd: UploadFile | None = File(default=None),
    resumes: list[UploadFile] | None = File(default=None),
    jd_text: str = Form(default=""),
):
    jd_content = jd_text
    if jd and jd.filename:
        _, jd_content = _read_upload(jd)
    files = resumes or []
    if not files:
        raise HTTPException(400, "Upload at least one resume.")
    if len(files) > MAX_RESUMES:
        raise HTTPException(400, f"Maximum {MAX_RESUMES} resumes.")

    results = []
    try:
        for file in files:
            name, text = _read_upload(file)
            results.append(analyze_alignment(jd_content, text, name))
    except AnalyzerError as exc:
        raise HTTPException(400, str(exc)) from exc

    ranked = sorted(results, key=lambda r: r.final_score, reverse=True)
    return {
        "job_title": results[0].job_title if results else "",
        "count": len(results),
        "best_fit": ranked[0].resume_name if ranked else None,
        "results": [r.model_dump() for r in results],
    }


if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")
