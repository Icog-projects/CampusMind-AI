"""
CampusMind AI - Real-World End-to-End Smoke Test Script (SRS v1.3)
Executes end-to-end verification against live MySQL, Redis, Qdrant, and FastAPI application:
1. Verify GET /health reports healthy status for all dependencies.
2. Ingest CS_Student_Handbook_2026.pdf via POST /documents/upload.
3. Verify document appears in GET /documents with status 'indexed'.
4. Query POST /chat/ask (first time -> Cache Miss -> grounded answer + sources).
5. Query POST /chat/ask (second time with identical question -> Cache Hit -> is_cache_hit = True).
6. Verify MySQL persistence for both interactions in messages table.
7. Verify GET /metrics/cache and GET /health live counters.
"""

import os
import sys
import time
import pymysql
from fastapi.testclient import TestClient
from app.main import app

def run_smoke_test():
    client = TestClient(app)

    print("============================================================")
    print("CampusMind AI - Final Real-World End-to-End Smoke Test")
    print("============================================================")

    # 1. Check GET /health
    print("\n[Step 1] Checking GET /health...")
    res_health = client.get("/health")
    print(f"Status Code: {res_health.status_code}")
    health_data = res_health.json()
    print(f"Health Response: {health_data}")
    assert res_health.status_code == 200, "Health check failed"
    for dep, info in health_data["dependencies"].items():
        assert info["status"] == "healthy", f"Dependency {dep} is not healthy: {info}"
    print("-> Step 1 Result: PASS")

    # 2. Upload Document via POST /documents/upload
    print("\n[Step 2] Uploading CS_Student_Handbook_2026.pdf via POST /documents/upload...")
    file_path = os.path.join("evaluation", "corpus_files", "CS_Student_Handbook_2026.pdf")
    assert os.path.exists(file_path), f"File not found: {file_path}"

    with open(file_path, "rb") as f:
        files = {"file": ("CS_Student_Handbook_2026.pdf", f, "application/pdf")}
        data = {"uploader_id": "admin_smoke_test", "chunking_method": "recursive"}
        res_upload = client.post("/documents/upload", files=files, data=data)

    print(f"Status Code: {res_upload.status_code}")
    upload_data = res_upload.json()
    print(f"Upload Response: {upload_data}")
    assert res_upload.status_code == 201, f"Upload failed: {upload_data}"
    assert upload_data["status"] == "indexed", f"Expected indexed status, got {upload_data['status']}"
    assert upload_data["chunk_count"] > 0, "Chunk count must be greater than 0"
    doc_id = upload_data["document_id"]
    print("-> Step 2 Result: PASS")

    # 3. Verify GET /documents
    print("\n[Step 3] Checking GET /documents...")
    res_docs = client.get("/documents")
    print(f"Status Code: {res_docs.status_code}")
    docs_list = res_docs.json()
    target_doc = next((d for d in docs_list if d["id"] == doc_id), None)
    print(f"Uploaded Document Record in MySQL: {target_doc}")
    assert target_doc is not None, "Uploaded document record was not found in MySQL"
    assert target_doc["status"] == "indexed", f"Expected status 'indexed', got '{target_doc['status']}'"
    print("-> Step 3 Result: PASS")

    # 4. Ask Question (Cache Miss) via POST /chat/ask
    print("\n[Step 4] Submitting Question (Cache Miss) via POST /chat/ask...")
    question_text = "What is the minimum CGPA required for good standing in Computer Science?"
    session_id = f"smoke_session_{int(time.time())}"
    chat_payload = {
        "question": question_text,
        "session_id": session_id,
        "scope": "public",
        "top_k": 3,
    }

    t0 = time.perf_counter()
    res_ask1 = client.post("/chat/ask", json=chat_payload)
    latency_1 = round((time.perf_counter() - t0) * 1000.0, 2)
    ask1_data = res_ask1.json()

    safe_answer_1 = ask1_data.get("answer", "").encode("ascii", "replace").decode("ascii")
    print(f"Status Code: {res_ask1.status_code} ({latency_1} ms)")
    print(f"Answer: {safe_answer_1}")
    print(f"Sources: {len(ask1_data.get('sources', []))} citations")
    print(f"is_cache_hit: {ask1_data.get('is_cache_hit')}")

    assert res_ask1.status_code == 200, f"Query 1 failed: {ask1_data}"
    assert ask1_data.get("is_cache_hit") is False, "First query should be a cache miss"
    assert len(ask1_data.get("sources", [])) > 0, "Should return at least one citation reference"
    print("-> Step 4 Result: PASS")

    # 5. Submit Identical Question (Cache Hit) via POST /chat/ask
    print("\n[Step 5] Submitting Identical Question (Cache Hit) via POST /chat/ask...")
    t1 = time.perf_counter()
    res_ask2 = client.post("/chat/ask", json=chat_payload)
    latency_2 = round((time.perf_counter() - t1) * 1000.0, 2)
    ask2_data = res_ask2.json()

    safe_answer_2 = ask2_data.get("answer", "").encode("ascii", "replace").decode("ascii")
    print(f"Status Code: {res_ask2.status_code} ({latency_2} ms)")
    print(f"Answer: {safe_answer_2}")
    print(f"is_cache_hit: {ask2_data.get('is_cache_hit')}")

    assert res_ask2.status_code == 200, f"Query 2 failed: {ask2_data}"
    assert ask2_data.get("is_cache_hit") is True, "Second query MUST be a cache hit"
    print("-> Step 5 Result: PASS")

    # 6. Verify MySQL Persistence for Both Interactions
    print("\n[Step 6] Verifying MySQL Message Records for Session...")
    conn = pymysql.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", "12345678"),
        database=os.getenv("MYSQL_DATABASE", "campusmind"),
    )
    cur = conn.cursor()
    cur.execute(
        "SELECT role, is_cache_hit, content, source_references FROM messages WHERE session_id = %s ORDER BY created_at ASC, id ASC;",
        (session_id,),
    )
    messages = cur.fetchall()
    conn.close()

    print(f"Total Messages Logged in MySQL for Session: {len(messages)}")
    for i, (role, hit, content, sources) in enumerate(messages, start=1):
        print(f"  [{i}] role={role}, is_cache_hit={bool(hit)}, snippet={content[:60]}...")

    assert len(messages) == 4, f"Expected 4 messages (2 user + 2 assistant), found {len(messages)}"
    assert messages[1][1] == 0, "First assistant response should have is_cache_hit = False"
    assert messages[3][1] == 1, "Second assistant response should have is_cache_hit = True"
    print("-> Step 6 Result: PASS")

    # 7. Check GET /metrics/cache and Health
    print("\n[Step 7] Checking GET /metrics/cache and final GET /health...")
    res_metrics = client.get("/metrics/cache")
    print(f"Metrics Status: {res_metrics.status_code}")
    metrics = res_metrics.json()
    print(f"Cache Metrics (FR-15): {metrics}")

    assert res_metrics.status_code == 200
    assert metrics["hits"] >= 1, "Metrics should show at least 1 cache hit"
    assert metrics["misses"] >= 1, "Metrics should show at least 1 cache miss"
    assert metrics["llm_calls_avoided"] >= 1, "Metrics should show at least 1 avoided LLM call"
    print("-> Step 7 Result: PASS")

    print("\n============================================================")
    print("SMOKE TEST SUMMARY: ALL 7 CHECKS PASSED (NO BLOCKERS)")
    print("============================================================")

if __name__ == "__main__":
    run_smoke_test()

