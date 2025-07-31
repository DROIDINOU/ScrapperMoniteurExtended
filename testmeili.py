import meilisearch

client = meilisearch.Client("http://127.0.0.1:7700")
index_name = "debug_test_index"

try:
    index = client.get_index(index_name)
except meilisearch.errors.MeilisearchApiError:
    print("[INFO] Index not found, creating it...")
    task = client.create_index(index_name, {"primaryKey": "id"})
    client.wait_for_task(task.task_uid)
    index = client.get_index(index_name)

print(f"[DEBUG] Type de 'index': {type(index)}")

docs = [{"id": "1", "titre": "Test doc"}]
response = index.add_documents(docs)
print(f"[DEBUG] Type de 'response': {type(response)}")
print("Task UID:", response.task_uid)

index.wait_for_task(response.task_uid)
print("OK.")
