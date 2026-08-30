"""
=============================================================================
CampusGuard AI — Context-Aware Institutional RAG Knowledge Engine
=============================================================================
Provides semantic search and precise policy citation retrieval across:
1. Academic Regulations & Grading Bylaws (FAT/CAT, S/A+/A Grade Bands)
2. Examination Rules & Hall Ticket Eligibility Requirements
3. Attendance Shortage & Condonation Guidelines
4. Hostel Curfews, Outpass Rules & Resident Conduct
5. Campus Safety Protocols, Emergency Dispatch & Anti-Harassment Directives
6. Fee Schedules, Payment Installments & Refund Policies
=============================================================================
"""

import math
import re
from typing import List, Dict, Any

# Canonical Campus Knowledge Corpus with Section References
CAMPUS_REGULATIONS_CORPUS = [
    {
        "id": "ACAD-01",
        "title": "Minimum Attendance Requirement & Condonation Rules",
        "category": "Academic",
        "section": "Section 4.2 — Institutional Attendance Bylaws",
        "content": (
            "All undergraduate and postgraduate students must maintain a minimum of 75.0% aggregate attendance "
            "in each enrolled course to be eligible to appear for the Final Assessment Test (FAT). "
            "Students with attendance between 65.0% and 74.9% may apply for medical condonation subject to "
            "valid institutional hospital certification. Attendance below 65.0% results in mandatory course repetition (N Grade)."
        ),
        "keywords": ["attendance", "75", "75%", "condonation", "shortage", "minimum attendance", "eligibility", "fat eligibility", "medical leave"]
    },
    {
        "id": "ACAD-02",
        "title": "Grading Scale, SGPA & CGPA Calculation Formula",
        "category": "Academic",
        "section": "Section 6.1 — Academic Evaluation & Performance",
        "content": (
            "The 10-point relative grading scale is structured as: S Grade (10 points, >=90 marks), "
            "A+ Grade (9 points, 80-89 marks), A Grade (8 points, 70-79 marks), B Grade (7 points, 60-69 marks), "
            "C Grade (6 points, 50-59 marks), D Grade (5 points, 40-49 marks), F Grade (0 points, <40 marks - Fail). "
            "CGPA = Sum of (Course Credits * Grade Points) / Total Registered Credits."
        ),
        "keywords": ["grade", "grading", "cgpa", "sgpa", "s grade", "a grade", "gpa calculation", "grade points", "passing mark"]
    },
    {
        "id": "EXAM-01",
        "title": "Continuous Assessment & Final Examination Format",
        "category": "Examinations",
        "section": "Section 5.3 — Examination Framework",
        "content": (
            "Course evaluation consists of: CAT-1 (15%), CAT-2 (15%), Quizzes & Continuous Homework (10%), "
            "Term Project / Laboratory Viva (20%), and Comprehensive Final Assessment Test (FAT - 40%). "
            "A student must secure at least 40% in FAT and 50% composite aggregate to pass the course."
        ),
        "keywords": ["exam", "exams", "cat", "cat1", "cat2", "fat", "assessment", "weightage", "final exam", "marks distribution"]
    },
    {
        "id": "HOSTEL-01",
        "title": "Hostel Curfew Hours & Digital Outpass Guidelines",
        "category": "Hostel",
        "section": "Section 8.4 — Residential Living Regulations",
        "content": (
            "In-campus hostel gates close strictly at 09:30 PM on weekdays and 10:00 PM on weekends. "
            "Overnight leave or weekend home visit requires digital outpass authorization submitted at least 24 hours prior. "
            "Parental authorization via the CampusGuard Parent Portal is mandatory for outpass approval."
        ),
        "keywords": ["hostel", "curfew", "outpass", "leave", "timing", "gate close", "warden", "block", "overnight"]
    },
    {
        "id": "SAFETY-01",
        "title": "Emergency SOS Response & Safe Walk Telemetry",
        "category": "Safety",
        "section": "Section 2.1 — Campus Emergency Operating Procedures",
        "content": (
            "The CampusGuard SOS Beacon broadcasts high-precision GPS coordinates, user role, and active corridor metadata "
            "directly to the 24/7 Security Command Center. When activated, on-duty mobile patrol units are dispatched within 120 seconds. "
            "The Safe Walk Companion tracks timed journeys and automatically raises a high-priority alert if arrival is overdue."
        ),
        "keywords": ["sos", "emergency", "safe walk", "security", "patrol", "danger", "medical", "police", "helpline", "help"]
    },
    {
        "id": "FIN-01",
        "title": "Tuition, Hostel & Examination Fee Policies",
        "category": "Finance",
        "section": "Section 9.2 — Institutional Finance Bylaws",
        "content": (
            "Semester tuition and hostel charges must be settled prior to the published deadline via the secure online fee ledger. "
            "A grace period of 15 days is permitted with a nominal late fee of ₹500. "
            "Unpaid dues beyond the grace period restrict examination hall ticket generation and course registration."
        ),
        "keywords": ["fee", "fees", "due", "tuition", "fine", "late fee", "payment", "hostel fee", "hall ticket block"]
    },
    {
        "id": "DISC-01",
        "title": "Anti-Ragging, Anti-Harassment & Campus Code of Conduct",
        "category": "Governance",
        "section": "Section 1.3 — Student Conduct & Welfare Code",
        "content": (
            "CampusGuard enforces a strict zero-tolerance policy against ragging, physical harassment, and discrimination. "
            "Complaints can be logged anonymously via the Grievance Redressal system or via the dedicated Women's Safety Liaison (ext. 56782). "
            "Disciplinary Committee inquiries are completed within 72 working hours."
        ),
        "keywords": ["ragging", "anti-ragging", "harassment", "grievance", "complaint", "conduct", "disciplinary", "women safety"]
    }
]


def _tokenize_and_stem(text: str) -> List[str]:
    """Tokenizes string into clean lower-case alphanumeric tokens."""
    tokens = re.findall(r'\b[a-z0-9]+\b', text.lower())
    return [t for t in tokens if len(t) > 1]


def calculate_bm25_similarity(query_tokens: List[str], doc_tokens: List[str], doc_keywords: List[str], title: str = "") -> float:
    """Computes hybrid keyword match and token overlap score."""
    score = 0.0
    doc_text_set = set(doc_tokens)
    keywords_set = set(k.lower() for k in doc_keywords)
    title_tokens = set(_tokenize_and_stem(title))
    query_str = " ".join(query_tokens)

    for q in query_tokens:
        if q in title_tokens:
            score += 6.0
        if q in keywords_set:
            score += 4.5
        elif any(q in kw for kw in keywords_set):
            score += 2.5
        if q in doc_text_set:
            score += 1.5

    # Keyword phrase matching
    for kw in doc_keywords:
        if kw.lower() in query_str:
            score += 7.0

    return score


def search_campus_knowledge(query: str, top_k: int = 2) -> List[Dict[str, Any]]:
    """
    Performs context-aware RAG search against institutional policies,
    returning top scored documents with exact citations.
    """
    if not query:
        return []

    q_tokens = _tokenize_and_stem(query)
    if not q_tokens:
        return []

    scored_docs = []
    for doc in CAMPUS_REGULATIONS_CORPUS:
        doc_tokens = _tokenize_and_stem(doc['content'] + " " + doc['title'])
        score = calculate_bm25_similarity(q_tokens, doc_tokens, doc['keywords'], title=doc['title'])
        if score > 0:
            scored_docs.append({
                **doc,
                'score': round(score, 2)
            })

    scored_docs.sort(key=lambda d: d['score'], reverse=True)
    return scored_docs[:top_k]


def format_rag_context_for_llm(docs: List[Dict[str, Any]]) -> str:
    """Formats retrieved documents into grounded prompt context."""
    if not docs:
        return "No specific institutional regulations matched."

    lines = ["--- INSTITUTIONAL REGULATORY CITATIONS ---"]
    for i, d in enumerate(docs, 1):
        lines.append(f"[{i}] {d['title']} ({d['section']})")
        lines.append(f"    Category: {d['category']}")
        lines.append(f"    Official Policy: {d['content']}")
    lines.append("------------------------------------------")
    return "\n".join(lines)
