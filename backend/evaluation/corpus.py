"""
CampusMind AI - Evaluation Corpus
Provides a standardized university document corpus for benchmarking chunking and retrieval methods.
Contains sample policy, syllabus, and administrative documents with known facts.
"""

from typing import List
from app.schemas.chunk import ExtractedDocument, ExtractedPage

CORPUS_DOCUMENTS: List[ExtractedDocument] = [
    ExtractedDocument(
        document_id="doc_handbook_cs",
        document_name="CS_Student_Handbook_2026.pdf",
        pages=[
            ExtractedPage(
                page_number=1,
                text=(
                    "CampusMind University - Department of Computer Science\n"
                    "Academic Year 2026-2027 Student Handbook.\n"
                    "Dean of Engineering: Dr. Robert Vance. Department Chair: Prof. Elena Rostova.\n"
                    "Office Location: Turing Hall, Room 402. Contact: cs-dept@campusmind.edu."
                ),
            ),
            ExtractedPage(
                page_number=2,
                text=(
                    "Grading and Academic Standing Policy:\n"
                    "Letter grades are awarded as follows: A (90-100%), B (80-89%), C (70-79%), D (60-69%), F (<60%).\n"
                    "A minimum Cumulative Grade Point Average (CGPA) of 2.0 is required for good standing.\n"
                    "Students whose term GPA falls below 2.0 are placed on Academic Probation for the subsequent semester."
                ),
            ),
            ExtractedPage(
                page_number=3,
                text=(
                    "Course Registration and Deadlines:\n"
                    "The add/drop period closes on Friday, September 18, 2026 at 5:00 PM.\n"
                    "Course withdrawal with a grade of 'W' is permitted until Friday, November 6, 2026.\n"
                    "Late registrations incur a mandatory penalty fee of $50."
                ),
            ),
            ExtractedPage(
                page_number=4,
                text=(
                    "Graduation Requirements:\n"
                    "Undergraduate degree completion requires 128 total credit hours.\n"
                    "All students must complete a Senior Capstone Project (CS-490) with a grade of C or higher.\n"
                    "Students must fulfill 40 credits in core CS disciplines and 12 credits of technical electives."
                ),
            ),
        ],
        metadata={"category": "handbook", "year": "2026"},
    ),
    ExtractedDocument(
        document_id="doc_syllabus_cs301",
        document_name="CS301_Algorithms_Syllabus.docx",
        pages=[
            ExtractedPage(
                page_number=1,
                text=(
                    "CS-301: Design and Analysis of Algorithms - Fall 2026.\n"
                    "Instructor: Dr. Alan Sterling (alan.sterling@campusmind.edu). Office Hours: Mon/Wed 2-4 PM in Turing Hall 315.\n"
                    "Teaching Assistant: Marcus Chen (mchen@campusmind.edu). Lab Hours: Thursdays 10 AM-12 PM in Lab B04."
                ),
            ),
            ExtractedPage(
                page_number=2,
                text=(
                    "Assessment and Grading Weight Distribution:\n"
                    "Weekly Homework Assignments: 20% (6 total assignments, lowest score dropped).\n"
                    "Midterm Examination: 30% (Held in-class on Wednesday, October 21, 2026).\n"
                    "Final Examination: 40% (Comprehensive exam scheduled for December 15, 2026 in Main Hall).\n"
                    "Class Participation and Quizzes: 10%."
                ),
            ),
            ExtractedPage(
                page_number=3,
                text=(
                    "Late Submission Policy and Academic Integrity:\n"
                    "Assignments submitted up to 24 hours late receive a flat 15% deduction.\n"
                    "Submissions later than 24 hours will receive a score of zero unless excused by medical documentation.\n"
                    "All code must be original. Plagiarism is reported to the University Academic Integrity Board."
                ),
            ),
        ],
        metadata={"category": "syllabus", "course": "CS-301"},
    ),
    ExtractedDocument(
        document_id="doc_campus_facilities",
        document_name="Campus_Facilities_Guide.txt",
        pages=[
            ExtractedPage(
                page_number=1,
                text=(
                    "Campus Facilities and Services Guide:\n"
                    "Main Library (Babbage Memorial Library) Hours:\n"
                    "Monday to Thursday: 7:30 AM - Midnight.\n"
                    "Friday: 7:30 AM - 8:00 PM.\n"
                    "Saturday and Sunday: 10:00 AM - 6:00 PM.\n"
                    "Student Wellness Center is located in Building K, Room 110. Emergency Hotline: 555-0199.\n"
                    "Campus Dining Hall operates 7:00 AM - 9:00 PM daily. Meal plans require student ID card presentation."
                ),
            ),
        ],
        metadata={"category": "guide", "facility": "campus"},
    ),
]

