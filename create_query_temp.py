import os
import httpx

base = "https://support.wirenboard.com"
headers = {
    "Api-Key": "5a847cbd1ab985c9a052e1035849798704a7af46a4a6122f3560a9054469aeb8",
    "Api-Username": "system",
}
sql = """
SELECT DISTINCT ON (t.id)
  t.id AS topic_id,
  CONCAT('https://support.wirenboard.com/t/', t.id) AS topic_link,
  t.title AS topic_title,
  u.username AS assigned_user,
  t.updated_at AS last_updated
FROM topics t
JOIN topic_custom_fields tcf ON t.id = tcf.topic_id
JOIN assignments a ON t.id = a.topic_id
JOIN users u ON a.assigned_to_id = u.id
WHERE tcf.name = 'accepted_answer_post_id'
  AND tcf.value IS NOT NULL
  AND t.archived = false
  AND t.closed = false
  AND t.updated_at >= NOW() - INTERVAL '5 months'
  AND NOT EXISTS (
    SELECT 1
    FROM posts p2
    WHERE p2.topic_id = t.id
      AND p2.raw LIKE '%эта тема была автоматически закрыта%'
  )
ORDER BY t.id, t.updated_at DESC
"""
name = "auto_unassign_solved_topics_v1"
client = httpx.Client(base_url=base, headers=headers, timeout=30)
q = client.get("/admin/plugins/explorer/queries.json")
q.raise_for_status()
for item in q.json().get("queries", []):
    if item.get("name") == name:
        print(f"EXISTING_QUERY_ID={item.get('id')}")
        raise SystemExit(0)
payload = {"name": name, "description": "For discourse-assignee-automation service", "sql": sql}
r = client.post("/admin/plugins/explorer/queries", json=payload)
print("STATUS", r.status_code)
r.raise_for_status()
data = r.json()
print(f"CREATED_QUERY_ID={data.get('id')}")
