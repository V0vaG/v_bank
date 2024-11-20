import os
import json

def load_topic(topic_id, data_dir):
    topic_dir = os.path.join(data_dir, topic_id)
    json_file = os.path.join(topic_dir, f"{topic_id}.json")
    md_file = os.path.join(topic_dir, f"{topic_id}.md")

    topic_data = []
    topic_content = ""

    if os.path.exists(json_file):
        with open(json_file, 'r') as f:
            topic_data = json.load(f)

    if os.path.exists(md_file):
        with open(md_file, 'r') as f:
            topic_content = f.read()

    return topic_data, topic_content

def save_topic(topic_id, topic_data, topic_content, data_dir):
    topic_dir = os.path.join(data_dir, topic_id)
    os.makedirs(topic_dir, exist_ok=True)

    json_file = os.path.join(topic_dir, f"{topic_id}.json")
    md_file = os.path.join(topic_dir, f"{topic_id}.md")

    with open(json_file, 'w') as f:
        json.dump(topic_data, f, indent=4)

    with open(md_file, 'w') as f:
        f.write(topic_content)

def generate_topic_id(data_dir):
    existing_ids = sorted([int(d) for d in os.listdir(data_dir) if d.isdigit()])

    next_topic_id = 1
    for topic_id in existing_ids:
        if topic_id == next_topic_id:
            next_topic_id += 1
        else:
            break

    return str(next_topic_id)
