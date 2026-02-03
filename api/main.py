from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi import Request
from fastapi.templating import Jinja2Templates

from typing_extensions import Annotated
from pydantic import BaseModel, Field
import re
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import os
from dotenv import load_dotenv
# from openai import OpenAI
from fastapi import UploadFile, File, Form
from pypdf import PdfReader
from io import BytesIO
import time
import concurrent.futures

mistral_client = None


def mistral_call_with_retry(call_fn, retries=1, delay=1, timeout=25):
    last_error = None

    for _ in range(retries + 1):
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(call_fn)
                return future.result(timeout=timeout)

        except concurrent.futures.TimeoutError:
            last_error = TimeoutError("LLM request timed out")

        except Exception as e:
            last_error = e

        time.sleep(delay)

    raise last_error


load_dotenv()
# client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


app = FastAPI()
app.mount("/static", StaticFiles(directory="ui/static"), name="static")
templates = Jinja2Templates(directory="ui/templates")


# @app.get("/", response_class=HTMLResponse)
# def home():
#     with open("ui/templates/index.html") as f:
#         return f.read()

@app.get("/", response_class=HTMLResponse)
def serve_ui(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request}
    )



@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "AI Resume JD Matcher"
    }

# Load model once
model = SentenceTransformer("all-MiniLM-L6-v2")

class MatchRequest(BaseModel):
    resume_text: str = Field(..., min_length=50, description="Candidate resume text")
    jd_text: str = Field(..., min_length=50, description="Job description text")

class MatchResponse(BaseModel):
    match_percentage: float
    explanation: str
    interview_questions: str

def clean_text(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

async def extract_text_from_pdf_file(file: UploadFile) -> str:
    try:
        pdf_bytes = await file.read()
        reader = PdfReader(BytesIO(pdf_bytes))

        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""

        text = text.strip()
        if len(text) < 50:
            raise HTTPException(status_code=400, detail=f"{file.filename} text too short")

        return text

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail=f"Unable to read PDF: {file.filename}")



# def generate_explanation(resume_text, jd_text, match_percentage):  --For OpenAI purpose
#     prompt = f"""
# You are an AI hiring assistant.

# Resume:
# {resume_text}

# Job Description:
# {jd_text}

# Match Score: {match_percentage}%

# Explain the match in bullet points:
# - Key strengths
# - Missing skills
# - Summary
# """

#     response = client.chat.completions.create(
#         model="gpt-4o-mini",
#         messages=[{"role": "user", "content": prompt}],
#         temperature=0.3
#     )
#     return response.choices[0].message.content


# def generate_interview_questions(resume_text, jd_text):  --For OpenAI purpose
#     prompt = f"""
# You are a technical interviewer.

# Resume:
# {resume_text}

# Job Description:
# {jd_text}

# Generate:
# - 3 technical questions
# - 2 scenario questions
# - 2 skill-gap questions
# """

#     response = client.chat.completions.create(
#         model="gpt-4o-mini",
#         messages=[{"role": "user", "content": prompt}],
#         temperature=0.4
#     )
#     return response.choices[0].message.content

def generate_explanation(resume_text, jd_text, match_percentage):
    from mistralai import Mistral
    global mistral_client

    if mistral_client is None:
        mistral_client = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))

    try:
        response = mistral_call_with_retry(
            lambda: mistral_client.chat.complete(
                model="mistral-small-latest",
                messages=[
                    {
                        "role": "user",
                        "content": f"""
You are an AI hiring assistant.

Resume:
{resume_text[:3000]}

Job Description:
{jd_text[:3000]}

Match Score: {match_percentage}%

Explain the match in bullet points:
- Key strengths
- Missing skills
- Summary
"""
                    }
                ],
                temperature=0.3
            )
        )

        # ✅ FIXED RESPONSE PARSING
        return response.choices[0].message.content[0].text

    except Exception as e:
        print("🔥 Explanation LLM error:", repr(e))
        return "Explanation unavailable (LLM error)."



def generate_interview_questions(resume_text, jd_text):
    from mistralai import Mistral
    global mistral_client
    if mistral_client is None:
        mistral_client = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))
    try:
        response = mistral_call_with_retry(
            lambda: mistral_client.chat.complete(
                model="mistral-small-latest",
                messages=[
                    {
                        "role": "user",
                        "content": f"""
You are a technical interviewer.

Resume:
{resume_text[:3000]}

Job Description:
{jd_text[:3000]}

Generate:
- 3 technical questions
- 2 scenario questions
- 2 skill-gap questions
"""
                    }
                ],
                temperature=0.4
            )
        )
        return response.choices[0].message.content

    except Exception as e:
        print("🔥 Interview LLM error:", repr(e))
        return "Interview questions unavailable (LLM error)."







@app.post("/match", response_model=MatchResponse)
def match_resume(request: MatchRequest):
    try:
        # ---- CORE ML (MUST NEVER FAIL) ----
        clean_resume = clean_text(request.resume_text)
        clean_jd = clean_text(request.jd_text)

        resume_emb = model.encode(clean_resume).reshape(1, -1)
        jd_emb = model.encode(clean_jd).reshape(1, -1)

        score = cosine_similarity(resume_emb, jd_emb)[0][0]
        match_percentage = round(score * 100, 2)

        # ---- OPTIONAL AI PART (CAN FAIL) ----
        try:
            explanation = generate_explanation(
                clean_resume, clean_jd, match_percentage
            )
        except Exception:
            explanation = "Explanation temporarily unavailable."

        try:
            interview_questions = generate_interview_questions(
                clean_resume, clean_jd
            )
        except Exception:
            interview_questions = "Interview questions temporarily unavailable."

        return MatchResponse(
            match_percentage=match_percentage,
            explanation=explanation,
            interview_questions=interview_questions
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Core matching failed: {str(e)}"
        )
    
@app.post("/match-pdf", response_model=MatchResponse)
async def match_pdf(
    resume_pdf: Annotated[UploadFile, File(...)],
    jd_pdf: Annotated[UploadFile, File(...)]
):
    try:
        # ---- PDF EXTRACTION (CAN FAIL) ----
        resume_text = await extract_text_from_pdf_file(resume_pdf)
        jd_text = await extract_text_from_pdf_file(jd_pdf)

        clean_resume = clean_text(resume_text)
        clean_jd = clean_text(jd_text)

        # ---- CORE ML (MUST NEVER FAIL) ----
        resume_emb = model.encode(clean_resume).reshape(1, -1)
        jd_emb = model.encode(clean_jd).reshape(1, -1)

        score = cosine_similarity(resume_emb, jd_emb)[0][0]
        match_percentage = round(score * 100, 2)

        # ---- OPTIONAL AI PART (CAN FAIL SAFELY) ----
        try:
            explanation = generate_explanation(
                clean_resume, clean_jd, match_percentage
            )
        except Exception:
            explanation = "Explanation temporarily unavailable."

        try:
            interview_questions = generate_interview_questions(
                clean_resume, clean_jd
            )
        except Exception:
            interview_questions = "Interview questions temporarily unavailable."

        return MatchResponse(
            match_percentage=match_percentage,
            explanation=explanation,
            interview_questions=interview_questions
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Core PDF matching failed: {str(e)}"
        )
