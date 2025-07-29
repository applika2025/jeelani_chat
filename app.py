from flask import Flask, render_template, request, send_from_directory, redirect, url_for, jsonify
import os, json, socket, datetime, glob

app = Flask(__name__)

SHARE_DIR = 'shared_folder'
TASK_FILE = 'tasks.json'
CHAT_DIR = 'chat_data'
INSTALL_FLAG = 'C:/ProgramData/FileShareApp/installed.flag'

# Ensure folders exist
os.makedirs(SHARE_DIR, exist_ok=True)
os.makedirs(CHAT_DIR, exist_ok=True)
os.makedirs(os.path.dirname(INSTALL_FLAG), exist_ok=True)

# Ensure task file exists
if not os.path.exists(TASK_FILE):
    json.dump([], open(TASK_FILE, 'w'))

connected_clients = set()

def get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except:
        return 'localhost'

def get_chat_filename(date=None):
    date = date or datetime.date.today()
    return os.path.join(CHAT_DIR, f'chat_{date}.json')

def cleanup_old_chats():
    all_files = glob.glob(os.path.join(CHAT_DIR, 'chat_*.json'))
    today = datetime.date.today()
    for f in all_files:
        try:
            date_str = os.path.basename(f).split('_')[1].split('.')[0]
            file_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
            if (today - file_date).days > 5:
                os.remove(f)
        except:
            continue

@app.before_request
def track_clients():
    ip = request.remote_addr
    device_name = request.user_agent.platform or "Device"
    client_id = f"{ip} ({device_name})"
    connected_clients.add(client_id)

@app.context_processor
def inject_globals():
    return dict(
        connected_clients=sorted(connected_clients),
        connected_count=len(connected_clients),
        ip=get_ip(),
        pc=socket.gethostname()
    )

@app.route('/')
def index():
    files = os.listdir(SHARE_DIR)
    with open(TASK_FILE, 'r') as f:
        tasks = json.load(f)
    return render_template("index.html", files=files, tasks=tasks)

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files['file']
    if file:
        file.save(os.path.join(SHARE_DIR, file.filename))
    return redirect(url_for('index'))

@app.route('/download/<filename>')
def download(filename):
    return send_from_directory(SHARE_DIR, filename, as_attachment=True)

# ✅ Old Form-Based Task Routes (legacy fallback)
@app.route('/add_task', methods=['POST'])
def add_task():
    task = request.form['task']
    with open(TASK_FILE, 'r+') as f:
        tasks = json.load(f)
        tasks.append({'task': task, 'done': False})
        f.seek(0)
        json.dump(tasks, f)
    return redirect(url_for('index'))

@app.route('/toggle_task/<int:index>')
def toggle_task(index):
    with open(TASK_FILE, 'r+') as f:
        tasks = json.load(f)
        tasks[index]['done'] = not tasks[index]['done']
        f.seek(0)
        f.truncate()
        json.dump(tasks, f)
    return redirect(url_for('index'))

@app.route('/delete_task/<int:index>')
def delete_task(index):
    with open(TASK_FILE, 'r+') as f:
        tasks = json.load(f)
        tasks.pop(index)
        f.seek(0)
        f.truncate()
        json.dump(tasks, f)
    return redirect(url_for('index'))

# ✅ New API-Based Task Routes (AJAX)
@app.route('/api/tasks')
def api_tasks():
    with open(TASK_FILE, 'r') as f:
        tasks = json.load(f)
    return jsonify(tasks)

@app.route('/api/add_task', methods=['POST'])
def api_add_task():
    data = request.get_json()
    task_text = data.get('task', '').strip()
    if task_text:
        with open(TASK_FILE, 'r+') as f:
            tasks = json.load(f)
            tasks.append({'task': task_text, 'done': False})
            f.seek(0)
            f.truncate()
            json.dump(tasks, f)
        return jsonify({'status': 'success'}), 200
    return jsonify({'status': 'error'}), 400

@app.route('/api/delete_task/<int:index>', methods=['DELETE'])
def api_delete_task(index):
    with open(TASK_FILE, 'r+') as f:
        tasks = json.load(f)
        if 0 <= index < len(tasks):
            tasks.pop(index)
            f.seek(0)
            f.truncate()
            json.dump(tasks, f)
            return jsonify({'status': 'deleted'}), 200
    return jsonify({'status': 'not_found'}), 404

@app.route('/api/toggle_task/<int:index>', methods=['POST'])
def api_toggle_task(index):
    with open(TASK_FILE, 'r+') as f:
        tasks = json.load(f)
        if 0 <= index < len(tasks):
            tasks[index]['done'] = not tasks[index]['done']
            f.seek(0)
            f.truncate()
            json.dump(tasks, f)
            return jsonify({'status': 'toggled'}), 200
    return jsonify({'status': 'not_found'}), 404

# ✅ Chat Routes
@app.route('/chat')
def chat():
    messages = []
    today = datetime.date.today()
    for i in range(5):
        fpath = get_chat_filename(today - datetime.timedelta(days=i))
        if os.path.exists(fpath):
            with open(fpath) as f:
                try:
                    messages.extend(json.load(f))
                except:
                    continue
    return render_template('chat.html', messages=messages[-100:])

@app.route('/send_message', methods=['POST'])
def send_message():
    cleanup_old_chats()
    message = request.form['message']
    name = request.form['name']

    if not message.strip():
        return redirect(url_for('chat'))

    msg = {
        'name': name,
        'text': message,
        'time': datetime.datetime.now().strftime('%I:%M %p')
    }

    chat_file = get_chat_filename()
    messages = []
    if os.path.exists(chat_file):
        with open(chat_file, 'r') as f:
            try:
                messages = json.load(f)
            except:
                messages = []

    messages.append(msg)
    with open(chat_file, 'w') as f:
        json.dump(messages[-100:], f)

    return redirect(url_for('chat'))

@app.route('/get_messages')
def get_messages():
    messages = []
    today = datetime.date.today()
    for i in range(5):
        fpath = get_chat_filename(today - datetime.timedelta(days=i))
        if os.path.exists(fpath):
            with open(fpath) as f:
                try:
                    messages.extend(json.load(f))
                except:
                    continue
    return jsonify(messages[-100:])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
