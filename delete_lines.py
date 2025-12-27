lines_to_keep = []
file_path = 'backend/static/app_v2.js'
start_delete = 2678
end_delete = 2958

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

with open(file_path, 'w', encoding='utf-8') as f:
    for i, line in enumerate(lines):
        line_num = i + 1
        if line_num < start_delete or line_num > end_delete:
            f.write(line)

print(f"Deleted lines {start_delete} to {end_delete}")
