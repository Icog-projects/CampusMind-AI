"""
CampusMind AI - Benchmark Questions Dataset (SRS 12.2, 12.3)
A fixed benchmark of 25 questions covering all required categories:
- Single-document factual queries
- Multi-document queries
- Exact names, dates, course codes, and room numbers
- Unanswerable / absent questions (to verify insufficient-context handling)
- Completely unrelated / out-of-domain queries
"""

from typing import List, Dict, Any

BENCHMARK_QUESTIONS: List[Dict[str, Any]] = [
    # --- Category 1: Single-document factual queries ---
    {
        "id": "Q01",
        "question": "What is the minimum CGPA required for good academic standing in Computer Science?",
        "category": "single_document",
        "expected_doc_ids": ["doc_handbook_cs"],
        "expected_answer_keywords": ["2.0", "CGPA", "good standing"],
        "is_answerable": True,
    },
    {
        "id": "Q02",
        "question": "How many total credit hours are required for undergraduate degree completion?",
        "category": "single_document",
        "expected_doc_ids": ["doc_handbook_cs"],
        "expected_answer_keywords": ["128", "credit hours"],
        "is_answerable": True,
    },
    {
        "id": "Q03",
        "question": "What happens if an assignment is submitted up to 24 hours late in CS-301?",
        "category": "single_document",
        "expected_doc_ids": ["doc_syllabus_cs301"],
        "expected_answer_keywords": ["15%", "deduction", "24 hours"],
        "is_answerable": True,
    },
    {
        "id": "Q04",
        "question": "What percentage of the CS-301 course grade is the final examination worth?",
        "category": "single_document",
        "expected_doc_ids": ["doc_syllabus_cs301"],
        "expected_answer_keywords": ["40%", "final examination"],
        "is_answerable": True,
    },
    {
        "id": "Q05",
        "question": "What are the operating hours of the Main Library on Saturdays and Sundays?",
        "category": "single_document",
        "expected_doc_ids": ["doc_campus_facilities"],
        "expected_answer_keywords": ["10:00 AM", "6:00 PM"],
        "is_answerable": True,
    },
    # --- Category 2: Exact names, dates, identifiers, room numbers ---
    {
        "id": "Q06",
        "question": "Who is the Chair of the Computer Science Department?",
        "category": "exact_identifiers",
        "expected_doc_ids": ["doc_handbook_cs"],
        "expected_answer_keywords": ["Prof. Elena Rostova", "Elena Rostova"],
        "is_answerable": True,
    },
    {
        "id": "Q07",
        "question": "Where is the Computer Science Department office located?",
        "category": "exact_identifiers",
        "expected_doc_ids": ["doc_handbook_cs"],
        "expected_answer_keywords": ["Turing Hall", "Room 402"],
        "is_answerable": True,
    },
    {
        "id": "Q08",
        "question": "What is the exact deadline date and time for the add/drop registration period?",
        "category": "exact_identifiers",
        "expected_doc_ids": ["doc_handbook_cs"],
        "expected_answer_keywords": ["Friday, September 18, 2026", "5:00 PM"],
        "is_answerable": True,
    },
    {
        "id": "Q09",
        "question": "When is the CS-301 midterm examination scheduled to take place?",
        "category": "exact_identifiers",
        "expected_doc_ids": ["doc_syllabus_cs301"],
        "expected_answer_keywords": ["Wednesday, October 21, 2026", "October 21"],
        "is_answerable": True,
    },
    {
        "id": "Q10",
        "question": "Who is the teaching assistant for CS-301 and what is his email address?",
        "category": "exact_identifiers",
        "expected_doc_ids": ["doc_syllabus_cs301"],
        "expected_answer_keywords": ["Marcus Chen", "mchen@campusmind.edu"],
        "is_answerable": True,
    },
    {
        "id": "Q11",
        "question": "What is the emergency hotline number for the Student Wellness Center?",
        "category": "exact_identifiers",
        "expected_doc_ids": ["doc_campus_facilities"],
        "expected_answer_keywords": ["555-0199"],
        "is_answerable": True,
    },
    {
        "id": "Q12",
        "question": "Where is the Student Wellness Center located?",
        "category": "exact_identifiers",
        "expected_doc_ids": ["doc_campus_facilities"],
        "expected_answer_keywords": ["Building K", "Room 110"],
        "is_answerable": True,
    },
    {
        "id": "Q13",
        "question": "What is the course code for the mandatory Senior Capstone Project?",
        "category": "exact_identifiers",
        "expected_doc_ids": ["doc_handbook_cs"],
        "expected_answer_keywords": ["CS-490"],
        "is_answerable": True,
    },
    {
        "id": "Q14",
        "question": "What is the late registration penalty fee in the Computer Science department?",
        "category": "exact_identifiers",
        "expected_doc_ids": ["doc_handbook_cs"],
        "expected_answer_keywords": ["$50", "50"],
        "is_answerable": True,
    },
    # --- Category 3: Multi-document / Cross-domain queries ---
    {
        "id": "Q15",
        "question": "Where are Dr. Sterling's office hours held and what building houses the CS department office?",
        "category": "multi_document",
        "expected_doc_ids": ["doc_syllabus_cs301", "doc_handbook_cs"],
        "expected_answer_keywords": ["Turing Hall", "315", "402"],
        "is_answerable": True,
    },
    {
        "id": "Q16",
        "question": "What is the final exam date for CS-301 and what are the library operating hours on that weekday?",
        "category": "multi_document",
        "expected_doc_ids": ["doc_syllabus_cs301", "doc_campus_facilities"],
        "expected_answer_keywords": ["December 15", "Midnight", "7:30 AM"],
        "is_answerable": True,
    },
    {
        "id": "Q17",
        "question": "If a student wants to withdraw from CS-301 with a W grade, what is the deadline according to the handbook?",
        "category": "multi_document",
        "expected_doc_ids": ["doc_handbook_cs", "doc_syllabus_cs301"],
        "expected_answer_keywords": ["Friday, November 6, 2026", "November 6"],
        "is_answerable": True,
    },
    {
        "id": "Q18",
        "question": "What grade is required on the Senior Capstone Project and what letter percentage does that represent?",
        "category": "multi_document",
        "expected_doc_ids": ["doc_handbook_cs"],
        "expected_answer_keywords": ["C", "70-79%"],
        "is_answerable": True,
    },
    # --- Category 4: Unanswerable / Absent information ---
    {
        "id": "Q19",
        "question": "What is the cost of tuition per credit hour for international graduate students?",
        "category": "unanswerable",
        "expected_doc_ids": [],
        "expected_answer_keywords": ["not contain sufficient information", "not found"],
        "is_answerable": False,
    },
    {
        "id": "Q20",
        "question": "What are the swimming pool open hours at the university recreation center?",
        "category": "unanswerable",
        "expected_doc_ids": [],
        "expected_answer_keywords": ["not contain sufficient information", "not found"],
        "is_answerable": False,
    },
    {
        "id": "Q21",
        "question": "Who is the professor teaching Artificial Intelligence CS-420 in Spring 2027?",
        "category": "unanswerable",
        "expected_doc_ids": [],
        "expected_answer_keywords": ["not contain sufficient information", "not found"],
        "is_answerable": False,
    },
    {
        "id": "Q22",
        "question": "What is the price of a monthly campus parking permit for commuter students?",
        "category": "unanswerable",
        "expected_doc_ids": [],
        "expected_answer_keywords": ["not contain sufficient information", "not found"],
        "is_answerable": False,
    },
    # --- Category 5: Completely unrelated / Out-of-domain ---
    {
        "id": "Q23",
        "question": "What is the capital city of Australia?",
        "category": "unrelated",
        "expected_doc_ids": [],
        "expected_answer_keywords": ["not contain sufficient information", "not found"],
        "is_answerable": False,
    },
    {
        "id": "Q24",
        "question": "Can you give me a recipe for chocolate chip cookies?",
        "category": "unrelated",
        "expected_doc_ids": [],
        "expected_answer_keywords": ["not contain sufficient information", "not found"],
        "is_answerable": False,
    },
    {
        "id": "Q25",
        "question": "How far is the Earth from the Sun in kilometers?",
        "category": "unrelated",
        "expected_doc_ids": [],
        "expected_answer_keywords": ["not contain sufficient information", "not found"],
        "is_answerable": False,
    },
]

