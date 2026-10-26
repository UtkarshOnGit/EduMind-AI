import urllib.request
import json
import time

API_BASE = "http://localhost:5001/api/v1"
AI_BASE = "http://localhost:8000/api/v1"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjZhYjk0MDYxNzdiMDhmMWU1M2Y3M2E5YSIsImlhdCI6MTc5MDUzMjg0NCwiZXhwIjoxNzkxMTM3NjQ0fQ.MGK2Lko2LpV3IZs_5CaU-FB32UHF79njO1h_zujLDaI"
COURSE_ID = "6ab9417977b08f1e53f73aef"

def stream_chat(query, conversation_id=None):
    payload = {"query": query}
    if conversation_id:
        payload["conversationId"] = conversation_id

    req = urllib.request.Request(
        f"{API_BASE}/courses/{COURSE_ID}/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    )

    assigned_id = None
    tokens = []
    citations = []

    with urllib.request.urlopen(req) as resp:
        for line in resp:
            line_str = line.decode("utf-8").strip()
            if line_str.startswith("data: "):
                raw = line_str[6:].strip()
                if raw == "[DONE]":
                    break
                try:
                    data = json.loads(raw)
                    if "conversationId" in data and not assigned_id:
                        assigned_id = data["conversationId"]
                    if "token" in data:
                        tokens.append(data["token"])
                    if "citations" in data:
                        citations = data["citations"]
                except Exception:
                    pass

    return {
        "conversation_id": assigned_id or conversation_id,
        "answer": "".join(tokens).strip(),
        "citations": citations
    }

def get_conversations():
    req = urllib.request.Request(
        f"{API_BASE}/courses/{COURSE_ID}/conversations",
        headers={"Authorization": f"Bearer {TOKEN}"}
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

def get_conversation_detail(conv_id):
    req = urllib.request.Request(
        f"{API_BASE}/courses/{COURSE_ID}/conversations/{conv_id}",
        headers={"Authorization": f"Bearer {TOKEN}"}
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

def delete_conversation(conv_id):
    req = urllib.request.Request(
        f"{API_BASE}/courses/{COURSE_ID}/conversations/{conv_id}",
        headers={"Authorization": f"Bearer {TOKEN}"},
        method="DELETE"
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

print("=================================================================")
print("  MULTI-SESSION CHAT & LANGGRAPH PIPELINE VERIFICATION SUITE")
print("=================================================================\n")

# STEP 1: Start Chat Session A (Memoization)
print("1. [Session A] Asking initial question (no conversationId)...")
q1 = "What is memoization in dynamic programming?"
res1 = stream_chat(q1)
conv_a = res1["conversation_id"]
print(f"   -> Session A Created! ID: {conv_a}")
print(f"   -> Answer snippet: {res1['answer'][:100]}...")
print(f"   -> Citations received: {len(res1['citations'])}")
assert conv_a is not None, "Failed to create Session A"
assert len(res1["citations"]) > 0, "No citations received"

# STEP 2: Follow-up question in Session A (testing short-term memory & rephraser)
print("\n2. [Session A] Follow-up question relying on memory: 'How does it compare to tabulation?'...")
res2 = stream_chat("How does it compare to tabulation?", conversation_id=conv_a)
print(f"   -> Answer snippet: {res2['answer'][:100]}...")
print(f"   -> Citations received: {len(res2['citations'])}")

detail_a = get_conversation_detail(conv_a)
msg_count_a = len(detail_a["data"]["messages"])
print(f"   -> Session A total stored messages: {msg_count_a} (Expected: 4)")
assert msg_count_a == 4, f"Expected 4 messages in Session A, got {msg_count_a}"

# STEP 3: Start Chat Session B (New Chat - separate ID and clean memory)
print("\n3. [Session B] Creating independent New Chat session on 'Optimal Substructure'...")
q3 = "What is optimal substructure?"
res3 = stream_chat(q3)
conv_b = res3["conversation_id"]
print(f"   -> Session B Created! ID: {conv_b}")
print(f"   -> Answer snippet: {res3['answer'][:100]}...")
print(f"   -> Citations received: {len(res3['citations'])}")
assert conv_b != conv_a, f"Session B should have a distinct ID from Session A! Got {conv_b}"

detail_b = get_conversation_detail(conv_b)
msg_count_b = len(detail_b["data"]["messages"])
print(f"   -> Session B total stored messages: {msg_count_b} (Expected: 2)")
assert msg_count_b == 2, f"Expected 2 messages in Session B, got {msg_count_b}"

# STEP 4: Verify Multi-Session Isolation and List
print("\n4. Listing all conversations for student...")
conv_list = get_conversations()
ids = [c["_id"] for c in conv_list["data"]]
print(f"   -> Active session IDs: {ids}")
assert conv_a in ids, "Session A missing from conversations list"
assert conv_b in ids, "Session B missing from conversations list"

# STEP 5: Clean up test Session B while keeping Session A
print("\n5. Deleting Session B and verifying Session A is preserved...")
del_b = delete_conversation(conv_b)
print(f"   -> Deleted Session B: {del_b['success']}")

conv_list_after = get_conversations()
remaining_ids = [c["_id"] for c in conv_list_after["data"]]
assert conv_b not in remaining_ids, "Session B should be deleted"
assert conv_a in remaining_ids, "Session A should remain intact"
print("   -> Successfully verified session deletion and persistence!")

print("\n=================================================================")
print("  ALL MULTI-SESSION CHAT & LANGGRAPH TESTS PASSED (100%)")
print("=================================================================")
