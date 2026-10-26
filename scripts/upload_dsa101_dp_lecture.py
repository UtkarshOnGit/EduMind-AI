import sys
import os
import time
from bson import ObjectId
from pymongo import MongoClient

# Ensure ai-service is on Python path
ai_service_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ai-service"))
if ai_service_path not in sys.path:
    sys.path.insert(0, ai_service_path)

from app.core.config import settings
from app.services.embedding_service import embedding_service
from app.services.qdrant_service import qdrant_service
from app.services.chunking_service import chunking_service

def format_time(seconds: float) -> str:
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"

# Structured semantic blocks from user's lecture content
DP_LECTURE_BLOCKS = [
    {
        "block_index": 0,
        "start_time": 0.0,
        "end_time": 75.0,
        "text": (
            "Dynamic Programming (DP) Introduction. Dynamic Programming is a commonly used algorithmic "
            "technique used to optimize recursive solutions when the same subproblems are called again and again. "
            "The core idea behind DP is to store solutions to subproblems so that each is solved only once. "
            "To solve DP problems, we first write a recursive solution in a way that there are overlapping subproblems "
            "in the recursion tree where the recursive function is called with the same parameters multiple times. "
            "To make sure that a recursive value is computed only once to improve algorithm execution time, we store "
            "results of the recursive calls. There are two primary ways to store the results: one is top-down (or memoization) "
            "and the other is bottom-up (or tabulation)."
        )
    },
    {
        "block_index": 1,
        "start_time": 75.0,
        "end_time": 165.0,
        "text": (
            "When to Use Dynamic Programming (DP)? Dynamic programming is used for solving problems that possess "
            "two foundational characteristics: 1. Optimal Substructure: This property means that we use the optimal "
            "results of subproblems to achieve the optimal result of the bigger problem. For example, in finding the "
            "minimum cost path in a weighted graph from a source node to a destination node, we break it down into finding "
            "the minimum cost path from source to intermediate nodes, and from intermediate nodes to destination. "
            "2. Overlapping Subproblems: The same subproblems are solved repeatedly in different parts of the problem. "
            "For example, in computing the Fibonacci series, calculating F(n) requires F(n-1) and F(n-2), while F(n-1) "
            "again requires F(n-2) and F(n-3). Here, the subproblem F(n-2) is computed multiple times in the recursion tree."
        )
    },
    {
        "block_index": 2,
        "start_time": 165.0,
        "end_time": 240.0,
        "text": (
            "Approaches of Dynamic Programming: Dynamic programming can be achieved using two main approaches: "
            "1. Top-Down Approach (Memoization): In the top-down approach, also known as memoization, we keep the solution "
            "recursive and add a memoization lookup table to avoid repeated calls of the same subproblems. Before making "
            "any recursive call, we first check if the memoization table already has the solution for it. After the recursive "
            "call is over, we store the solution in the memoization table. "
            "2. Bottom-Up Approach (Tabulation): In the bottom-up approach, also known as tabulation, we start with the "
            "smallest subproblems and gradually build up to the final solution iteratively, avoiding recursion overhead. "
            "We use a dp table where we first fill base cases and then fill remaining entries using the recurrence formula."
        )
    },
    {
        "block_index": 3,
        "start_time": 240.0,
        "end_time": 320.0,
        "text": (
            "Example of Dynamic Programming: Consider finding the Fibonacci sequence (0, 1, 1, 2, 3, 5, 8, 13, 21, 34...). "
            "The brute force recursive approach fib(n) = fib(n-1) + fib(n-2) has exponential time complexity O(2^n) because "
            "of repeated redundant work in the recursion tree. "
            "Using the Memoization Approach achieves O(n) Time and O(n) Space by using a memo array initialized to -1. "
            "If memo[n] != -1 we return the stored result; otherwise we compute memo[n] = fibRec(n-1, memo) + fibRec(n-2, memo). "
            "Using the Tabulation Approach also achieves O(n) Time and O(n) Space iteratively by allocating vector<int> dp(n+1), "
            "setting dp[0]=0, dp[1]=1, and filling dp[i] = dp[i-1] + dp[i-2] in a loop from i=2 to n."
        )
    },
    {
        "block_index": 4,
        "start_time": 320.0,
        "end_time": 375.0,
        "text": (
            "Space-Optimized Dynamic Programming: Notice that the current Fibonacci number depends only on the previous two values. "
            "Therefore, we do not need to store the entire table of size n+1. Instead, we can store only the previous two values "
            "using three variables: prevPrev, prev, and curr. We initialize prevPrev=0, prev=1, and iteratively compute: "
            "curr = prev + prevPrev; prevPrev = prev; prev = curr. This optimizes auxiliary space from O(n) down to O(1) Space "
            "while maintaining O(n) linear execution time."
        )
    },
    {
        "block_index": 5,
        "start_time": 375.0,
        "end_time": 440.0,
        "text": (
            "Common Algorithms that Use Dynamic Programming: "
            "Longest Common Subsequence (LCS) used in file diff comparison utilities; "
            "Edit Distance used for spell checkers and string similarity like Google's 'did you mean'; "
            "Longest Increasing Subsequence (LIS); Bellman-Ford Shortest Path algorithm; Floyd-Warshall all-pairs shortest path; "
            "0/1 Knapsack Problem for capacity optimization; Matrix Chain Multiplication. "
            "Key Advantages of DP: avoids recomputing identical subproblems leading to massive runtime speedups, and guarantees "
            "finding the optimal solution by systematically evaluating state combinations. Applications include computer science, "
            "combinatorial optimization, and operations research."
        )
    }
]

def upload_dp_lecture():
    print("=" * 75)
    print("🎓  UPLOADING DYNAMIC PROGRAMMING LECTURE & VECTORS FOR DSA101")
    print("=" * 75)

    # 1. Connect to MongoDB
    mongo_client = MongoClient(settings.MONGODB_URI)
    db = mongo_client["edumind-ai"]

    # 2. Locate Professor & Course
    prof = db.users.find_one({"email": "professor2@gmail.com"})
    if not prof:
        print("❌ Error: User 'professor2@gmail.com' not found in MongoDB.")
        sys.exit(1)
    print(f"✅ Found Professor: {prof.get('name')} ({prof.get('email')}) [ID: {prof['_id']}]")

    course = db.courses.find_one({"code": "DSA101"})
    if not course:
        print("❌ Error: Course 'DSA101' not found in MongoDB.")
        sys.exit(1)

    course_id_str = str(course["_id"])
    print(f"✅ Found Course   : {course.get('code')} - {course.get('title')} [ID: {course_id_str}]")

    # Enroll all students in DSA101 so students can test chatting too
    all_students = list(db.users.find({"role": "student"}))
    student_ids = [s["_id"] for s in all_students]
    if student_ids:
        db.courses.update_one(
            {"_id": course["_id"]},
            {"$addToSet": {"enrolledStudents": {"$each": student_ids}}}
        )
        print(f"✅ Enrolled {len(student_ids)} students into {course['code']} for access testing.")

    # 3. Create or Update Lecture in MongoDB
    lecture_title = "Lecture 1: Dynamic Programming (DP) Introduction"
    lecture_desc = "Optimal Substructure, Overlapping Subproblems, Memoization vs Tabulation, and Fibonacci Space Optimization."
    
    # Use a working Cloudinary MP4 video sample so the HTML5 video player can play & seek
    sample_video_url = "https://res.cloudinary.com/demo/video/upload/spiderman.mp4"

    # Upsert lecture record
    lecture = db.lectures.find_one({"courseId": course["_id"], "title": lecture_title})
    now = time.time()
    if lecture:
        lecture_id = lecture["_id"]
        db.lectures.update_one(
            {"_id": lecture_id},
            {
                "$set": {
                    "description": lecture_desc,
                    "cloudinaryUrl": sample_video_url,
                    "cloudinaryPublicId": "edumind/lectures/dsa101_dp_intro",
                    "duration": 440,
                    "status": "processed",
                    "processingError": None
                }
            }
        )
        print(f"✅ Updated existing Lecture in MongoDB: '{lecture_title}' [ID: {lecture_id}]")
    else:
        lecture_doc = {
            "courseId": course["_id"],
            "title": lecture_title,
            "description": lecture_desc,
            "cloudinaryUrl": sample_video_url,
            "cloudinaryPublicId": "edumind/lectures/dsa101_dp_intro",
            "duration": 440,
            "status": "processed",
            "processingError": None
        }
        res = db.lectures.insert_one(lecture_doc)
        lecture_id = res.inserted_id
        print(f"✅ Created new Lecture in MongoDB: '{lecture_title}' [ID: {lecture_id}]")

    lecture_id_str = str(lecture_id)

    # 4. Ingest Chunks & Vectors into Qdrant & MongoDB
    print("\n--- [INGESTING CHUNKS INTO QDRANT & MONGODB] ---")
    chunk_payloads = [
        {"start_time": b["start_time"], "end_time": b["end_time"], "text": b["text"]}
        for b in DP_LECTURE_BLOCKS
    ]

    import httpx
    try:
        # If FastAPI server is running live, call /api/v1/ingest/chunks so the running process indexes it
        ingest_res = httpx.post(
            "http://localhost:8000/api/v1/ingest/chunks",
            json={
                "course_id": course_id_str,
                "lecture_id": lecture_id_str,
                "lecture_title": lecture_title,
                "chunks": chunk_payloads
            },
            timeout=60.0
        )
        if ingest_res.status_code == 200:
            print(f"✅ Ingested {len(chunk_payloads)} chunks via live AI microservice: {ingest_res.json()}")
        else:
            raise RuntimeError(f"Server returned {ingest_res.status_code}: {ingest_res.text}")
    except Exception as e:
        print(f"⚠️ Live server call failed ({e}). Performing direct indexing...")
        # Direct fallback
        raw_blocks_to_insert = [
            {
                "courseId": course["_id"],
                "lectureId": lecture_id,
                "blockIndex": b["block_index"],
                "startTime": b["start_time"],
                "endTime": b["end_time"],
                "text": b["text"]
            }
            for b in DP_LECTURE_BLOCKS
        ]
        db.transcriptblocks.delete_many({"lectureId": lecture_id})
        db.transcriptblocks.insert_many(raw_blocks_to_insert)

        chunks = [
            {
                "chunk_id": f"{lecture_id_str}_c{i}",
                "course_id": course_id_str,
                "lecture_id": lecture_id_str,
                "lecture_title": lecture_title,
                "chunk_index": i,
                "start_time": b["start_time"],
                "end_time": b["end_time"],
                "text": b["text"],
                "token_count": len(b["text"].split())
            }
            for i, b in enumerate(DP_LECTURE_BLOCKS)
        ]
        chunk_texts = [c["text"] for c in chunks]
        embeddings = embedding_service.embed_passages(chunk_texts)
        qdrant_service.upsert_chunks(chunks, embeddings)
        qdrant_service.close()

    # 5. Test Query via Live API Server
    print("\n--- [TESTING LIVE RAG CHATBOT FOR DSA101] ---")
    test_query = "What is the difference between memoization and tabulation in dynamic programming?"
    try:
        chat_res = httpx.post(
            "http://localhost:8000/api/v1/chat/query-sync",
            json={
                "course_id": course_id_str,
                "student_id": "student1",
                "query": test_query
            },
            timeout=30.0
        )
        if chat_res.status_code == 200:
            chat_data = chat_res.json()
            print(f"🔍 Question : \"{test_query}\"")
            print(f"💡 Answer   :\n{chat_data.get('answer')}\n")
            print(f"🔖 Citations: {len(chat_data.get('citations', []))}")
            for c in chat_data.get("citations", []):
                print(f"   -> [{c['lecture_title']} @ {format_time(c['start_time'])} - {format_time(c['end_time'])}] Score: {c['score']:.4f}")
        else:
            print("Chat query failed:", chat_res.status_code, chat_res.text)
    except Exception as chat_err:
        print(f"Live chat test exception: {chat_err}")

    print("=" * 75)
    print("🎉 ALL CONTENT SUCCESSFULLY SAVED IN QDRANT & MONGODB!")
    print(f"👉 Course Code   : {course['code']}")
    print(f"👉 Course URL    : http://localhost:3000/courses/{course_id_str}")
    print(f"👉 Login User    : professor2@gmail.com (or student1@gmail.com)")
    print("=" * 75)

if __name__ == "__main__":
    upload_dp_lecture()
